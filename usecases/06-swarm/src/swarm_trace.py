"""E1/E2: what a three-node swarm actually does, and what "done" means.

    --mode happy    researcher -> calculator -> writer, each handoff explicit
    --mode silent   the entry node answers without handing off

Both modes print the same trace fields so the two runs can be compared line by
line: the order nodes ran, how many model calls each made, how many tokens each
spent, the wall-clock intervals, and the exact text each node was handed.

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
Evidence: evidence/swarm-trace.txt and evidence/swarm-trace.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    LEDGER,
    NodeRecorder,
    first_input,
    node_agents,
    overlaps,
    read_brief_input,
    reset_ledger,
    save_draft,
    sum_tokens,
)

from strands.multiagent import Swarm  # noqa: E402

TASK = (
    "Produce a short brief. The input file holds the topic, the raw points and the "
    "per-node token counts. The brief must state the total token count and the cost in USD."
)

HAPPY = {
    "researcher": (
        "You are the researcher. Call read_brief_input, then state exactly three findings "
        "and quote the raw numbers. Then call handoff_to_agent with agent_name='calculator' "
        "and put the three findings and the token counts into the message argument. "
        "Do not finish your turn without handing off."
    ),
    "calculator": (
        "You are the calculator. The handoff message contains per-node token counts. "
        "Call sum_tokens with exactly those counts, then call handoff_to_agent with "
        "agent_name='writer' and put the total and the cost into the message argument. "
        "Do not finish your turn without handing off."
    ),
    "writer": (
        "You are the writer. Using the handoff message, write a brief of 100 words or fewer "
        "that states the total token count and the cost in USD. Call save_draft once with "
        "the finished brief. Do not hand off to anyone."
    ),
}

SILENT = {
    "researcher": (
        "You are the researcher. Summarize the topic of the input file in one sentence and "
        "finish. Do not call any tool."
    ),
    "calculator": "You are the calculator. Wait for a handoff.",
    "writer": "You are the writer. Wait for a handoff.",
}

ORDER = ["researcher", "calculator", "writer"]


async def run(mode: str) -> dict:
    reset_ledger()
    instructions = HAPPY if mode == "happy" else SILENT
    tools = [] if mode == "silent" else [read_brief_input, sum_tokens, save_draft]
    agents, counters = node_agents(instructions, tools=tools)

    recorder = NodeRecorder()
    nodes = [agents[name] for name in ORDER]
    swarm = Swarm(
        nodes=nodes,
        entry_point=agents["researcher"],
        max_handoffs=20,
        max_iterations=20,
        hooks=[recorder],
    )

    started = time.time()
    events: list[dict] = []
    result = None
    async for event in swarm.stream_async(TASK):
        events.append(event)
        if "result" in event:
            result = event["result"]
    elapsed = time.time() - started

    turns = recorder.turns
    handoffs = [e for e in events if e.get("type") == "multiagent_handoff"]
    cancels = [e for e in events if e.get("type") == "multiagent_node_cancel"]

    per_node = {}
    for name in ORDER:
        node_result = result.results.get(name) if result else None
        per_node[name] = {
            "model_calls": counters[name].calls,
            "total_tokens": (node_result.accumulated_usage.get("totalTokens") if node_result else 0),
            "input_tokens": (node_result.accumulated_usage.get("inputTokens") if node_result else 0),
            "output_tokens": (node_result.accumulated_usage.get("outputTokens") if node_result else 0),
            "status": (node_result.status.value if node_result else "never ran"),
            "wall_ms": (node_result.execution_time if node_result else 0),
        }

    return {
        "mode": mode,
        "status": result.status.value if result else "no result",
        "execution_count": result.execution_count if result else 0,
        "node_history": [str(n) for n in result.node_history] if result else [],
        "elapsed_s": round(elapsed, 3),
        "total_tokens": result.accumulated_usage.get("totalTokens") if result else 0,
        "per_node": per_node,
        "turns": [
            {k: (round(v - started, 3) if k in ("start", "stop") and isinstance(v, float) else v) for k, v in t.items()}
            for t in turns
        ],
        "overlaps": overlaps(turns),
        "handoffs": [
            {"from": h.get("from_node_ids"), "to": h.get("to_node_ids"), "message": (h.get("message") or "")[:200]}
            for h in handoffs
        ],
        "cancels": [{"node": c.get("node_id"), "message": c.get("message")} for c in cancels],
        "ledger": [
            {"tool": e["tool"], "words": e.get("words"), "total": e.get("total"), "text": e.get("text")}
            for e in LEDGER
        ],
        "first_input": {name: first_input(agents[name]) for name in ORDER if agents[name].messages},
        "final_message": (
            json.dumps(result.results.get(str(result.node_history[-1])).result.message.get("content"), default=str)[:900]
            if result and result.node_history
            else ""
        ),
    }


def report(trace: dict) -> None:
    print(f"=== mode={trace['mode']} ===")
    print(f"status            : {trace['status']}")
    print(f"execution_count   : {trace['execution_count']}")
    print(f"node_history      : {' -> '.join(trace['node_history']) or '(empty)'}")
    print(f"wall clock        : {trace['elapsed_s']}s")
    print(f"total tokens      : {trace['total_tokens']}")
    print()
    print("per node:")
    for name, row in trace["per_node"].items():
        print(
            f"  {name:<11} status={row['status']:<13} model_calls={row['model_calls']} "
            f"tokens={row['total_tokens']:<5} in={row['input_tokens']:<5} out={row['output_tokens']:<4} "
            f"wall={row['wall_ms']}ms"
        )
    print()
    print("node turn intervals (s from invocation start):")
    for turn in trace["turns"]:
        print(f"  {turn['node']:<11} start={turn.get('start')} stop={turn.get('stop')}")
    print(f"overlapping node turns: {trace['overlaps'] or 'none'}")
    print()
    print("handoffs:")
    for h in trace["handoffs"]:
        print(f"  {h['from']} -> {h['to']} | {h['message']}")
    print(f"cancels: {trace['cancels'] or 'none'}")
    print()
    print("tool ledger:")
    for row in trace["ledger"]:
        print(f"  {row}")
    print()
    for name, text in trace["first_input"].items():
        print(f"--- first input of {name} ---")
        print(text)
        print()
    print("--- final node message ---")
    print(trace["final_message"])
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["happy", "silent"], default="happy")
    parser.add_argument("--json", help="also write the raw trace here")
    args = parser.parse_args()

    trace = asyncio.run(run(args.mode))
    report(trace)
    if args.json:
        Path(args.json).write_text(json.dumps(trace, indent=2, default=str))


if __name__ == "__main__":
    main()
