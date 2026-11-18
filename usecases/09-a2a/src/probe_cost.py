"""E8: the cost ledger does not survive the process boundary.

Runs the same brief locally (one process, real Bedrock), then through A2A
(two processes, real Bedrock on the far side). Records token usage from all
three places: the local agent, the remote agent inside the server, and the
caller's AgentResult. Also scans the SDK converter for usage/token/metric hits.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands import Agent  # noqa: E402
from strands.agent.a2a_agent import A2AAgent  # noqa: E402

from common import (  # noqa: E402
    PORT,
    agent_result_summary,
    base,
    emit,
    model,
    receipts,
    remote_usage,
    reset_receipts,
    start_server,
    stop_server,
    sum_tokens,
    save_draft,
)

PROMPT = (
    "Call sum_tokens with [1180, 940, 1520]. Then call save_draft with a brief "
    "under 100 words containing the total and the cost, using key 'uc09-cost'. "
    "Report the receipt id verbatim."
)


def usage_of(result) -> dict:  # noqa: ANN001
    metrics = getattr(result, "metrics", None)
    return {
        "accumulated_usage": json.loads(
            json.dumps(getattr(metrics, "accumulated_usage", None), default=str)
        ),
        "cycle_count": getattr(metrics, "cycle_count", None),
        "tool_metrics": json.loads(json.dumps(getattr(metrics, "tool_metrics", None), default=str)),
    }


def main() -> None:
    port = PORT + 8
    reset_receipts()
    record = base("cost", port)

    # Control: the same task in this process, with the same model and tools.
    local = Agent(
        model=model(),
        tools=[sum_tokens, save_draft],
        system_prompt="Call the named tools once and report the result verbatim.",
        callback_handler=None,
    )
    local_result = local(PROMPT)
    record["local_usage"] = usage_of(local_result)
    record["local_stop_reason"] = getattr(local_result, "stop_reason", None)
    record["local_receipts"] = receipts()

    # Clear the control's write so the remote receipt is unambiguously the
    # server process's own side effect, not a deduplicated local one.
    reset_receipts()

    # Across the boundary: real Bedrock in the server process.
    proc = start_server("normal", port)
    try:
        client = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=90)
        remote_result = client(PROMPT)
        record["remote_pid"] = proc.pid
        record["caller_usage"] = usage_of(remote_result)
        record["caller_result"] = agent_result_summary(remote_result)
        record["remote_side_usage"] = remote_usage()
    finally:
        stop_server(proc)

    # Static check: does the A2A conversion layer ever mention usage or tokens?
    import strands.multiagent.a2a.executor as executor_module

    source = Path(executor_module.__file__).read_text(encoding="utf-8")
    terms = ["usage", "token", "metric"]
    record["converter_source"] = str(executor_module.__file__)
    record["converter_term_hits"] = {
        term: source.lower().count(term) for term in terms
    }
    record["converter_total_hits"] = sum(record["converter_term_hits"].values())
    record["receipts"] = [
        {k: v for k, v in r.items() if k in ("receipt", "key", "pid")} for r in receipts()
    ]
    emit("a2a-cost", record)


if __name__ == "__main__":
    main()
