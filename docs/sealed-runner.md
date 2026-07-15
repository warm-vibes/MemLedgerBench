# Sealed runner (no-network container)

The sealed track scores a submission against a private world inside a container with **no network**.
It exists so a real (non-public) evaluation set can be used without the submission being able to
memorize it, exfiltrate it, or observe ground truth before answering. Everything below needs only
Docker — no host Python.

Three properties hold by construction:

- **Offline.** The run container has no network (`--network none` / `network_mode: none`), so a
  submission cannot phone home or leak the world.
- **Opaque worlds.** A sealed world uses nonce-salted, hashed identifiers (`e_…`, `u_…`, `s_…`,
  scenario id `sealed-…`), so a submission cannot infer structure or intent from names like
  `m_prompt_injection`. Sealing is score-preserving: a sealed world scores identically to its
  public twin.
- **Answers before ground truth.** The runner records every adapter answer first and only then builds
  the policy oracle and gold-derived labels, so no answer can be scored against or influenced by
  ground truth.

## 1. Build the runner image

```sh
docker build -t memledgerbench-sealed:local .
```

The build installs the benchmark (network is needed here, once). Runs are offline.

## 2. Generate a sealed world

Keep sealed worlds out of the public set and use a **private** nonce. Generate offline into a local
`sealed/` directory:

```sh
mkdir -p sealed out
docker run --rm --network none -v "$PWD/sealed:/sealed" memledgerbench-sealed:local \
  generate --scale tiny --seed 4242 --sealed --nonce "CHOOSE-A-PRIVATE-NONCE" \
  --out /sealed/world.json
```

```
generated sealed-23176f433214 (sealed): 5 users/entities, 5 spaces, 27 events, 16 queries -> /sealed/world.json
```

The seed selects the world; the nonce controls id opacity. Both stay on the evaluator side (the seed
lives in world metadata that is never sent to a submission).

## 3. Run a submission offline

Record the image digest (goes into the manifest for provenance), then run. Replace the `--command`
with your own adapter (see §5); the bundled `examples/unsafe_jsonl_adapter.py` is used here as a
self-contained demo.

```sh
export MLB_IMAGE_DIGEST="$(docker inspect --format '{{.Id}}' memledgerbench-sealed:local)"
docker run --rm --network none -e MLB_IMAGE_DIGEST \
  -v "$PWD/sealed:/world:ro" -v "$PWD/out:/out" \
  memledgerbench-sealed:local \
  sealed-run /world/world.json \
  --command "python examples/unsafe_jsonl_adapter.py" \
  --out-dir /out
```

```
jsonl-command: score=40.48, utility=0.600, retrieval_F1=0.364, safety=0.333, gate=FAIL, ranking=INELIGIBLE
sealed-run -> /out/result.json + manifest.json
```

Equivalently, with Compose (reads `./sealed` and `./out`):

```sh
export MLB_IMAGE_DIGEST="$(docker inspect --format '{{.Id}}' memledgerbench-sealed:local)"
docker compose run --rm sealed-runner
```

## 4. Outputs

The run emits exactly two files into `out/`:

- `result.json` — the full run result (summary, per-response rows, provenance).
- `manifest.json` — the provenance record:

```json
{
  "scenario_id": "sealed-23176f433214",
  "dataset_sha256": "fd916ccae132b0317f44b679a708d6185a34a78b33e9cf18836e8118f41b3277",
  "sealed": true,
  "seed": 4242,
  "scale": "tiny",
  "tool_version": "0.2.0",
  "image_digest": "sha256:0f7b0523…",
  "safe_memory_score": 40.48,
  "deployment_gate_pass": false,
  "ranking_eligible": false
}
```

`dataset_sha256` fingerprints the exact sealed world; `image_digest` and `tool_version` pin the runner
that produced the score. See [run-the-benchmark.md](run-the-benchmark.md) for what the score and gate
mean.

## 5. Bring your own adapter

Your adapter speaks the [JSONL protocol](adapter_protocol.md) — one JSON object per line over
stdin/stdout. It runs as a subprocess of the sealed runner, inside the same no-network container, so
it must be present in the image or mounted in. Two options:

- **Derived image:** write a `Dockerfile` with `FROM memledgerbench-sealed:local`, `COPY` your adapter
  in, and point `--command` at it.
- **Mount it:** add `-v "$PWD/my-adapter:/adapter:ro"` and use
  `--command "python /adapter/main.js"` (or your runtime). It still runs offline.

The runner never sends your adapter gold answers, evidence labels, task tags, or the sealing nonce.
