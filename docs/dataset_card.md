# Dataset card: SocialMemBench synthetic fixture

## Summary

The bundled dataset is deterministic synthetic test data for a social-memory lifecycle conformance
harness. It contains no intentional real personal data and is designed for unit, integration, and
product-regression testing.

## Version and provenance

- Benchmark version: `0.2`
- Generator: `social_memory_bench.generator`
- Public fixture seed: `7`
- Public fixture scale: `tiny`
- Contents: 5 synthetic users/entities, 5 spaces, 27 events, 16 queries
- Modalities: text plus one app-supplied noisy voice transcript
- Hashing: every result records the canonical dataset SHA-256

## Included concepts

- aliases and a same-name collision;
- DMs, family/group, launch group, board channel, and public space;
- cross-space and multi-hop recall;
- corrected/edited information and stale evidence;
- retained-history and retroactive-revocation membership policies;
- requester and output-audience authorization;
- logical deletion, tombstone, and restore checkpoint;
- a prompt-injection/untrusted-source distractor;
- an explicitly stated local convention;
- a noisy transcript homophone.

## Intended use

- adapter protocol development;
- deterministic regression tests;
- smoke testing authorization and tombstone failures;
- measuring interference/latency as distractors are added;
- comparing versions of the same product under controlled local settings.

## Out-of-scope uses

- claims of population-level social reasoning;
- compliance certification or proof of physical erasure;
- raw speech, ASR, diarization, or bystander-consent evaluation;
- cross-cultural quality/fairness conclusions;
- trusted public leaderboard ranking;
- training or fine-tuning on private user communications.

## Known limitations

The `small` and `stress` worlds share the same core task templates and add synthetic noise. The corpus
does not contain independently authored topologies, real audio, attachments, screenshots, websites,
calendar/mail data, policy changes, rejoins, role downgrades, retries, out-of-order events, or real
crash/index rebuilds. Answer-level leakage checks use exact known strings.

## Privacy and ethics

Do not replace the synthetic events with real private messages or recordings without explicit
authorization, purpose limitation, data minimization, retention/deletion controls, and a documented
lawful basis. Do not infer sensitive or protected traits from identity, names, language, or group
membership.

## Licensing

The synthetic fixture is currently distributed under the repository's restrictive prototype license
status. Imported LoCoMo data is not bundled and remains subject to LoCoMo's CC BY-NC 4.0 terms.
