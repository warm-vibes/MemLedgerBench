# Sanitized baseline results

**Run date:** 15 July 2026  
**Version:** 0.2.0  
**Data:** deterministic synthetic fixture only

These are engineering controls, not competitive product results. The two BM25 controls fail the
exact-match deployment smoke gate; the reference control is designed to pass it and anchors the scale.

## Tiny fixture

Command settings: seed 7 fixture, top-k 3, three repeated read-only queries. Critical violations are
counted per scored response, so the totals below scale with the repetition setting (two distinct
violating queries × three repetitions for the policy-aware control).

| Adapter | Descriptive score | Utility | Decision macro-F1 | Evidence F1 | Exact safety | Critical violations | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| reference control (positive) | 87.36 | 1.000 | 1.000 | 0.781 | 0.867 | 0 | Yes |
| policy-aware BM25 | 82.33 | 1.000 | 1.000 | 0.781 | 0.733 | 6 | No |
| deliberately unsafe BM25 | 48.13 | 0.667 | 0.407 | 0.448 | 0.400 | 21 | No |

The policy filter reduces critical exposures from 21 to 6 and, because it refuses with a typed `deny`
whenever the strongest lexical match is blocked for the requester or audience, it makes the required
deny decisions on the permission queries. It is still not safe: both of its remaining critical
violations come from the memory-poisoning slice, where a permission-legal but untrusted injected
message is retrieved and its forbidden content is echoed back. Membership rules alone cannot detect
poisoned memory; the gate fails by design for that control.

The **reference control** is the same event store and evaluator-consistent policy replay, extended to
drop untrusted-provenance content (the `trust` marker a real ingestion pipeline attaches) instead of
echoing it. It passes the gate with zero critical violations and is ranking-eligible, which proves the
gate is passable without any gold label. It is a positive engineering control that anchors the metric
scale, **not a comparator**: it shares the evaluator's access-control implementation by construction,
so other systems must not be ranked against it. Its exact safety is 0.867 rather than 1.000 because it
still retrieves two *non-critical* forbidden items (a same-name distractor and a superseded version)
that carry no message-level provenance signal — declining them would require reading gold labels,
which it does not.

## Standard suite

Settings: five seeds × `tiny`/`small`/`stress`, five query repetitions, top-k 5. Related scale
conditions are clustered by seed, leaving five independent seed clusters.

| Aggregate | policy-aware BM25 | reference control |
|---|---:|---:|
| Descriptive score | 77.47 | 81.91 |
| Task utility | 1.000 | 1.000 |
| Deployment gate | Fail | Pass (all 15 worlds) |
| Ranking eligibility | Ineligible | Eligible |

The bootstrap interval collapses to a point (e.g. 77.47–77.47) because the current seeds vary nonce
values but produce identical aggregate behavior. This is evidence that the generator needs
structural/template diversity; it is not evidence of precise population performance. The reference
control passes the gate on every world, confirming the gate is passable at scale, not only on the
tiny fixture.

Detailed JSON reports are deliberately untracked because they store raw adapter answers and evidence
IDs. Reproduce them locally with the commands in `README.md`.
