#!/usr/bin/env bash
# One-command fresh-clone proof: installs deps, runs the agent end-to-end on a
# real mainnet contract, shows the written artifact. Judges run this, done.
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || uv venv .venv
source .venv/bin/activate
uv pip install -q -r requirements.txt

[ -f .env ] && set -a && . ./.env && set +a && echo "Loaded .env: live mainnet run." || echo "No .env: agent runs deterministic MOCK mode (needs no keys)."

cd src
../.venv/bin/python - <<'EOF'
import os
os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY","mock-key"))
from agent import run_reasoning_loop
out = run_reasoning_loop(
  "Triage 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2: check it's a contract, "
  "read name() and totalSupply() via eth_call, write triage_note.md.")
print("--- reasoning trace ---")
for s in out["steps"]:
    print(f"[{s['role']}] {str(s['content'])[:90]}")
print("--- artifact: triage_note.md ---")
print(open("triage_note.md").read()[:600])
EOF
