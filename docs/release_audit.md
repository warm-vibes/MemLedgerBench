# Adversarial release audit

**Audit date:** 14 July 2026  
**Audited version:** 0.2.0

## Verdict

The repository is safe to share as a synthetic development prototype and Claude handoff. It is a
useful internal regression harness. It is not yet safe to operate as a trusted public leaderboard or
to execute untrusted third-party adapters.

The audit found no apparent credentials or real personal data. Twenty-one tests pass.

## Actual coverage

| Scale | Entities | Spaces | Events | Queries | What changes |
|---|---:|---:|---:|---:|---|
| `tiny` | 5 | 5 | 27 | 16 | core lifecycle fixture |
| `small` | 29 | 13 | 332 | 16 | extra users/spaces and 250 distractors |
| `stress` | 133 | 69 | 5,493 | 16 | extra users/spaces and 5,000 distractors |

The scale conditions share the same core world and query templates for a given seed. Version 0.2
therefore clusters scale variants by seed before bootstrapping; the interval remains descriptive
because the generator has one structural template family.

## What is done well

- explicit allowlists and deep copies at the evaluator-to-adapter boundary;
- generator seeds, gold answers, task labels, forbidden labels, future events, and reference voice
  transcripts are not sent through the protocol;
- evaluator-owned checks catch unknown, fabricated, future, invalid, deleted, and unauthorized
  returned evidence IDs;
- clear requester-plus-audience intersection and compact membership-history policies;
- deterministic generation, online replay, dataset SHA-256, run configuration, and a negative control;
- logical deletion plus one tombstone-preserving restore checkpoint;
- honest synthetic-data, raw-audio, and physical-erasure boundaries;
- command-line adapter arguments are no longer written verbatim into result files.

## Fixed during this audit

1. Typed decisions now affect utility; `deny` with a correct answer string no longer earns credit.
2. Decision macro-F1, over-refusal, authorized-answer accuracy, and Recall@10 are reported.
3. The composite always uses the same three components; stability is separate.
4. Gate-failed systems are marked `ranking_eligible: false` and receive no `ranking_score`.
5. Overall bootstrap intervals cluster related scale conditions by seed.
6. Required suite slices are validated instead of silently ignored.
7. Research-release thresholds are labeled as unenforced, not executable gates.
8. Adapter cleanup now runs even when initial reset fails.
9. Command arguments are redacted and represented by a fingerprint in results.
10. Malformed `forbidden_evidence` now produces a validation error instead of an attribute crash.
11. Claims were rewritten around GateMem, PiSAs, and OmniMemEval.

## P0 blockers for a trusted leaderboard

### No submission isolation

The JSONL process inherits the operator's environment, filesystem, and network access. It can read
benchmark files, modify the host, inspect credentials, or exfiltrate data. Timeouts stop the direct
process but are not a security sandbox.

Required fix: run submissions in locked-down containers or VMs with a scrubbed environment, no
network, resource limits, read-only submission files, and no evaluator/gold filesystem mount.

### Public worlds are gameable

Scenario and event/query IDs are semantic; seeds/templates are published; a local adapter can inspect
or regenerate the corpus. This is acceptable for development, not leaderboard validity.

Required fix: evaluator-private nonce worlds, opaque per-run IDs, sealed gold, post-submission fact
generation, limited submissions, and periodically refreshed human-authored cases.

## P1 validity and safety gaps

### Answer-level privacy is only a smoke test

The strong policy oracle applies to returned evidence IDs. Arbitrary answer text is checked only for
known normalized forbidden strings. Paraphrases, inferences, translations, omissions of citations,
confidence changes, ranking signals, and timing can leak without detection.

Required fix: counterfactual non-interference, semantic/human disclosure adjudication, required
provenance attestations, and separate direct/inferred/retrieval exposure metrics.

### Implemented gate is deliberately narrow

`deployment_gate_pass` means zero critical exact-evidence/exact-string smoke violations. It is not the
full research gate in the benchmark specification. Confidence-bound leakage, calibrated voice
retention, and fixed-reader validity are not implemented.

### No controlled fixed-reader track

The specification proposes retrieval and constrained end-to-end tracks with a common reader and 8K
budget. The code currently evaluates native adapter answers and evidence. Product comparisons can be
confounded by the reader model, prompt, top-k, judge, and tool autonomy.

### Incomplete lifecycle semantics

The schema accepts `policy_change`, but the generator has no such event. Prospective versus
retroactive policy changes, edit/delete authority, rejoin behavior, legal holds, expiry, retries,
out-of-order delivery, index rebuild, and concurrent edit/delete are future work.

### Result files can contain sensitive product output

Detailed reports store raw answers and evidence IDs. They are ignored under `results/*.json`, but an
operator can choose another path. Treat detailed outputs as sensitive, especially with real service
responses. A summary-only/redacted report mode remains to be implemented.

## P2 release gaps

- no complete JSON Schema for all dataset/protocol fields;
- no official-corpus LoCoMo integration test in CI;
- no passing full-world positive control (bundled BM25 controls intentionally fail);
- no independent human validation or severity-label audit;
- no selected open-source license;
- no release tag or reproducible package lock (runtime is standard-library only).

## Readiness tiers

| Use | Status | Conditions |
|---|---|---|
| Share with another coding agent | Ready | Use this repository/zip and `CLAUDE.md`. |
| Internal CI against trusted adapters | Ready with caveats | Synthetic data; protect detailed results; pin product/model versions. |
| Public prototype repository | Ready after account upload | Keep prototype banner and current restrictive license status. |
| Execute untrusted submissions | Not ready | Container/VM isolation required. |
| Publish comparative product claims | Not ready | Controlled adapters, common reader/budget, paired statistics required. |
| Academic leaderboard or certification | Not ready | Sealed diverse corpus, human validation, calibrated gates, anti-cheating required. |

## Highest-value next implementation order

1. isolated runner plus opaque sealed IDs;
2. policy-change/rejoin/retry/out-of-order/rebuild scenarios;
3. counterfactual twin evaluator and semantic disclosure audit;
4. fixed-reader retrieval track and comparable-run manifest;
5. diverse generators and human-authored blind set;
6. real consented audio track and provenance/derivative deletion hooks;
7. summary-only result mode, complete schema, and a deliberate license choice.
