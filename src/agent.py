"""
ChainPilot agent built on the AWS Strands Agents SDK.

A "Professional Agent" for EVM security researchers: it quietly handles the
repetitive on-chain recon steps (is this contract alive? what is its symbol?
what's the supply? write the triage note) and surfaces only the decoded
finding. All chain reads go through permissionless public JSON-RPC; the LLM
plans the calls, the runtime executes them.

Model: Gemini via Strands' GeminiModel (any GEMINI_API_KEY works: the SDK
is provider-agnostic, swap to Bedrock/Anthropic with one line).
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY", "mock-key")

MODEL_ID = os.environ.get("CHAINPILOT_MODEL", "gemini-flash-lite-latest")
EVM_RPCS = ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"]

SYSTEM_PROMPT = (
    "You are ChainPilot, an autonomous on-chain recon agent for security "
    "researchers. Given a contract address or a repetitive recon task: "
    "inspect it with eth_call, eth_get_code and eth_get_storage_at tools, decode results, and write a concise "
    "triage note with write_file. Use tools for every chain fact; never "
    "fabricate addresses, selectors, or values. If a call reverts or returns "
    "0x, say the address is likely not a contract."
)


def _eth_http(method: str, params: list) -> dict:
    """JSON-RPC with publicnode -> llamarpc fallback. Returns parsed response."""
    import requests
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for rpc in EVM_RPCS:
        try:
            j = requests.post(rpc, json=payload, timeout=10).json()
            if "result" in j or "error" in j:
                return {"rpc": rpc, **j}
        except Exception:
            continue
    return {"error": "all RPCs unreachable"}


def build_agent():
    """Wire a Strands Agent with the on-chain tool set."""
    from strands import Agent, tool
    from strands.models.gemini import GeminiModel

    @tool
    def eth_call(to: str, data: str) -> str:
        """eth_call on Ethereum mainnet via public JSON-RPC.
        to: 0x contract address; data: 0x selector + ABI-encoded args."""
        return json.dumps(_eth_http("eth_call", [{"to": to, "data": data}, "latest"]))

    @tool
    def eth_get_code(address: str) -> str:
        """Return the bytecode of an address ('0x' means EOA/empty).
        Use first to check a contract is actually deployed."""
        r = _eth_http("eth_getCode", [address, "latest"])
        code = r.get("result", "0x")
        return json.dumps({"rpc": r.get("rpc"), "size": max(0, (len(code) - 2) // 2), "is_contract": len(code) > 2})

    @tool
    def eth_get_storage_at(address: str, slot: str) -> str:
        """Read one storage slot of a contract via public JSON-RPC.
        address: 0x contract; slot: hex slot number or 32-byte slot key."""
        r = _eth_http("eth_getStorageAt", [address, slot, "latest"])
        return json.dumps({"rpc": r.get("rpc"), "result": r.get("result") or r.get("error")})

    @tool
    def read_file(path: str) -> str:
        """Read a local file (max 4 KB)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:4096]
        except Exception as e:
            return f"Error reading file: {e}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write a file (triage notes, reports)."""
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    model = GeminiModel(api_key=api_key, model_id=MODEL_ID)
    return Agent(model=model, tools=[eth_call, eth_get_code, eth_get_storage_at, read_file, write_file],
                 system_prompt=SYSTEM_PROMPT)


def run_reasoning_loop(prompt: str) -> dict:
    """Same interface the FastAPI app and dashboard expect:
    returns {'steps': [{role, content}], 'result': str}."""
    if api_key == "mock-key":
        # deterministic stub artifact so demo.sh works keyless (out-of-box proof)
        with open("triage_note.md", "w", encoding="utf-8") as f:
            f.write("# Triage Note (MOCK MODE)\n\n"
                    "No GEMINI_API_KEY found: this artifact is a deterministic stub.\n"
                    "With a key, the agent verifies the contract via eth_get_code, reads\n"
                    "name()/totalSupply() via eth_call, and writes the decoded findings.\n")
        return {
            "steps": [{"role": "system", "content": "Running in mock mode (no GEMINI_API_KEY)."}],
            "result": f"[mock] Processed prompt: {prompt}",
        }

    agent = build_agent()
    result = agent(prompt)

    steps = []
    for msg in agent.messages:
        role = msg.get("role")
        for c in msg.get("content") or []:
            if "text" in c and c["text"]:
                steps.append({"role": "assistant" if role == "agent" else role, "content": c["text"]})
            if "toolUse" in c:
                steps.append({"role": "tool_call",
                              "content": json.dumps({"tool": c["toolUse"].get("name"),
                                                     "args": c["toolUse"].get("input")})})
            if "toolResult" in c:
                body = "".join(p.get("text", "") for p in c["toolResult"].get("content", []))
                steps.append({"role": "tool_result", "content": body[:2048]})

    final = str(result) or next((s["content"] for s in reversed(steps)
                                 if s["role"] == "assistant"), "[agent] No final answer.")
    return {"steps": steps, "result": final}
