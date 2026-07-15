# Changelog

## Unreleased

- Added `run --responses-log`, which writes the raw adapter responses as JSONL (no gold, no scoring)
  so scores can be recomputed independently and deterministically from a submission.
- Added the sealed track: a no-network container runner (`Dockerfile`/`compose.yaml`), a
  `generate --sealed`/`seal_dataset` transform that produces opaque nonce-salted worlds
  (score-preserving), and a `sealed-run` command that emits only a result and a provenance manifest
  (seed, dataset sha, image digest). The runner now records all answers before building ground truth.
- Renamed the project to **MemLedgerBench** (package `mem_ledger_bench`, CLI `mem-ledger-bench`); the
  former name collided with a published benchmark (SocialMemBench, Owolabi, arXiv 2605.17789).
- Dual-licensed the release: Apache-2.0 for source code, CC BY 4.0 for the `data/` datasets.
- Corrected three citations (EverMemBench 2,400 QA, Letta memory-blocks doc URL, OmniMemEval
  two-track / six-stage protocol) and added the SocialMemBench and AFA "first"-claims to the
  claims-to-avoid list.
- Added `reference-control`, a positive engineering control (event store + evaluator-consistent
  policy replay + untrusted-provenance filtering) that passes the deployment smoke gate and anchors
  the metric scale; exposed the message `trust` provenance marker to adapters so poisoning can be
  resisted without gold labels.
- Removed answer-pool strings hard-coded in three distractor noise templates so no seed can leak a
  gold answer or forbidden string into noise.
- Replaced the semantic query id sent to adapters with an opaque, scenario-salted handle so the
  system under test can no longer read a query's expected decision from its label.
- Made the baseline's online policy seq-aware for deletions and policy changes, matching the
  evaluator's PolicyOracle at point-in-time queries.
- Taught the policy-aware BM25 control to refuse with a typed `deny` when its strongest lexical
  match is blocked for the requester or audience, and aligned the dataset/scoring fallback for
  should-abstain queries with the generator's `deny` convention.
- Removed dead code, hardened `python -O` invariants, and deduplicated the percentile helper.
- Documented the `contextual_integrity` gate reason, repetition-scaled violation counts, and why
  both bundled controls fail the smoke gate; refreshed baseline tables; made README code blocks
  cross-platform.

## 0.2.0 — 2026-07-14

- Repositioned the project as an engineering conformance prototype after auditing GateMem, PiSAs,
  GroupMemBench, EverMemBench, CIMemories, and OmniMemEval.
- Added typed-decision correctness, decision macro-F1, over-refusal, authorized-answer accuracy, and
  evidence Recall@10.
- Fixed the composite definition so sampling stability no longer changes its dimensions.
- Marked gate-failed systems ineligible for ranking.
- Clustered suite confidence intervals by seed across related scale conditions.
- Validated required suite slices and separated unenforced research targets from the smoke gate.
- Ensured adapter cleanup after reset failure and redacted command arguments in result metadata.
- Added competitive, release, dataset, security, citation, CI, and Claude handoff documentation.
- Expanded the test suite from 16 to 21 tests.

## 0.1.0 — 2026-07-14

- Initial deterministic generator, policy oracle, BM25 controls, JSONL adapter, LoCoMo importer,
  lifecycle runner, scoring, suite aggregation, and tests.
