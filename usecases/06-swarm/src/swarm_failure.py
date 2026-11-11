"""E4/E5/E6: three ways a node stops being in charge.

    --mode toolerror a node asks for a handoff, then its tool throws
    --mode timeout   a node asks for a handoff, then blocks past node_timeout
    --mode cancel    a BeforeNodeCallEvent hook cancels the next node
    --mode session   a node agent is given a session manager

Each mode answers one question the article makes a claim about:
  toolerror  does a broken tool stop the node, or only that one call?
  timeout    is a handoff requested by a node that then dies still honoured?
  cancel   where can a human stand in front of a node at all?
  session  can one node keep its own conversation across invocations?

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
Evidence: evidence/swarm-failure.txt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    LEDGER,
    Canceller,
    ToolOrder,
    explode,
    model,
    node_agents,
    read_brief_input,
    reset_ledger,
    save_draft,
    slow_step,
    sum_tokens,
)

from strands import Agent  # noqa: E402
from strands.multiagent import Swarm  # noqa: E402
from strands.session import FileSessionManager  # noqa: E402

TASK = "Produce the brief from the input file."

TIMEOUT_PROMPT = (
    "You are the calculator. In this turn do exactly two tool calls, in this order: "
    "first handoff_to_agent with agent_name='writer' and message='write the brief', "
    "then slow_step with seconds=10. Never call another tool."
)

RAISE_PROMPT = (
    "You are the calculator. In this turn do exactly two tool calls, in this order: "
    "first handoff_to_agent with agent_name='writer' and message='write the brief', "
    "then explode. Never write the brief yourself and never call another tool."
)

HANDOFF_THEN_WAIT = {
    "researcher": (
        "You are the researcher. Call read_brief_input, state three findings, then call "
        "handoff_to_agent with agent_name='calculator'. Do not finish without handing off."
    ),
    "calculator": "You are the calculator. Call sum_tokens, then hand off to writer.",
    "writer": "You are the writer. Call save_draft once with a 90-word brief.",
}


async def collect(swarm: Swarm, task: str) -> tuple[list[dict], object, float]:
    started = time.time()
    events: list[dict] = []
    result = None
    async for event in swarm.stream_async(task):
        events.append(event)
        if "result" in event:
            result = event["result"]
    return events, result, time.time() - started


async def mode_raise(mode: str) -> dict:
    reset_ledger()
    order = ToolOrder()
    second = explode if mode == "toolerror" else slow_step
    prompt = RAISE_PROMPT if mode == "toolerror" else TIMEOUT_PROMPT
    tools = [explode] if mode == "toolerror" else [slow_step]
    calculator = Agent(
        model=model(),
        tools=tools,
        system_prompt=prompt,
        name="calculator",
        description="checks numbers",
        hooks=[order],
        callback_handler=None,
    )
    writer = Agent(
        model=model(),
        tools=[save_draft],
        system_prompt=HANDOFF_THEN_WAIT["writer"],
        name="writer",
        description="writes the brief",
        callback_handler=None,
    )
    swarm = Swarm(
        nodes=[calculator, writer],
        entry_point=calculator,
        max_handoffs=4,
        max_iterations=4,
        node_timeout=(90 if mode == "toolerror" else 4),
    )
    events, result, elapsed = await collect(swarm, TASK)

    handoff_in_state = swarm.state.handoff_node
    return {
        "mode": mode,
        "status": result.status.value if result else "no result",
        "execution_count": result.execution_count if result else 0,
        "node_history": [str(n) for n in result.node_history] if result else [],
        "handoff_node_after_run": str(handoff_in_state) if handoff_in_state else None,
        "writer_status": (
            result.results["writer"].status.value if result and "writer" in result.results else "never ran"
        ),
        "calculator_tool_order": order.order,
        "tool_ledger": [{"tool": e["tool"]} for e in LEDGER],
        "elapsed_s": round(elapsed, 3),
        "total_tokens": result.accumulated_usage.get("totalTokens") if result else 0,
    }


async def mode_cancel() -> dict:
    reset_ledger()
    agents, _ = node_agents(HANDOFF_THEN_WAIT, tools=[read_brief_input, sum_tokens, save_draft])
    canceller = Canceller("calculator", "a human stopped this node")
    swarm = Swarm(
        nodes=[agents["researcher"], agents["calculator"], agents["writer"]],
        entry_point=agents["researcher"],
        max_handoffs=6,
        max_iterations=6,
        hooks=[canceller],
    )
    events, result, elapsed = await collect(swarm, TASK)
    cancels = [{"node": e.get("node_id"), "message": e.get("message")} for e in events
               if e.get("type") == "multiagent_node_cancel"]
    return {
        "mode": "cancel",
        "status": result.status.value if result else "no result",
        "execution_count": result.execution_count if result else 0,
        "node_history": [str(n) for n in result.node_history] if result else [],
        "cancel_events": cancels,
        "tool_ledger": [{"tool": e["tool"]} for e in LEDGER],
        "elapsed_s": round(elapsed, 3),
        "total_tokens": result.accumulated_usage.get("totalTokens") if result else 0,
    }


def mode_session() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        session = FileSessionManager(session_id="node-with-own-session", storage_dir=tmp)
        agent = Agent(model=model(), system_prompt="hi", name="solo", session_manager=session)
        try:
            Swarm(nodes=[agent], entry_point=agent)
            outcome = "constructed without error"
        except Exception as exc:  # noqa: BLE001
            outcome = f"{type(exc).__name__}: {exc}"
    return {"mode": "session", "outcome": outcome}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["toolerror", "timeout", "cancel", "session"], required=True)
    parser.add_argument("--json")
    args = parser.parse_args()

    if args.mode == "toolerror":
        out = asyncio.run(mode_raise("toolerror"))
    elif args.mode == "timeout":
        out = asyncio.run(mode_raise("timeout"))
    elif args.mode == "cancel":
        out = asyncio.run(mode_cancel())
    else:
        out = mode_session()

    print(json.dumps(out, indent=2, default=str))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
