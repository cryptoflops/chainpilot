"""
FastAPI application exposing the /run endpoint that triggers the agent
reasoning loop and returns structured JSON with the reasoning trace.
"""

import os
import json
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a local .env file

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agent import run_reasoning_loop

app = FastAPI(
    title="ChainPilot: Professional Agent",
    description="Autonomous EVM recon agent built on the AWS Strands Agents SDK",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The task instruction for the agent.")


class StepEntry(BaseModel):
    role: str
    content: str


class RunResponse(BaseModel):
    status: str
    result: str
    steps: list[StepEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serve the single-page HTML dashboard."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    html_path = os.path.join(current_dir, "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"<h3>Failed to load dashboard: {e}</h3>", status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
async def run_agent(req: RunRequest):
    """Execute the agent reasoning loop for a given prompt."""
    try:
        output = run_reasoning_loop(req.prompt)
        return RunResponse(
            status="success",
            result=output["result"],
            steps=[StepEntry(**s) for s in output["steps"]],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")


@app.post("/run/stream")
async def run_agent_stream(req: RunRequest):
    """Server-sent events: live tool calls, results, and text as the agent works."""
    from fastapi.responses import StreamingResponse
    from stream import run_reasoning_stream

    async def sse():
        try:
            async for msg in run_reasoning_stream(req.prompt):
                yield f"data: {json.dumps(msg, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'final', 'result': f'error: {e}', 'artifact': None})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
