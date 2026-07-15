# Changelog

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
