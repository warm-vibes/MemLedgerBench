# Competitive and value audit

**Research snapshot:** 14 July 2026  
**Method:** primary papers, official repositories, and official product documentation. Vendor scores
are reported as vendor claims, not as an apples-to-apples leaderboard.

## Executive verdict

MemLedgerBench should not be positioned as the first multi-user, group-memory, privacy, deletion, or
recovery benchmark. Those broad claims are already occupied.

The credible v0.2 position is:

> A dependency-free conformance harness for permission-aware memory in chat products. It replays
> social membership, edits, deletion, and recovery online, then checks recall and whether every cited
> memory was authorized for the exact output audience.

Its narrow differentiation is the combination of membership-history semantics, multi-recipient
audience intersection, evaluator-owned evidence authorization, and tombstone behavior across restore.
Its long-term moat would come from sealed diverse scenarios, policy modeling, evidence provenance,
product connectors, and continuous regression—not from public synthetic templates or BM25.

## Benchmark landscape

| Benchmark | Strongest established coverage | Important difference or overlap |
|---|---|---|
| [GateMem](https://arxiv.org/abs/2606.18829) / [official repo](https://github.com/rzhub/GateMem) | 91 long multi-party episodes, 2,218 hidden checkpoints, legitimate utility, contextual access control, and explicit deletion/active forgetting | Closest collision. MemLedgerBench must not claim first multi-principal governance or forgetting. Remaining angle: membership-history policies, multiple output recipients, evidence-ID oracle, and restore/tombstone mechanics. |
| [PiSAs](https://arxiv.org/abs/2607.05318) | User and task appropriateness across outputs, inter-agent communication, shared memory, and agent topologies | Stronger contextual-integrity breadth; current MemLedgerBench has only one exact-string contextual case. |
| [GroupMemBench](https://arxiv.org/abs/2605.14498) | Group dynamics, speaker-grounded belief, audience language, ambiguity, updates, multi-hop, temporal reasoning, and abstention | Stronger social reasoning breadth; no formal membership-time ACL/deletion/recovery track. |
| [EverMemBench](https://arxiv.org/abs/2602.01313) / [official repo](https://github.com/EverMind-AI/EverMemBench) | Multi-party, multi-group interleaved histories beyond one million tokens and 2,400 QA | Stronger scale and collaborative complexity; no formal authorization/deletion lifecycle. |
| [CIMemories](https://arxiv.org/abs/2511.14937) / [official repo](https://github.com/facebookresearch/CIMemories) | Contextual-integrity profiles, disclosure/coverage, and repeated-run privacy instability | Stronger privacy evaluation; not a changing social membership event stream. |
| [OmniMemEval](https://github.com/MemTensor/OmniMemEval) | Two-track harness: a User Memory track wrapping LoCoMo/LongMemEval/BEAM/PersonaMem v2/HaluMem, and an Agent Memory track with a six-stage protocol (training, cleanup, backup, restore, memory settling, test) | Invalidates “no benchmark has recovery.” It does not specifically score tombstone non-resurrection through restore/rebuild. |
| [Memora](https://arxiv.org/abs/2604.20006) | Obsolete or invalidated fact reuse in personalized dialogue | Stronger forgetting-aware conversational quality; not multi-principal audience authorization. |
| [LoCoMo](https://aclanthology.org/2024.acl-long.747/) / [data](https://github.com/snap-research/locomo) | Ten long dyadic conversations, 1,986 QA, event summaries, and multimodal response generation | Compatibility track only; no groups, ACL, deletion, voice, or recovery. CC BY-NC 4.0 data. |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) | 500 questions for extraction, multi-session reasoning, updates, temporal reasoning, and abstention | Strong single-user baseline; no changing social authorization. |
| [LongMemEval V2](https://github.com/xiaowu0162/LongMemEval-V2) | Web/enterprise trajectories up to 115M tokens, workflows, dynamic facts, gotchas, and premise awareness | Much stronger operational breadth/scale; not a social-principal benchmark. |

### What this means

- Group memory itself is not the research contribution.
- Access control plus deletion itself is not the research contribution after GateMem.
- Contextual integrity itself is not the contribution after CIMemories and PiSAs.
- Backup/restore itself is not the contribution after OmniMemEval.
- The remaining hypothesis is lifecycle correctness across **social topology + membership time + output
  audience + provenance + failure recovery**.

## Product landscape

| Product/tool | Relevant capabilities from official sources | Implication for this project |
|---|---|---|
| [Mem0](https://github.com/mem0ai/mem0) | Entity scopes, graph memory, multimodal ingestion, and deletion operations; official [scope](https://docs.mem0.ai/platform/features/entity-scoped-memory) and [delete](https://docs.mem0.ai/core-concepts/memory-operations/delete) docs | Useful adapter target. Scopes are isolation primitives, not proof of dynamic group/audience policy correctness. |
| [Zep / Graphiti](https://github.com/getzep/graphiti) | Bitemporal knowledge graph, hybrid retrieval, invalidation, enterprise [ABAC](https://help.getzep.com/attribute-based-access-control) and [RBAC](https://help.getzep.com/role-based-access-control) | Strong temporal/enterprise comparator. Its [deletion docs](https://help.getzep.com/deleting-data-from-the-graph) illustrate why derivative-data closure matters. |
| [Letta](https://github.com/letta-ai/letta) | Stateful agents, archival memory, and dynamically [attached shared blocks](https://docs.letta.com/guides/core-concepts/memory/memory-blocks/) | Shared blocks are useful but application-controlled attachment is not a social authorization benchmark. |
| [Hindsight](https://github.com/vectorize-io/hindsight) | Facts, experiences, entity/temporal/causal structure, mental models, hybrid retrieval, and delete/clear APIs | Strong open memory-bank comparator; namespaces are not changing social ACLs by themselves. |
| [MemOS](https://github.com/MemTensor/MemOS) | Unified graph-structured memory, composable memory cubes, edit/delete, and OmniMemEval integration | Strong architecture and harness comparator; benchmark social governance separately. |
| [EverOS](https://github.com/EverMind-AI/EverOS) | Current local-first Markdown canonical store with SQLite/LanceDB indexes and user/agent/project/session scopes | Pin product generation and date; do not conflate current EverOS with older EverMemOS architecture claims. |
| [Backboard](https://docs.backboard.io/concepts/memory) | Managed assistant memory, documents/RAG, real-time voice, STT/TTS, transcripts, and deletion APIs | Useful voice/product adapter target. Published memory scores do not evaluate voice-memory safety. |
| [Cognee](https://github.com/topoteretes/cognee) | Graph/vector/ontology memory, explicit [multi-user permissions](https://docs.cognee.ai/core-concepts/multi-user-mode/permissions-system/overview), audio loading, snapshots, backup, and restore | One of the strongest targets for permission and recovery conformance tests. |
| [Supermemory](https://github.com/supermemoryai/supermemory) | Hybrid memory graph, contradiction/update/expiration, profiles, containers, forget, and deletion | Distinguish “exclude from recall” from permanent deletion when adapting. |
| [LangMem](https://github.com/langchain-ai/langmem) | Semantic/episodic/procedural memory tools and developer-defined namespaces | Security and lifecycle semantics belong to the application/store; a neutral harness is valuable. |

Vendor benchmark numbers are not directly comparable. Dataset versions, ingestion/backfill, reader
models, judges, retrieval budgets, top-k, agent tools, and exclusions differ. MemLedgerBench should
run products through one declared protocol rather than reproduce marketing tables.

## Audit of our value

### Strongest implemented value

1. **Evaluator-owned authorization.** Every returned event ID is independently checked for existence,
   event type, time, deletion, and audience access.
2. **Multi-recipient outputs.** A private answer and a post into a group are different security
   actions; authorization intersects the requester and all audience members.
3. **Social membership history.** `retain_seen`, `active_window`, `current_full`, and `public` express
   pre-join and post-leave visibility more directly than a simple user namespace.
4. **Online protocol.** The adapter sees only allowlisted scenario structure, past events, and the
   current query—not future events, gold labels, or reference transcripts.
5. **Engineering portability.** Standard-library Python plus JSONL makes the harness inexpensive to
   add to CI or wrap around a vendor API.
6. **Recovery-aware deletion smoke test.** A checkpoint/reset/restore sequence checks both retained
   live memory and a deleted tombstone.

### Weak or unproven claims

- Scale adds distractors but not new query structures or independently authored worlds.
- Exact forbidden-string checks miss paraphrase, inference, translation, and side channels.
- The voice slice is one corrupted transcript, not audio, ASR, diarization, or bystander consent.
- The cultural slice is one explicitly stated local convention, not cross-cultural validity.
- `policy_change` exists in the schema but no generated case exercises it.
- No fixed-reader 8K retrieval track or sealed leaderboard is implemented.
- The command adapter is unsandboxed and public templates/IDs can be memorized or inspected.
- Both bundled BM25 systems fail the smoke gate; they are negative engineering controls, not product
  baselines.

## Best users and business position

The immediate users are security/platform teams building memory for collaboration, family,
workplace, support, community, or multi-tenant agents; memory vendors needing ACL/deletion regression
tests; and product teams deciding whether a memory architecture is safe enough to pilot.

A defensible open-core path would be:

- **Open:** runner, adapter protocol, policy oracle, basic synthetic fixture, and CI examples.
- **Commercial/private:** sealed scenario corpus, policy compiler, product connectors, on-prem runner,
  governance dashboard, regression alerts, and audited red-team reports.
- **Moat:** hidden diverse worlds, provenance traces, workload importers, and continuously refreshed
  tests—not the public generator.

Do not market v0.2 as certification, compliance, physical erasure, a raw-voice benchmark, or an
academic leaderboard.

## Claims to avoid

- first or only group/multi-user memory benchmark;
- first social-group memory benchmark (SocialMemBench, Owolabi, [arXiv 2605.17789](https://arxiv.org/abs/2605.17789), May 2026, already holds this name and framing);
- first identity-aware multi-user attribution benchmark (occupied by AFA + PAT, [arXiv 2604.25022](https://arxiv.org/abs/2604.25022));
- first benchmark combining multi-principal access control and forgetting;
- no other benchmark tests recovery;
- zero observed leakage proves safety;
- logical non-retrieval proves GDPR erasure or deletion from every backup/index/model;
- vendor superiority from published scores with different protocols;
- commercial reuse of LoCoMo without accounting for its CC BY-NC 4.0 license.

## Recommended next proof points

1. sealed nonce worlds with opaque IDs and a containerized, no-network submission runner;
2. counterfactual twins differing only in hidden facts;
3. diverse human-reviewed social topologies, membership churn, policy changes, and rejoins;
4. provenance closure from message to summary, embedding, graph fact, cache, export, and backup;
5. crash/replay/index-loss/rebuild with duplicate, delayed, and out-of-order events;
6. matched gold transcript, noisy ASR, and consented multi-speaker audio;
7. controlled adapters for at least three products under one reader, budget, and judge protocol.
