# Sealed-track runner image for MemLedgerBench.
#
# Build needs network (to install the package); the run does not. Score a
# submission offline with:
#   docker run --network none -v "$PWD/sealed:/world:ro" -v "$PWD/out:/out" \
#     memledgerbench-sealed sealed-run /world/world.json \
#     --command "python examples/unsafe_jsonl_adapter.py" --out-dir /out
FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .

# The submission adapter runs as a subprocess of this entrypoint, inside the
# same no-network container. Replace the --command with your own adapter.
ENTRYPOINT ["mem-ledger-bench"]
CMD ["--help"]
