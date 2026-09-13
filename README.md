# ChainPilot - an autonomous EVM recon agent (Strands Agents SDK)

**47 addresses. 30 clerical minutes. Zero of them yours.**

**Track: Professional Agents.** Security researchers burn hours on repetitive
on-chain triage: *is this address a contract, what does it call, what's the
supply, does the pattern match the docs?* ChainPilot runs that busywork
silently with tools that hit **live Ethereum mainnet over permissionless
public RPC**, and only surfaces the decoded triage note. No wallets, no keys
to chain services, no hallucinated numbers - every fact is a tool result.

Built with the **AWS Strands Agents SDK** (`strands-agents`), model-agnostic:
demo runs Gemini via `GeminiModel`; a one-line swap runs Bedrock/Anthropic.

## The repetitive loop it automates
```
prompt: "Triage 0xC02aaA...6Cc2"
 -> eth_get_code -> 3,124 bytes: it's a contract
 -> eth_call name -> "Wrapped Ether"
 -> eth_call totalSupply -> 3.2M WETH
 -> write_file triage_note.md (verified by reading it back)
 -> surfaces the summary, you make the judgment call
```

## Tools (Strands @tool functions)
| Tool | Purpose |
|---|---|
| `eth_call` | raw mainnet read via publicnode, llamarpc fallback |
| `eth_get_code` | contract liveness/size check |
| `eth_get_storage_at` | raw storage slot reads (EIP-1967 proxy targets) |
| `read_file` / `write_file` | artifact handling, sandboxed, 4 KB caps |

Agent loop, tool schemas, and retries are Strands' event loop - ChainPilot is
the system prompt, the EVM tool layer, and the triage workflow, not a
hand-rolled agent framework (the SDK's point).

## Run
```bash
bash demo.sh # fresh clone, one command: installs, runs the agent, prints the trace + artifact. Needs zero keys (mock mode).
```
Or serve the dashboard:
```bash
uv pip install -r requirements.txt
echo "GEMINI_API_KEY=***" > .env # any AI Studio key
cd src && python run.py # serves on :8000 (dual-stack: localhost, 127.0.0.1, ::1)
```
Dashboard: http://localhost:8000 - shows the live tool-call trace.

## Layout
```
agents4humans/
├── src/agent.py # Strands agent + EVM tool layer
├── src/app.py # FastAPI /run, /health, dashboard
├── src/index.html # terminal-style UI
└── requirements.txt # strands-agents, google-genai, fastapi...
```

Mock mode (no key) keeps `/run` deterministic for CI. MIT licensed.
