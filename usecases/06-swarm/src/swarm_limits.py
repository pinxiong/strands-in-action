"""E3: the two limits that look like two knobs and behave like one.

    --cap iterations   max_iterations=3, max_handoffs=20
    --cap handoffs     max_handoffs=3, max_iterations=20

Two agents hand the task back and forth forever. Whichever name you pick, the
run stops at the same place, because both limits are compared against the same
counter: len(node_history).

The stop reason only exists at DEBUG level, so the swarm's own log line is
captured and printed. That line is the evidence, not my reading of the source.

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
Evidence: evidence/swarm-limits.txt.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import model  # noqa: E402

from strands import Agent  # noqa: E402
from strands.multiagent import Swarm  # noqa: E402

PROMPT = (
    "You are {name}. Your only job is to pass the task to {other}. Call handoff_to_agent "
    "with agent_name='{other}' and message='your turn'. Never answer with text only, "
    "always hand off."
)

TASK = "Pass this task back and forth. Nobody should ever finish it."


def build() -> tuple[Swarm, io.StringIO]:
    alpha = Agent(model=model(), system_prompt=PROMPT.format(name="alpha", other="beta"), name="alpha",
                  description="passes the task to beta", callback_handler=None)
    beta = Agent(model=model(), system_prompt=PROMPT.format(name="beta", other="alpha"), name="beta",
                 description="passes the task to alpha", callback_handler=None)
    return alpha, beta


async def run(cap: str) -> dict:
    alpha, beta = build()
    if cap == "iterations":
        kwargs = {"max_iterations": 3, "max_handoffs": 20}
    else:
        kwargs = {"max_handoffs": 3, "max_iterations": 20}
    swarm = Swarm(nodes=[alpha, beta], entry_point=alpha, **kwargs)

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    logger = logging.getLogger("strands.multiagent.swarm")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    result = None
    try:
        async for event in swarm.stream_async(TASK):
            if "result" in event:
                result = event["result"]
    finally:
        logger.removeHandler(handler)

    log = buf.getvalue()
    reasons = [line.strip() for line in log.splitlines() if "reason=" in line and "stopping execution" in line]
    return {
        "cap": cap,
        "kwargs": kwargs,
        "status": result.status.value if result else "no result",
        "execution_count": result.execution_count if result else 0,
        "node_history": [str(n) for n in result.node_history] if result else [],
        "total_tokens": result.accumulated_usage.get("totalTokens") if result else 0,
        "stop_reason_lines": reasons[-3:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", choices=["iterations", "handoffs"], required=True)
    parser.add_argument("--json")
    args = parser.parse_args()

    out = asyncio.run(run(args.cap))
    print(json.dumps(out, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
