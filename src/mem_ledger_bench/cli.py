from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .adapters import JsonlCommandAdapter, LexicalAdapter, ReferenceControlAdapter
from .dataset import DatasetValidationError, load_dataset, save_dataset
from .generator import SCALES, generate_dataset, seal_dataset
from .locomo import import_locomo
from .runner import run_benchmark
from .suite import aggregate_world_results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mem-ledger-bench",
        description="Permission-aware lifecycle benchmark for social-agent memory",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    generate = subparsers.add_parser("generate", help="generate a deterministic synthetic world")
    generate.add_argument("--scale", choices=sorted(SCALES), default="tiny")
    generate.add_argument("--seed", type=int, default=7)
    generate.add_argument(
        "--sealed",
        action="store_true",
        help="seal the world with opaque, nonce-salted identifiers (for the sealed track)",
    )
    generate.add_argument(
        "--nonce",
        help="sealing nonce (defaults to the seed); use a private value for real sealed sets",
    )
    generate.add_argument("--out", type=Path, required=True)

    validate = subparsers.add_parser("validate", help="validate a dataset and gold policy labels")
    validate.add_argument("dataset", type=Path)

    run = subparsers.add_parser("run", help="replay and evaluate a memory system")
    run.add_argument("dataset", type=Path)
    run.add_argument(
        "--adapter",
        choices=["bm25-policy", "bm25-unsafe", "reference-control", "command"],
        default="bm25-policy",
    )
    run.add_argument(
        "--command",
        dest="adapter_command",
        help="JSONL adapter process command; required for --adapter command",
    )
    run.add_argument("--top-k", type=int, default=5)
    run.add_argument("--timeout", type=float, default=30.0, help="seconds per JSONL operation")
    run.add_argument("--repetitions", type=int, default=1)
    run.add_argument("--no-recovery", action="store_true")
    run.add_argument(
        "--responses-log",
        type=Path,
        help="also write the raw adapter responses as JSONL, for independent rescoring",
    )
    run.add_argument("--out", type=Path, required=True)

    suite = subparsers.add_parser("suite", help="run a multi-seed, multi-scale benchmark matrix")
    suite.add_argument("--config", type=Path, required=True)
    suite.add_argument(
        "--adapter",
        choices=["bm25-policy", "bm25-unsafe", "reference-control", "command"],
        default="bm25-policy",
    )
    suite.add_argument("--command", dest="adapter_command")
    suite.add_argument("--top-k", type=int, default=5)
    suite.add_argument("--timeout", type=float, default=30.0)
    suite.add_argument("--repetitions", type=int, help="override matrix repetitions")
    suite.add_argument("--out", type=Path, required=True)

    compare = subparsers.add_parser("compare", help="compare one or more result files")
    compare.add_argument("results", type=Path, nargs="+")
    compare.add_argument("--json", action="store_true", dest="as_json")
    compare.add_argument(
        "--allow-mixed",
        action="store_true",
        help="allow comparison across different dataset hashes",
    )

    locomo = subparsers.add_parser("import-locomo", help="convert official locomo10.json")
    locomo.add_argument("input", type=Path)
    locomo.add_argument("--out-dir", type=Path, required=True)

    sealed = subparsers.add_parser(
        "sealed-run",
        help="run a submission against a sealed world, emitting only result + manifest",
    )
    sealed.add_argument("dataset", type=Path)
    sealed.add_argument(
        "--command",
        dest="adapter_command",
        required=True,
        help="JSONL adapter process command for the submission",
    )
    sealed.add_argument("--out-dir", type=Path, required=True)
    sealed.add_argument("--top-k", type=int, default=5)
    sealed.add_argument("--timeout", type=float, default=30.0)
    sealed.add_argument("--repetitions", type=int, default=3)
    sealed.add_argument("--no-recovery", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "generate":
            dataset = generate_dataset(scale=args.scale, seed=args.seed)
            if args.sealed:
                nonce = args.nonce if args.nonce is not None else str(args.seed)
                dataset = seal_dataset(dataset, nonce)
            save_dataset(dataset, args.out)
            sealed_note = " (sealed)" if args.sealed else ""
            print(
                f"generated {dataset.scenario_id}{sealed_note}: {len(dataset.entities)} users/entities, "
                f"{len(dataset.spaces)} spaces, {len(dataset.events)} events, "
                f"{len(dataset.queries)} queries -> {args.out}"
            )
            return 0
        if args.action == "validate":
            dataset = load_dataset(args.dataset)
            print(
                f"valid: {dataset.scenario_id} ({len(dataset.events)} events, "
                f"{len(dataset.queries)} queries)"
            )
            return 0
        if args.action == "run":
            dataset = load_dataset(args.dataset)
            adapter = _create_adapter(args)
            result = run_benchmark(
                dataset,
                adapter,
                repetitions=args.repetitions,
                perform_recovery=not args.no_recovery,
                responses_log=args.responses_log,
            )
            _write_json(result, args.out)
            _print_summary(result)
            if args.responses_log:
                print(f"responses log -> {args.responses_log}")
            print(f"result -> {args.out}")
            return 0
        if args.action == "suite":
            config = _read_json(args.config)
            seeds = [int(seed) for seed in config.get("seeds", [])]
            scales = [str(scale) for scale in config.get("scales", [])]
            if not seeds or not scales:
                raise ValueError("suite config needs non-empty seeds and scales")
            unknown_scales = sorted(set(scales) - SCALES.keys())
            if unknown_scales:
                raise ValueError(f"unknown suite scales: {unknown_scales}")
            repetitions = (
                args.repetitions
                if args.repetitions is not None
                else int(config.get("repetitions", 1))
            )
            world_results = []
            required_slices = {str(item) for item in config.get("required_slices", [])}
            for scale in scales:
                for seed in seeds:
                    dataset = generate_dataset(scale=scale, seed=seed)
                    present_slices = {
                        str(tag) for query in dataset.queries for tag in query.get("tags", [])
                    }
                    missing_slices = sorted(required_slices - present_slices)
                    if missing_slices:
                        raise ValueError(
                            f"generated world is missing required slices: {missing_slices}"
                        )
                    result = run_benchmark(
                        dataset,
                        _create_adapter(args),
                        repetitions=repetitions,
                        perform_recovery=True,
                    )
                    world_results.append(result)
                    _print_summary(result)
            suite_result = {
                "format_version": "0.2",
                "suite_config": config,
                "adapter": args.adapter,
                "aggregate": aggregate_world_results(world_results),
                "world_results": world_results,
            }
            _write_json(suite_result, args.out)
            overall = suite_result["aggregate"]["overall"]["safe_memory_score"]
            print(
                f"suite: worlds={len(world_results)}, score={overall['mean']:.2f} "
                f"(95% CI {overall['ci95_low']:.2f}–{overall['ci95_high']:.2f}) -> {args.out}"
            )
            return 0
        if args.action == "compare":
            results = [_read_json(path) for path in args.results]
            hashes = {result.get("dataset_sha256") for result in results}
            if len(hashes) > 1 and not args.allow_mixed:
                raise ValueError(
                    "result files use different datasets; pass --allow-mixed for a non-paired view"
                )
            evaluation_configs = {
                (
                    result.get("run_config", {}).get("repetitions"),
                    result.get("run_config", {}).get("perform_recovery"),
                )
                for result in results
            }
            if len(evaluation_configs) > 1 and not args.allow_mixed:
                raise ValueError(
                    "result files use different repetition/recovery settings; "
                    "pass --allow-mixed for a non-paired view"
                )
            if args.as_json:
                print(json.dumps([_comparison_row(item) for item in results], indent=2))
            else:
                _print_comparison(results)
            return 0
        if args.action == "import-locomo":
            datasets = import_locomo(args.input)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            for dataset in datasets:
                save_dataset(dataset, args.out_dir / f"{dataset.scenario_id}.json")
            print(f"converted {len(datasets)} LoCoMo scenarios -> {args.out_dir}")
            return 0
        if args.action == "sealed-run":
            dataset = load_dataset(args.dataset)
            adapter = JsonlCommandAdapter(args.adapter_command, timeout_seconds=args.timeout)
            result = run_benchmark(
                dataset,
                adapter,
                repetitions=args.repetitions,
                perform_recovery=not args.no_recovery,
            )
            args.out_dir.mkdir(parents=True, exist_ok=True)
            _write_json(result, args.out_dir / "result.json")
            metadata = dataset.raw.get("metadata", {})
            manifest = {
                "format_version": "0.2",
                "created_at": result["created_at"],
                "scenario_id": result["scenario_id"],
                "dataset_sha256": result["dataset_sha256"],
                "sealed": bool(metadata.get("sealed", False)),
                "seed": metadata.get("seed"),
                "scale": metadata.get("scale"),
                "tool_version": _tool_version(),
                "image_digest": os.environ.get("MLB_IMAGE_DIGEST"),
                "run_config": result["run_config"],
                "safe_memory_score": result["summary"]["safe_memory_score"],
                "deployment_gate_pass": result["summary"]["deployment_gate_pass"],
                "ranking_eligible": result["summary"]["ranking_eligible"],
            }
            _write_json(manifest, args.out_dir / "manifest.json")
            _print_summary(result)
            print(f"sealed-run -> {args.out_dir}/result.json + manifest.json")
            return 0
    except (DatasetValidationError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled action {args.action!r}")


def _tool_version() -> str:
    return __version__


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _create_adapter(args: argparse.Namespace):
    if args.adapter == "command":
        if not args.adapter_command:
            raise ValueError("--command is required with --adapter command")
        return JsonlCommandAdapter(args.adapter_command, timeout_seconds=args.timeout)
    if args.adapter == "reference-control":
        return ReferenceControlAdapter(top_k=args.top_k)
    return LexicalAdapter(
        top_k=args.top_k,
        policy_aware=args.adapter == "bm25-policy",
    )


def _write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print(
        f"{result['adapter']}: score={summary['safe_memory_score']:.2f}, "
        f"utility={summary['task_utility']:.3f}, retrieval_F1={summary['evidence_f1']:.3f}, "
        f"safety={summary['safety']:.3f}, gate={'PASS' if summary['deployment_gate_pass'] else 'FAIL'}, "
        f"ranking={'ELIGIBLE' if summary.get('ranking_eligible') else 'INELIGIBLE'}"
    )


def _comparison_row(result: dict[str, Any]) -> dict[str, Any]:
    summary = result["summary"]
    return {
        "scenario": result["scenario_id"],
        "dataset_sha256": result.get("dataset_sha256"),
        "adapter": result["adapter"],
        "safe_memory_score": summary["safe_memory_score"],
        "ranking_score": summary.get("ranking_score"),
        "task_utility": summary["task_utility"],
        "evidence_f1": summary["evidence_f1"],
        "safety": summary["safety"],
        "stability": summary["stability"],
        "critical_violations": summary["critical_policy_violations"],
        "gate": summary["deployment_gate_pass"],
        "p95_ms": summary["latency_ms"]["p95"],
    }


def _print_comparison(results: list[dict[str, Any]]) -> None:
    rows = [_comparison_row(result) for result in results]
    headers = [
        "scenario",
        "adapter",
        "score",
        "utility",
        "retr.F1",
        "safety",
        "stable",
        "critical",
        "gate",
        "p95ms",
    ]
    print("  ".join(f"{header:>10}" for header in headers))
    for row in rows:
        values = [
            str(row["scenario"]),
            str(row["adapter"]),
            f"{row['safe_memory_score']:.2f}",
            f"{row['task_utility']:.3f}",
            f"{row['evidence_f1']:.3f}",
            f"{row['safety']:.3f}",
            f"{row['stability']:.3f}" if row["stability"] is not None else "n/a",
            str(row["critical_violations"]),
            "PASS" if row["gate"] else "FAIL",
            f"{row['p95_ms']:.2f}",
        ]
        print("  ".join(f"{value:>10}" for value in values))


if __name__ == "__main__":
    raise SystemExit(main())
