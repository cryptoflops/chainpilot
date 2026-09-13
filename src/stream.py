"""
Streaming agent execution for the web console.

run_reasoning_stream(prompt) is an async generator yielding JSON-safe dicts:
  {"type":"tool_call","tool","args"}   the model asked for a tool
  {"type":"tool_result","tool","content"}  the tool answered (from the message history event)
  {"type":"delta","text"}              assistant text streaming
  {"type":"final","result","artifact"} run complete + written file if any
"""
import asyncio
import json
import os

from agent import api_key, build_agent

ARTIFACT = "triage_note.md"   # cwd-relative; agent's write_file lands here


async def run_reasoning_stream(prompt: str):
    if api_key == "mock-key":
        yield {"type": "delta", "text": f"[mock] Processed prompt: {prompt}"}
        yield {"type": "final", "result": "[mock] no GEMINI_API_KEY configured", "artifact": None}
        return

    agent = build_agent()
    queue: asyncio.Queue = asyncio.Queue()
    tool_names = {}   # toolUseId -> tool name (toolResult events carry no name)

    async def pump():
        try:
            async for ev in agent.stream_async(prompt):
                for msg in _classify(ev, tool_names):
                    await queue.put(msg)
        finally:
            await queue.put(None)

    task = asyncio.create_task(pump())
    final_text = ""
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            if msg["type"] == "delta":
                final_text += msg["text"]
            yield msg
    finally:
        task.cancel()

    artifact = None
    if os.path.exists(ARTIFACT):
        artifact = open(ARTIFACT, encoding="utf-8").read()
    yield {"type": "final", "result": final_text.strip() or "done", "artifact": artifact}


def _classify(ev, tool_names):
    """One Strands stream event -> 0..n console messages."""
    if not isinstance(ev, dict):
        return []
    out = []
    event = ev.get("event")
    if isinstance(event, dict):
        delta = event.get("contentBlockDelta")
        if isinstance(delta, dict):
            text = (delta.get("delta") or {}).get("text")
            if text:
                out.append({"type": "delta", "text": text})
    msg = ev.get("message")
    if isinstance(msg, dict):
        for c in msg.get("content") or []:
            if not isinstance(c, dict):
                continue
            tu = c.get("toolUse")
            if tu and msg.get("role") == "assistant":
                tool_names[tu.get("toolUseId")] = tu.get("name")
                out.append({"type": "tool_call", "tool": tu.get("name"),
                            "args": _short(tu.get("input"))})
            tr = c.get("toolResult")
            if tr and msg.get("role") == "user":
                body = "".join(p.get("text", "") for p in tr.get("content", []) if isinstance(p, dict))
                out.append({"type": "tool_result", "tool": tool_names.get(tr.get("toolUseId"), "tool"),
                            "content": body[:800] + ("…" if len(body) > 800 else "")})
    return out


def _short(args) -> str:
    s = json.dumps(args, default=str) if args is not None else ""
    return s[:300] + ("…" if len(s) > 300 else "")
