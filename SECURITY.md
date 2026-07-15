# Security policy

## Prototype boundary

SocialMemBench 0.2 is a development harness, not a security boundary. Its `--adapter command` mode
starts a normal local process. That process inherits the operator's filesystem permissions,
environment, and network context.

**Run only adapter code you trust.** Do not use this mode for third-party submissions, downloaded
scripts, or adversarial binaries. A timeout is not sandboxing and may not terminate every descendant
process.

## Sensitive outputs

Detailed result files contain raw adapter answers and evidence identifiers. Treat them as sensitive
when evaluating real services. The repository ignores `results/*.json`, but writing elsewhere can
bypass that protection. Never place credentials in command-line arguments; result metadata redacts
arguments, but operating-system process listings and shell history may still expose them.

## Data handling

Bundled fixtures are synthetic. Do not ingest real private messages, group histories, attachments, or
voice recordings without explicit authorization, data minimization, retention/deletion controls,
and a documented lawful basis.

## Reporting a vulnerability

This handoff repository has no configured security contact. Before public release, add a private
reporting channel and GitHub security policy contact owned by the project maintainer.

Do not include real secrets or personal data in a public issue.
