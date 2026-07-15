# Sanitized baseline results

**Run date:** 15 July 2026  
**Version:** 0.2.0  
**Data:** deterministic synthetic fixture only

These are engineering controls, not competitive product results. Both controls fail the exact-match
deployment smoke gate and are therefore ineligible for ranking.

## Tiny fixture

Command settings: seed 7 fixture, top-k 3, three repeated read-only queries. Critical violations are
counted per scored response, so the totals below scale with the repetition setting (two distinct
violating queries × three repetitions for the policy-aware control).

| Adapter | Descriptive score | Utility | Decision macro-F1 | Evidence F1 | Exact safety | Critical violations | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| policy-aware BM25 | 82.33 | 1.000 | 1.000 | 0.781 | 0.733 | 6 | No |
| deliberately unsafe BM25 | 48.13 | 0.667 | 0.407 | 0.448 | 0.400 | 21 | No |

The policy filter reduces critical exposures from 21 to 6 and, because it refuses with a typed `deny`
whenever the strongest lexical match is blocked for the requester or audience, it now makes the
required deny decisions on the permission queries. It is still not safe: both of its remaining
critical violations come from the memory-poisoning slice, where a permission-legal but untrusted
injected message is retrieved and its forbidden content is echoed back. Membership rules alone cannot
detect poisoned memory; the gate fails by design for this control.

## Standard suite

Settings: five seeds × `tiny`/`small`/`stress`, five query repetitions, top-k 5. Related scale
conditions are clustered by seed, leaving five independent seed clusters.

| Aggregate | Value |
|---|---:|
| Descriptive score | 77.47 |
| Task utility | 1.000 |
| Evidence F1 | 0.664 |
| Exact safety | 0.733 |
| Deployment gate | Fail |
| Ranking eligibility | Ineligible |

The bootstrap interval collapses to a point (77.47–77.47) because the current seeds vary nonce
values but produce identical aggregate behavior for this baseline. This is evidence that the
generator needs structural/template diversity; it is not evidence of precise population performance.

Detailed JSON reports are deliberately untracked because they store raw adapter answers and evidence
IDs. Reproduce them locally with the commands in `README.md`.
