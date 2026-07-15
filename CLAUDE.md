# Claude continuation brief

## Objective

Continue developing MemLedgerBench as a vendor-neutral conformance and research harness for
permission-aware memory in social/chat agents.

Start with `README.md`, `docs/competitive_audit.md`, and `docs/release_audit.md`. Treat the latter two
as the claim boundary: do not reintroduce “first/only multi-user privacy/deletion benchmark” language.
GateMem and PiSAs materially overlap those broad claims.

## Current state

- Package/version: `mem-ledger-bench` 0.2.0, Python 3.11+, standard library only.
- Tests: 21 passing with `python -m unittest discover -s tests -v`.
- Public fixture: 5 entities, 5 spaces, 27 events, 16 queries.
- Scales: small/stress add noise but not new structural query templates.
- Strongest implemented mechanics: evaluator-owned evidence policy oracle, online allowlisted replay,
  multi-recipient audience intersection, membership-history policies, deletion tombstone, and one
  snapshot/reset/restore checkpoint.
- Hard limits: unsandboxed product process; public/gameable worlds; exact-string answer leakage; no
  fixed-reader track; no raw audio; no generated policy-change event; no research-grade leaderboard.

## Commands

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
mem-ledger-bench validate data/fixtures/tiny_social.json
mem-ledger-bench run data/fixtures/tiny_social.json --adapter bm25-policy --repetitions 3 --out results/policy.json
mem-ledger-bench suite --config configs/benchmark_matrix.json --adapter bm25-policy --out results/suite.json
```

Use the active environment's Python interpreter; do not bake any machine-specific runtime path into
package code or public documentation.

## Next priorities

1. Add a containerized/no-network execution path and opaque sealed per-run IDs.
2. Add policy change, rejoin, role downgrade, expiry, retry, delayed/out-of-order, and rebuild worlds.
3. Implement counterfactual twin evaluation for semantic and side-channel non-interference.
4. Add a fixed-reader retrieval track with explicit token budget and comparable-run manifest.
5. Diversify world structures/personas/templates and add a human-authored blind set.
6. Add provenance/derivative deletion hooks and crash/index-loss recovery tests.
7. Add a consented matched audio/transcript track only after the above core governance work.
8. Add summary-only results, complete JSON Schema, positive control, and choose a license.

## Engineering rules

- Preserve the evaluator/adapter boundary; never send gold answers, labels, seeds, reference
  transcripts, or future events to the system under test.
- Treat privacy failures as ranking disqualifiers.
- Keep stability separate from the fixed composite.
- Cluster related scale variants by latent seed/world family.
- Use exact, versioned claims and primary sources; vendor scores are not mutually comparable.
- Do not run untrusted adapter commands outside a real sandbox.
- Keep all bundled data synthetic.
