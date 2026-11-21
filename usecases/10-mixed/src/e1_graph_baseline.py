"""E1 — pure Graph baseline: three nodes, serial (researcher -> calculator -> writer).

Records execution_order, real per-node token usage, total usage, model calls and
wall-clock time. No mixing: the control every mixed run is compared against.

    ../../.venv/bin/python src/e1_graph_baseline.py
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent.graph import GraphBuilder

from common import (
    LEDGER, NODE_TURNS, ROLE_INSTRUCTIONS, TASK, TOOLS,
    NodeRecorder, base, emit, first_input, node_agents, reset, usage_of,
)

ORDER = ["researcher", "calculator", "writer"]


def run() -> dict:
    reset()
    agents, counters = node_agents(ROLE_INSTRUCTIONS, TOOLS)
    recorder = NodeRecorder()

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("researcher", "calculator")
    gb.add_edge("calculator", "writer")
    gb.set_entry_point("researcher")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([recorder])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        build_warnings = [str(w.message) for w in caught]
        started = time.time()
        result = graph(TASK)
        wall = time.time() - started
        run_warnings = [str(w.message) for w in caught]

    per_node = {}
    for name in ORDER:
        nr = result.results.get(name)
        per_node[name] = {
            "model_calls": counters[name].calls,
            **(usage_of(nr) if nr else {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}),
            "status": nr.status.value if nr else "never ran",
            "wall_ms": nr.execution_time if nr else 0,
        }

    u = result.accumulated_usage
    record = {
        **base("E1 pure Graph baseline (control)"),
        "status": result.status.value,
        "execution_order": [n.node_id for n in result.execution_order],
        "total_nodes": result.total_nodes,
        "completed_nodes": result.completed_nodes,
        "failed_nodes": result.failed_nodes,
        "execution_time_ms": result.execution_time,
        "wall_clock_s": round(wall, 3),
        "tokens_total": {
            "inputTokens": u.get("inputTokens", 0),
            "outputTokens": u.get("outputTokens", 0),
            "totalTokens": u.get("totalTokens", 0),
        },
        "model_calls_total": sum(c.calls for c in counters.values()),
        "per_node": per_node,
        "node_turns": [
            {"node": t["node"], "duration_s": round(t.get("stop", t["start"]) - t["start"], 3)}
            for t in NODE_TURNS
        ],
        "first_inputs": {name: first_input(a) for name, a in agents.items()},
        "results_text": {name: str(nr)[:320] for name, nr in (result.results or {}).items()},
        "ledger": list(LEDGER),
        "build_warnings": build_warnings,
        "run_warnings": run_warnings,
    }
    emit("e1-graph-baseline", record)
    return record


if __name__ == "__main__":
    run()
