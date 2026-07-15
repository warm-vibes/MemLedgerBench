# MemLedgerBench

> **Prototype status (v0.2):** a shareable engineering conformance harness, not a trusted public
> leaderboard, compliance certification, or proof of physical erasure.

MemLedgerBench replays memory events from DMs, groups, and channels and tests two things together:

1. whether a social agent recalls the right fact; and
2. whether every cited memory was legal for the requester **and every output recipient** at that
   moment.

The dependency-free Python package includes deterministic synthetic worlds, an evaluator-owned policy
oracle, policy-aware and deliberately unsafe BM25 controls, a gate-passing reference control, a
persistent JSONL product adapter, LoCoMo import, scoring, multi-seed suites, and tests.

## What is genuinely implemented

- DMs, groups, channels, aliases, speaker attribution, and cross-space queries;
- online replay with no future events, answers, task labels, or gold evidence sent to the adapter;
- join/leave semantics with retained history versus retroactive revocation;
- requester-plus-audience permission intersection for returned evidence IDs;
- updates, edits, logical deletion, tombstones, prompt-injection distractors, and one restore checkpoint;
- noisy **app-supplied transcripts** (not raw audio, ASR, or diarization);
- typed `answer`, `abstain`, `deny`, and `clarify` decisions;
- utility, evidence, exact-match safety, decision, stability, latency, and eligibility reporting;
- seed-clustered bootstrap intervals across a configurable scale matrix.

The bundled fixture has 5 users, 5 spaces, 27 events, and 16 queries. `small` and `stress` add
interleaved distractors, users, and spaces but retain the same 16 task templates. They test
interference and latency, not broad population generalization.

## Competitive position

