# Adapter example results

These are **integration examples, not a leaderboard**. They show that open memory systems wire into
the JSONL protocol and produce real, gate-checked numbers on the same replay every other system runs.
They are **not** a ranking: settings differ per system (see caveats), the public worlds are small, and
the bundled controls share the evaluator's access rules by construction.

Every number below comes from a real local run on 2026-07-16 (macOS, CPython 3.14). Vendor systems used
OpenAI `gpt-4o-mini` for the LLM and `text-embedding-3-small` for embeddings; retrieval `top_k = 5`;
`repetitions = 3`. Adapters live in [`examples/`](../examples).

## Results

| System | Scale | SLS | Utility | Evidence F1 | Safety | Stability | Gate | p50 | p95 |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| **Mem0** | tiny | 74.68 | 1.000 | 0.605 | 0.733 | 1.000 | FAIL | 213 ms | 278 ms |
| **Mem0** | small | 71.72 | 0.967 | 0.560 | 0.733 | 1.000 | FAIL | 219 ms | 296 ms |
| **Cognee** | tiny | 74.68 | 1.000 | 0.605 | 0.733 | 0.979 | FAIL | 5.6 s | 12.4 s |
| bm25-policy *(control)* | tiny | 79.78 | 1.000 | 0.716 | 0.733 | 1.000 | FAIL | ~0 ms | ~0 ms |
| bm25-policy *(control)* | small | 76.32 | 1.000 | 0.638 | 0.733 | 1.000 | FAIL | 0.5 ms | 0.8 ms |
| reference-control | tiny | 84.49 | 1.000 | 0.716 | 0.867 | 1.000 | PASS | ~0 ms | ~0 ms |
| reference-control | small | 80.62 | 1.000 | 0.638 | 0.867 | 1.000 | PASS | 0.5 ms | 0.9 ms |

SLS = safe lifecycle score (harmonic mean of utility, authorized-evidence F1, and safety, ×100), reported
for all systems here for illustration; only gate-passers are ranking-eligible. The two `*(control)*`
rows and `reference-control` are the bundled engineering controls, included only as scale anchors — do
not read the examples as "beating" or "losing to" them.

## How to read this (caveats that matter)

1. **Both vendor examples FAIL the deployment gate for the same, non-vendor reason.** Each adapter
   synthesizes its answer as the raw concatenation of retrieved message text — so an authorized but
   sensitive message trips the evaluator's answer-level forbidden-string check (2 critical violations
   per repetition, exactly like the bundled `bm25-policy` control). This is a property of the naive
   answer step in the *example*, not of Mem0 or Cognee retrieval. A real submission would add an
   answer-shaping / redaction pass; `reference-control` shows the gate is passable.

2. **On `tiny`, Mem0 and Cognee score identically (74.68) — that is expected, not a bug.** Evidence F1
   is count-based: on the 16-query fixture both systems retrieve every gold item (recall 1.0) with the
   same retrieved count, and both trip the same two answer-level disclosures, so utility, F1, and safety
   coincide. They genuinely differ on *which* distractors they surface (7 of 16 queries), but that does
   not move count-based metrics at this size. This is exactly why the spec warns against treating tiny
   worlds as a leaderboard — `small` already separates Mem0 (71.72) from the controls.

3. **Cognee is `tiny`-only and `--no-recovery` here.** Its `cognify()` graph build is expensive
   (per-query p50 ≈ 5.6 s including amortized graph construction; the reps=3 tiny run took ≈ 9 min).
   Running it on `small` (≈150 messages) with recovery was out of scope for a lean example budget. Mem0
   runs `tiny` + `small` with the full recovery track.

4. **Latency is harness timing, not a product SLO.** BM25 controls are in-process (~0 ms). Mem0 (~215 ms
   p50) does a real embedding round-trip to OpenAI per query. Cognee does graph search plus an LLM step.
   These numbers are not comparable as deployed latencies.

5. **Fairness.** Each example wraps the vendor library for ingestion and retrieval only; the
   authorization gate (membership / deletion / audience, reconstructed online from the event stream) is
   the same `_OnlinePolicy` the `bm25-policy` control uses. A memory store cannot know the scenario's
   audience rules, so delegating the gate to it would fail every permission query. Adapters receive no
   gold answers, evidence labels, task tags, or seeds — only the runner's stripped protocol stream; the
   repository's gold-exposure test guards this.

## Reproduce

```sh
# Mem0
pip install mem0ai
export OPENAI_API_KEY=...
mem-ledger-bench run data/fixtures/tiny_social.json --adapter command \
  --command "python examples/mem0_adapter.py" --repetitions 3 --out results/mem0-tiny.json
mem-ledger-bench run data/generated/small.json --adapter command \
  --command "python examples/mem0_adapter.py" --repetitions 3 --out results/mem0-small.json

# Cognee (small worlds only; cognify is slow)
pip install cognee
export LLM_API_KEY=$OPENAI_API_KEY LLM_PROVIDER=openai LLM_MODEL=gpt-4o-mini
export EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-small EMBEDDING_DIMENSIONS=1536
mem-ledger-bench run data/fixtures/tiny_social.json --adapter command \
  --command "python examples/cognee_adapter.py" --repetitions 3 --no-recovery --timeout 300 \
  --out results/cognee-tiny.json
```

`small` is generated with `mem-ledger-bench generate --scale small --out data/generated/small.json`.
Zep/Graphiti and Letta adapters are future work: Zep needs a hosted service or self-hosted server, and
Graphiti needs Neo4j — both heavier to stand up than the two local examples here.
