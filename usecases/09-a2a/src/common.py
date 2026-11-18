"""Shared bench for UC09: the UC08 brief fixture, now across a process boundary.

The remote agent runs in a separate OS process (src/remote_server.py). The caller
runs here. Nothing is shared except an HTTP port and a receipt file on disk.
That separation is the experiment: everything the caller can know about the
remote run has to arrive through the wire or through an explicit readback.

strands-agents 1.63.0, a2a-sdk 0.3.26, fastapi 0.163.2,
amazon.nova-pro-v1:0 in us-east-1, Python 3.11. Every number in the article
comes out of a run of these helpers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from strands import Agent, tool
from strands.hooks import HookProvider
from strands.hooks.events import AfterInvocationEvent, AfterModelCallEvent
from strands.models import BedrockModel

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data" / "brief-input.json"
EVIDENCE = ROOT / "evidence"
STATE = Path(os.environ.get("UC09_STATE_DIR") or "/tmp/uc09-a2a")
RECEIPTS = STATE / "receipts.jsonl"
REMOTE_USAGE = STATE / "remote-usage.jsonl"
MODEL_ID = "amazon.nova-pro-v1:0"
REGION = "us-east-1"
HOST = "127.0.0.1"
PORT = int(os.environ.get("UC09_PORT") or 9143)
BASE = f"http://{HOST}:{PORT}"
CARD_PATH = "/.well-known/agent-card.json"


def model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, region_name=REGION)


def fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def reset_receipts() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    RECEIPTS.write_text("", encoding="utf-8")
    REMOTE_USAGE.write_text("", encoding="utf-8")


def receipts() -> list[dict]:
    if not RECEIPTS.exists():
        return []
    return [json.loads(line) for line in RECEIPTS.read_text().splitlines() if line.strip()]


def remote_usage() -> list[dict]:
    if not REMOTE_USAGE.exists():
        return []
    return [json.loads(line) for line in REMOTE_USAGE.read_text().splitlines() if line.strip()]


class UsageRecorder(HookProvider):
    """Write the remote agent's real token usage to disk from inside the server process.

    The caller cannot see these numbers through A2A. This recorder proves they
    existed on the other side of the boundary.
    """

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001, ANN003
        registry.add_callback(AfterInvocationEvent, self.record)

    def record(self, event) -> None:  # noqa: ANN001
        agent = getattr(event, "agent", None)
        usage_blocks = []
        for message in getattr(agent, "messages", []) or []:
            for block in message.get("content", []) if isinstance(message, dict) else []:
                if isinstance(block, dict) and "usage" in block:
                    usage_blocks.append(block["usage"])
        metrics = getattr(agent, "event_loop_metrics", None)
        with REMOTE_USAGE.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "usage_blocks": usage_blocks,
                        "accumulated_usage": json.loads(
                            json.dumps(getattr(metrics, "accumulated_usage", None), default=str)
                        ),
                        "cycle_count": getattr(metrics, "cycle_count", None),
                    },
                    default=str,
                )
                + "\n"
            )


class CrashAfterModel(HookProvider):
    """Inject an agent-level exception after the real Bedrock call has happened."""

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001, ANN003
        registry.add_callback(AfterModelCallEvent, self.crash)

    def crash(self, event) -> None:  # noqa: ANN001
        raise RuntimeError("injected agent-level failure")


@tool
def sum_tokens(counts: list[int]) -> str:
    """Add the per-node token counts and price the total.

    Args:
        counts: Token counts, one per node.
    """
    data = fixture()
    total = sum(counts)
    cost = round(total / 1000 * data["price_per_1k_tokens"], 6)
    return json.dumps({"total": total, "cost_usd": cost})


@tool
def save_draft(text: str, key: str) -> str:
    """Save the finished brief under an idempotency key and return a receipt id.

    Args:
        text: The finished brief.
        key: Caller-supplied idempotency key for this operation.
    """
    existing = [r for r in receipts() if r["key"] == key]
    if existing:
        return json.dumps({"receipt": existing[0]["receipt"], "duplicate": True})
    receipt = f"R-{len(receipts()) + 1:03d}"
    with RECEIPTS.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "receipt": receipt,
                    "key": key,
                    "words": len(text.split()),
                    "text": text[:300],
                    "pid": os.getpid(),
                    "t": round(time.time(), 3),
                }
            )
            + "\n"
        )
    return json.dumps({"receipt": receipt, "duplicate": False})


@tool
def explode() -> str:
    """A tool that always fails. Used to inject a remote tool failure."""
    raise RuntimeError("injected tool failure")


@tool
def slow(seconds: int = 6, key: str = "uc09-slow") -> str:
    """Write a receipt first, then sleep before returning. Separates the write from the reply.

    Args:
        seconds: How long to block before returning.
        key: Caller-supplied idempotency key for this operation.
    """
    existing = [r for r in receipts() if r["key"] == key]
    if existing:
        receipt, duplicate = existing[0]["receipt"], True
    else:
        receipt, duplicate = f"R-{len(receipts()) + 1:03d}", False
        with RECEIPTS.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "receipt": receipt,
                        "key": key,
                        "pid": os.getpid(),
                        "t": round(time.time(), 3),
                        "phase": "written_before_reply",
                    }
                )
                + "\n"
            )
    time.sleep(seconds)
    return json.dumps({"receipt": receipt, "duplicate": duplicate})


def remote_agent(mode: str) -> Agent:
    """Build the remote agent. UC09_REMOTE_MODE decides which tools it gets."""
    tools = [sum_tokens, save_draft]
    hooks: list = [UsageRecorder()]
    if mode == "tool_raise":
        tools = [explode]
    elif mode == "slow":
        tools = [slow]
    elif mode == "agent_raise":
        hooks.append(CrashAfterModel())
    return Agent(
        model=model(),
        tools=tools,
        name="brief-writer",
        description="Adds per-node token counts and saves a short brief.",
        system_prompt=(
            "You execute one deterministic step. Call the named tool exactly once "
            "and report its result verbatim. Do not add commentary."
        ),
        hooks=hooks,
        callback_handler=None,
    )


def start_server(mode: str, port: int = PORT) -> subprocess.Popen:
    """Start the remote agent in a genuinely separate OS process."""
    STATE.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["UC09_REMOTE_MODE"] = mode
    env["UC09_PORT"] = str(port)
    env["UC09_STATE_DIR"] = str(STATE)
    log = STATE / f"server-{mode}.log"
    handle = log.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "src" / "remote_server.py")],
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    wait_ready(port, proc)
    return proc


def wait_ready(port: int, proc: subprocess.Popen, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    url = f"http://{HOST}:{port}{CARD_PATH}"
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"remote server exited early with {proc.returncode}; see {STATE}/server-*.log")
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:  # noqa: BLE001 - port not listening yet
            time.sleep(0.2)
    raise TimeoutError(f"remote agent card did not appear at {url} within {timeout}s")


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=6)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def fetch_card(port: int = PORT) -> dict:
    url = f"http://{HOST}:{port}{CARD_PATH}"
    with urllib.request.urlopen(url, timeout=5.0) as response:
        return json.loads(response.read().decode())


def agent_result_summary(result) -> dict:
    """Everything the caller can see after one A2A call, flattened."""
    message = result.message
    content = message.get("content", []) if isinstance(message, dict) else []
    return {
        "stop_reason": getattr(result, "stop_reason", None),
        "message_role": message.get("role") if isinstance(message, dict) else None,
        "content_blocks": [
            {k: v for k, v in block.items() if k in ("text", "type")} if isinstance(block, dict) else str(block)
            for block in content
        ],
        "text": "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict) and "text" in block
        ),
        "metrics": json.loads(json.dumps(getattr(result, "metrics", None), default=str)),
        "structured_output": getattr(result, "structured_output", None),
        "state": json.loads(json.dumps(getattr(result, "state", None), default=str)),
    }


def emit(name: str, record: dict) -> None:
    """Write one run's raw fields to evidence/ and echo a readable stdout line."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"{name}.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    lines: list[str] = []

    def walk(prefix: str, value) -> None:  # noqa: ANN001
        if isinstance(value, dict):
            for key, item in value.items():
                walk(f"{prefix}.{key}" if prefix else key, item)
        elif isinstance(value, list):
            lines.append(f"{prefix} = {json.dumps(value, default=str)}")
        else:
            lines.append(f"{prefix} = {value}")

    walk("", record)
    text = "\n".join(lines) + "\n"
    (EVIDENCE / f"{name}.txt").write_text(text, encoding="utf-8")
    print(text, end="")


def base(mode: str, port: int | None = None) -> dict:
    return {
        "verified_on": "2026-11-18",
        "sdk": "strands-agents 1.63.0 / a2a-sdk 0.3.26 / fastapi 0.163.2",
        "model": "amazon.nova-pro-v1:0 (us-east-1)",
        "python": "3.11",
        "mode": mode,
        "endpoint": f"http://{HOST}:{port if port is not None else PORT}",
        "caller_pid": os.getpid(),
    }
