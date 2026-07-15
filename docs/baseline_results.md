# Sanitized baseline results

**Run date:** 14 July 2026  
**Version:** 0.2.0  
**Data:** deterministic synthetic fixture only

These are engineering controls, not competitive product results. Both controls fail the exact-match
deployment smoke gate and are therefore ineligible for ranking.

## Tiny fixture

Command settings: seed 7 fixture, top-k 3, three repeated read-only queries.

| Adapter | Descriptive score | Utility | Decision macro-F1 | Evidence F1 | Exact safety | Critical violations | Eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| policy-aware BM25 | 62.40 | 0.667 | 0.282 | 0.514 | 0.733 | 6 | No |
| deliberately unsafe BM25 | 48.13 | 0.667 | 0.407 | 0.448 | 0.400 | 21 | No |

The policy filter reduces critical exposures from 21 to 6, which shows that the policy oracle detects
the intended difference. It does not make BM25 safe: lexical retrieval still returns contextual,
untrusted, or stale items and does not make the required deny decisions reliably.

## Standard suite

Settings: five seeds × `tiny`/`small`/`stress`, five query repetitions, top-k 5. Related scale
conditions are clustered by seed, leaving five independent seed clusters.

| Aggregate | Value |
|---|---:|
| Descriptive score | 52.19 |
| Task utility | 0.667 |
| Evidence F1 | 0.353 |
| Exact safety | 0.733 |
| Deployment gate | Fail |
| Ranking eligibility | Ineligible |

The bootstrap interval collapses to a point (52.19–52.19) because the current seeds vary nonce values
but produce identical aggregate behavior for this baseline. This is evidence that the generator needs
structural/template diversity; it is not evidence of precise population performance.

Detailed JSON reports are deliberately untracked because they store raw adapter answers and evidence
IDs. Reproduce them locally with the commands in `README.md`.
