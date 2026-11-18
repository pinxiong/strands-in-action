"""E2-E4: one real Bedrock call across the process boundary.

Modes:
  happy       remote tool succeeds; caller reads the reply and the on-disk receipt
  tool_raise  remote tool raises; caller sees what the protocol reports
  stream      same call, but record the raw A2A event sequence
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.agent.a2a_agent import A2AAgent  # noqa: E402

from common import (  # noqa: E402
    PORT,
    agent_result_summary,
    base,
    emit,
    receipts,
    reset_receipts,
    start_server,
    stop_server,
)

HAPPY = (
    "Call sum_tokens with [1180, 940, 1520]. Then call save_draft with a brief "
    "under 100 words containing the total and the cost, using key 'uc09-happy'. "
    "Report the receipt id verbatim."
)
TOOL_RAISE = "Call explode once and report its result verbatim."


def event_kind(event) -> str:  # noqa: ANN001
    if isinstance(event, tuple) and len(event) == 2:
        task, update = event
        return f"tuple(task.state={getattr(getattr(task, 'status', None), 'state', None)}, update={type(update).__name__})"
    return type(event).__name__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["happy", "tool_raise", "stream"], required=True)
    args = parser.parse_args()
    mode = args.mode
    port = PORT + {"happy": 2, "tool_raise": 3, "stream": 4}[mode]
    remote_mode = "tool_raise" if mode == "tool_raise" else "normal"
    key = "uc09-happy"
    prompt = TOOL_RAISE if mode == "tool_raise" else HAPPY

    reset_receipts()
    proc = start_server(remote_mode, port)
    started = time.time()
    try:
        client = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=90)
        record = base(mode, port)
        record.update({"prompt": prompt, "caller_key": key, "remote_pid": proc.pid})

        if mode == "stream":
            events: list[str] = []
            final = None

            async def collect() -> None:
                nonlocal final
                async for event in client.stream_async(prompt):
                    if "result" in event:
                        final = event["result"]
                    else:
                        inner = event.get("event")
                        events.append(event_kind(inner))

            asyncio.run(collect())
            record.update(
                {
                    "event_sequence": events,
                    "event_count": len(events),
                    "result": agent_result_summary(final) if final is not None else None,
                }
            )
        else:
            result = client(prompt)
            record.update({"result": agent_result_summary(result)})

        record["elapsed_s"] = round(time.time() - started, 2)
        record["on_disk_receipts"] = receipts()
        record["receipt_count"] = len(receipts())
        emit(f"a2a-{mode}", record)
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
