"""E3: a join with two parents is an OR, not a barrier.

Usage (from usecases/07-graph):
    ../../.venv/bin/python src/graph_fanin.py --mode or

Shape (this shape is what makes the test decisive):

    A (fast, batch 1) ---> B (slow, batch 2)
      \                     /
       +----------------> join

A is the only entry point. After batch 1 finishes, both B and join are ready,
because join has ONE incoming edge from A that is already satisfied. If join
were a barrier it would wait for B to finish. Instead it starts in the same
batch as B, overlaps B in wall-clock time, and receives only A's text (B is
not in completed_nodes yet, so _build_node_input cannot include it).

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strands.multiagent.graph import GraphBuilder

from src.common import (
    ModelCalls,
    NodeRecorder,
    emit,
    model,
    node_agents,
    overlaps,
    reset_ledger,
    slow_step,
    summarize,
)
from strands import Agent

PROMPTS = {
    "A": (
        "You are node A. Do not call any tool. "
        "Reply with exactly: A RESULT."
    ),
    "B": (
        "You are node B. Call slow_step with seconds=4 exactly once, "
        "then reply: B RESULT. Do not call any other tool."
    ),
    "join": (
        "You are the join. Do not call any tool. "
        "Reply with exactly: JOIN RESULT."
    ),
}


def always(state, *, invocation_state, **kwargs) -> bool:
    return True


def run() -> None:
    reset_ledger()
    agents, counters = node_agents({"B": PROMPTS["B"]}, [slow_step])
    for name in ("A", "join"):
        c = ModelCalls(name)
        agents[name] = Agent(
            model=model(), system_prompt=PROMPTS[name], name=name,
            callback_handler=None, hooks=[c],
        )
        counters[name] = c

    recorder = NodeRecorder()
    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("A", "B")
    gb.add_edge("A", "join", condition=always)
    gb.add_edge("B", "join", condition=always)
    gb.set_entry_point("A")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([recorder])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        result = graph("One task, one fast parent, one slow parent, one join.")

    turns = [
        {"node": t["node"], "start": round(t["start"], 3),
         "stop": round(t.get("stop", t["start"]), 3)}
        for t in recorder.turns
    ]
    b_turn = next((t for t in turns if t["node"] == "B"), None)
    join_turn = next((t for t in turns if t["node"] == "join"), None)
    join_input = ""
    from_blocks: list[str] = []
    if agents["join"].messages:
        blocks = agents["join"].messages[0].get("content", [])
        join_input = "\n".join(
            b.get("text", "") for b in blocks if isinstance(b, dict)
        )
        from_blocks = [
            line for line in join_input.splitlines() if line.startswith("From ")
        ]

    record = summarize(
        result, agents, counters, recorder,
        extra={
            "mode": "or",
            "shape": "A -> B ; A -> join ; B -> join",
            "turns": turns,
            "overlap_pairs": overlaps(recorder.turns),
            "join_started_before_B_stopped": (
                bool(b_turn and join_turn and join_turn["start"] < b_turn["stop"])
            ),
            "from_blocks_in_join_input": from_blocks,
            "join_input": join_input[:600],
            "warnings": [str(w.message) for w in caught],
        },
    )
    emit("graph-fanin-or", record)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["or"], default="or")
    ap.parse_args()
    run()
