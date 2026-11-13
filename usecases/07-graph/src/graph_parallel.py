"""E4: nodes in the same batch really overlap in wall-clock time.

Usage (from usecases/07-graph):
    ../../.venv/bin/python src/graph_parallel.py --mode overlap

UC06 measured an empty overlap list for a Swarm. The same recorder on a Graph
should produce at least one intersecting pair. stdout is the raw evidence.

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
    NodeRecorder,
    emit,
    model,
    node_agents,
    overlaps,
    reset_ledger,
    slow_step,
    summarize,
)

PROMPTS = {
    "left": (
        "You are the left branch. Call slow_step with seconds=3 exactly once, "
        "then reply: LEFT DONE. Do not call any other tool."
    ),
    "right": (
        "You are the right branch. Call slow_step with seconds=3 exactly once, "
        "then reply: RIGHT DONE. Do not call any other tool."
    ),
}


def run() -> None:
    reset_ledger()
    agents, counters = node_agents(PROMPTS, [slow_step])
    recorder = NodeRecorder()

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.set_entry_point("left")
    gb.set_entry_point("right")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([recorder])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        result = graph("Two independent branches, one task.")

    record = summarize(
        result, agents, counters, recorder,
        extra={
            "mode": "overlap",
            "overlap_pairs": overlaps(recorder.turns),
            "warnings": [str(w.message) for w in caught],
        },
    )
    emit("graph-parallel-overlap", record)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["overlap"], default="overlap")
    ap.parse_args()
    run()
