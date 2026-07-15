from __future__ import annotations

import random
from statistics import fmean
from typing import Any


SUITE_METRICS = ("safe_memory_score", "task_utility", "evidence_f1", "safety")


def aggregate_world_results(
    results: list[dict[str, Any]], *, bootstrap_samples: int = 2_000, seed: int = 2026
) -> dict[str, Any]:
    """Macro-average worlds and bootstrap worlds as the independent unit."""

    if not results:
        raise ValueError("suite has no world results")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    by_scale: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        scale = str(result.get("dataset_metadata", {}).get("scale", "unknown"))
        by_scale.setdefault(scale, []).append(result)
    return {
        "worlds": len(results),
        "independent_seed_clusters": _cluster_count(results),
        "deployment_gate_pass": all(
            bool(result["summary"]["deployment_gate_pass"]) for result in results
        ),
        "overall": _aggregate_group(results, bootstrap_samples, seed),
        "by_scale": {
            scale: _aggregate_group(group, bootstrap_samples, seed + index + 1)
            for index, (scale, group) in enumerate(sorted(by_scale.items()))
        },
    }


def _aggregate_group(
    results: list[dict[str, Any]], bootstrap_samples: int, seed: int
) -> dict[str, Any]:
    random_source = random.Random(seed)
    metrics: dict[str, Any] = {
        "worlds": len(results),
        "independent_seed_clusters": _cluster_count(results),
    }
    for metric in SUITE_METRICS:
        values = _clustered_values(results, metric)
        bootstrap_means = sorted(
            fmean(random_source.choice(values) for _ in values)
            for _ in range(bootstrap_samples)
        )
        metrics[metric] = {
            "mean": fmean(values),
            "ci95_low": _percentile(bootstrap_means, 0.025),
            "ci95_high": _percentile(bootstrap_means, 0.975),
        }
    return metrics


def _clustered_values(results: list[dict[str, Any]], metric: str) -> list[float]:
    """Average scale conditions within a seed before bootstrapping seeds."""

    clusters: dict[str, list[float]] = {}
    for index, result in enumerate(results):
        seed = result.get("dataset_metadata", {}).get("seed")
        cluster = f"seed:{seed}" if seed is not None else f"result:{index}"
        clusters.setdefault(cluster, []).append(float(result["summary"][metric]))
    return [fmean(values) for values in clusters.values()]


def _cluster_count(results: list[dict[str, Any]]) -> int:
    return len(_clustered_values(results, SUITE_METRICS[0]))


def _percentile(sorted_values: list[float], fraction: float) -> float:
    index = (len(sorted_values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
