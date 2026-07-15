# Product adapter protocol

> **Security warning:** v0.2 starts a normal local subprocess. It is not sandboxed. Run only adapter
> code you trust; do not use this protocol runner for untrusted public submissions.

The harness starts one persistent subprocess and exchanges newline-delimited JSON. Every request must
receive exactly one response. Diagnostic output belongs on standard error; standard output is reserved
for protocol messages.

## Operations

### Reset

The adapter receives non-secret scenario structure, but no event stream or test labels.

```json
{"op":"reset","scenario":{"benchmark_version":"0.2","scenario_id":"...","entities":[],"spaces":[],"metadata":{}}}
```

Respond with:

```json
{"ok":true}
```

### Ingest

Events arrive exactly once and in increasing `seq` order. Production-grade submissions should still
make ingestion idempotent because the future full benchmark includes duplicate retry conditions.

```json
{"op":"ingest","event":{"seq":12,"id":"m_12","type":"message","space_id":"g_1","author_id":"u_1","modality":"text","observed_text":"..."}}
```

Membership, delete, edit, and policy-change events use the same envelope. Respond with `{"ok":true}`.

Evaluator-only fields such as `reference_text`, gold facts, answers, and evidence labels are stripped
before ingestion.

### Query

```json
{"op":"query","query":{"id":"q_1","after_seq":40,"requester_id":"u_1","audience_ids":["u_2"],"active_space_id":"g_1","purpose":"post_to_group","question":"..."}}
```

Evaluator-only task labels, difficulty tags, generation seeds, answer keys, and forbidden-memory
annotations are never sent. The required response is:

```json
{
  "decision": "answer",
  "answer": "September 3",
  "retrieved_event_ids": ["m_27"],
  "confidence": 0.91,
  "metadata": {"retrieved_tokens": 84}
}
```

`decision` is one of `answer`, `abstain`, `deny`, or `clarify`. Evidence IDs must refer to ingested
events. Returning evidence is required for retrieval-track scoring; an answer-only service may return
an empty list, but will receive zero evidence credit.

The output audience is security-relevant. Evidence may be used only when every recipient can access it
at query time. A private answer to the requester and a message posted into a group are different tasks.
Query operations must be read-only with respect to durable memory; the harness may repeat an identical
query to estimate sampling stability.

### Snapshot and restore

At a checkpoint the harness sends:

```json
{"op":"snapshot"}
```

Return an opaque, JSON-serializable token or state:

```json
{"snapshot":{"id":"snapshot-17"}}
```

The harness then resets the adapter and sends:

```json
{"op":"restore","snapshot":{"id":"snapshot-17"}}
```

Respond with `{"ok":true}`. The restored state must retain acknowledged live events and tombstones.
If the product owns recovery externally, the snapshot value can be an opaque deployment identifier.

### Stats and close

```json
{"op":"stats"}
```

Recommended response:

```json
{"stats":{"storage_bytes":120430,"ingest_model_calls":14,"query_model_calls":0}}
```

The runner measures query wall time itself. On `{"op":"close"}`, respond once and exit cleanly.

## Fairness requirements

- Do not inspect dataset files or result labels from the adapter process.
- Freeze model, embedding, reranker, prompt, index, and policy versions in result metadata.
- Retrieval comparisons must use the same reader and retrieved-token budget.
- Run stochastic systems at least five times and aggregate by world, not by individual question.
- Treat policy and deletion failures as hard failures, even if the response omits citations.

Detailed result files preserve raw answers and evidence IDs. Protect them as potentially sensitive
product output. Adapter command arguments are fingerprinted rather than recorded verbatim, but
credentials should never be passed on the command line.
