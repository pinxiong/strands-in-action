"""E5-E7: what the caller sees when the remote side fails, times out, or is retried.

Modes:
  agent_raise  an exception in the agent layer after the real Bedrock call
  timeout      remote write happens first, then the reply never arrives in time
  readback     sane response to that uncertainty: read back, then retry with the same key
"""

from __future__ import annotations

import argparse
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

SLOW = "Call slow with seconds=6 and key 'uc09-slow'. Report the tool result verbatim."
SAVE = (
    "Call sum_tokens with [1180, 940, 1520]. Then call save_draft with a brief "
    "under 100 words containing the total and the cost, using key 'uc09-happy'. "
    "Report the tool result verbatim."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["agent_raise", "timeout", "readback"], required=True)
    args = parser.parse_args()
    mode = args.mode
    port = PORT + {"agent_raise": 5, "timeout": 6, "readback": 7}[mode]
    remote_mode = {"agent_raise": "agent_raise", "timeout": "slow", "readback": "normal"}[mode]

    reset_receipts()
    proc = start_server(remote_mode, port)
    record = base(mode, port)
    record["remote_pid"] = proc.pid
    started = time.time()
    try:
        if mode == "timeout":
            client = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=2)
            record["client_timeout_s"] = 2
            record["prompt"] = SLOW
            try:
                result = client(SLOW)
                record["outcome"] = "returned"
                record["result"] = agent_result_summary(result)
            except Exception as exc:  # noqa: BLE001
                record["outcome"] = "exception"
                record["exception"] = f"{type(exc).__name__}: {exc}"
            record["receipts_at_exception"] = receipts()
            # The server is still running. Wait past the sleep so the remote write
            # can finish, then read back what actually landed on disk.
            time.sleep(7.5)
            record["receipts_after_wait"] = receipts()
            record["write_happened_without_reply"] = len(record["receipts_after_wait"]) > 0
            record["caller_could_know_from_result"] = record["outcome"] == "returned"
        elif mode == "agent_raise":
            client = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=90)
            record["prompt"] = SAVE
            try:
                result = client(SAVE)
                record["outcome"] = "returned"
                record["result"] = agent_result_summary(result)
            except Exception as exc:  # noqa: BLE001
                record["outcome"] = "exception"
                record["exception"] = f"{type(exc).__name__}: {exc}"
            record["receipts"] = receipts()
        else:
            client = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=90)
            record["prompt"] = SAVE
            calls = []
            for index in (1, 2):
                result = client(SAVE)
                calls.append(
                    {
                        "attempt": index,
                        "text": agent_result_summary(result)["text"],
                        "stop_reason": agent_result_summary(result)["stop_reason"],
                        "state": agent_result_summary(result)["state"],
                        "receipt_count_after": len(receipts()),
                    }
                )
            record["calls"] = calls
            record["receipts"] = receipts()
            record["receipt_count"] = len(receipts())
            record["same_key_wrote_once"] = len(receipts()) == 1

        record["elapsed_s"] = round(time.time() - started, 2)
        emit(f"a2a-{mode}", record)
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