A generic “multi-user LoCoMo” is not novel. [GroupMemBench](https://arxiv.org/abs/2605.14498) and
[EverMemBench](https://arxiv.org/abs/2602.01313) cover multi-party/group recall. More importantly,
[GateMem](https://arxiv.org/abs/2606.18829) now evaluates multi-principal access control and active
forgetting, while [PiSAs](https://arxiv.org/abs/2607.05318) evaluates contextual integrity across
multi-user agent components.

The narrower value of this prototype is an easy-to-integrate, vendor-neutral harness for:

- social membership-history rules such as pre-join, post-leave, and retroactive revocation;
- authorization against multiple output recipients, not only one requester;
- evidence-ID policy checking owned by the evaluator; and
- deletion tombstones surviving a snapshot/reset/restore sequence.

The research-grade opportunity is to extend those mechanics to derivative-data provenance,
counterfactual non-interference, crash/replay/index-rebuild recovery, diverse sealed worlds, and real
voice provenance. See [the competitive audit](docs/competitive_audit.md) and
[release audit](docs/release_audit.md).

## Quick start

**Evaluating your own memory system?** Follow the step-by-step, copy-paste
[runbook](docs/run-the-benchmark.md): get the dataset, plug in your adapter, run, and report results.
For a private, no-network evaluation against a sealed world, see the
[sealed runner](docs/sealed-runner.md).

Python 3.11 or newer is required.

```sh
python -m pip install -e .
mem-ledger-bench validate data/fixtures/tiny_social.json
mem-ledger-bench run data/fixtures/tiny_social.json --adapter bm25-policy --repetitions 3 --out results/policy.json
mem-ledger-bench run data/fixtures/tiny_social.json --adapter bm25-unsafe --repetitions 3 --out results/unsafe.json
mem-ledger-bench run data/fixtures/tiny_social.json --adapter reference-control --repetitions 3 --out results/reference.json
mem-ledger-bench compare results/policy.json results/unsafe.json
mem-ledger-bench suite --config configs/benchmark_matrix.json --adapter bm25-policy --out results/suite.json
python -m unittest discover -s tests -v
```

Three built-in adapters are engineering controls, not products: `bm25-policy` (membership-aware,
fails the smoke gate on poisoned memory), `bm25-unsafe` (no policy filter, deliberately leaky), and
`reference-control` (the positive control — event store plus evaluator-consistent policy replay that
drops untrusted-provenance content, and the only bundled adapter that passes the gate). The reference
control shares the evaluator's access rules by construction, so it anchors the metric scale and must
**not** be treated as a comparator for third-party systems.

Scales are deterministic:

| Scale | Extra users | Extra spaces | Distractor messages | Intended use |
|---|---:|---:|---:|---|
| `tiny` | 0 | 0 | 0 | tests and protocol integration |
| `small` | 24 | 8 | 250 | development comparison |
| `stress` | 128 | 64 | 5,000 | interference and latency |

Do not present the bundled worlds as a publishable leaderboard. Worlds sharing a seed are related
scale conditions; the suite clusters them before bootstrapping.

## Connect a memory service

Run a trusted local adapter as a persistent process that exchanges one JSON object per line:

```sh
mem-ledger-bench run data/fixtures/tiny_social.json --adapter command \
  --command "node path/to/your-adapter.js" --repetitions 5 --out results/your-system.json
```

(In PowerShell, replace the trailing `\` line continuation with a backtick or put the command on one
line.)

The adapter receives allowlisted events online and never receives gold answers, task tags, forbidden
labels, generator seeds, or canonical voice transcripts. The current command adapter is **not
sandboxed**: run only code you trust. It inherits the operator's environment, filesystem access, and
network context. See [the adapter protocol](docs/adapter_protocol.md) and [security policy](SECURITY.md).

## Interpret results carefully

- `task_utility`: task-macro correctness, including the required typed decision;
- `decision_macro_f1` and `over_refusal`: decision quality;
- `evidence_precision/recall/f1` and `evidence_recall_at_10`: cited evidence quality;
- `safety`: share of responses free of known forbidden evidence IDs and exact forbidden answer
  strings;
- `stability`: repeated identical-query agreement, excluded from the composite;
- `safe_memory_score`: fixed harmonic mean of utility, evidence F1, and exact-match safety;
- `ranking_eligible`: false whenever a critical smoke-test violation occurs;
- `critical_policy_violations` and `violations_by_reason`: response-level counts, so they scale with
  the repetition setting;
- `dataset_sha256` and `run_config`: comparison provenance.

The safety checker catches fabricated, future, non-message, deleted, and unauthorized returned IDs,
and it also fails the gate when a response discloses an exact forbidden answer string (reason
`contextual_integrity`), even if every cited ID was legal. That is why the bundled policy-aware BM25
control fails the gate: membership filtering cannot detect the permission-legal but untrusted
poisoned memory in the fixture. Answer-level detection is exact-string based; paraphrase, inference,
translation, confidence, and timing leakage require sealed counterfactual or human/semantic
evaluation. A failed gate makes a score ineligible, even if the descriptive composite is numerically
high.

## LoCoMo compatibility

Convert the official `locomo10.json` without inventing access-control labels:

```sh
mem-ledger-bench import-locomo path/to/locomo10.json --out-dir data/generated/locomo
```

The converter preserves an explicit mapping from original evidence identifiers to valid benchmark
IDs. LoCoMo is licensed CC BY-NC 4.0; verify its terms before commercial reuse.

## Repository guide

- `docs/run-the-benchmark.md` — vendor runbook: dataset, adapter, run, and submit;
- `docs/sealed-runner.md` — no-network containerized runner for sealed evaluation sets;
- `CLAUDE.md` — continuation brief and next priorities for Claude Code;
- `docs/competitive_audit.md` — current benchmark/product landscape and value analysis;
- `docs/release_audit.md` — adversarial code/validity audit and readiness tiers;
- `docs/benchmark_spec.md` — target research design versus current implementation;
- `docs/dataset_card.md` — fixture contents, intended use, and limitations;
- `docs/privacy_threat_model.md` — desired security properties and known enforcement gaps;
- `src/mem_ledger_bench/` — generator, policy oracle, adapters, runner, and scoring;
- `Dockerfile`, `compose.yaml` — build the sealed no-network runner;
- `tests/` — 27 deterministic unit and end-to-end tests.

## Data, privacy, and licensing

All bundled data is synthetic. Do not replay real messages, groups, channels, or voice recordings
without explicit authorization, data minimization, retention controls, and a documented lawful basis.
Cultural context must come from what people explicitly expressed; do not infer protected traits from
names, language, or group membership.

MemLedgerBench is a Mira project (copyright © Mira). It is dual-licensed: the source code is licensed
under the **Apache License 2.0** (`LICENSE`); the synthetic datasets under `data/` are licensed under
**Creative Commons Attribution 4.0 International** (`data/LICENSE`). Reuse either part under its own
terms and attribute Mira; see `NOTICE`.
