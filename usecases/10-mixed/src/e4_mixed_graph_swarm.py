"""E4 — mixed A: a Graph top level with a Swarm as one node (research layer).

The Swarm is passed directly to GraphBuilder.add_node. Graph nodes do the
accounting and the writing. Records whether the Swarm really executes as a
node, execution_order, total usage (including nested Swarm tokens) and a
side-by-side delta against E1.

    ../../.venv/bin/python src/e4_mixed_graph_swarm.py
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent import Swarm
from strands.multiagent.base import MultiAgentBase
from strands.multiagent.graph import GraphBuilder

from common import (
    EVIDENCE, LEDGER, NODE_TURNS, ROLE_INSTRUCTIONS, TASK, TOOLS,
    NodeRecorder, base, emit, first_input, node_agents, reset, usage_of,
)

SWARM_RESEARCH_INSTRUCTIONS = {
    "scout": (
        "You are the scout. Call read_brief_input exactly once, then state exactly three "
        "findings and quote the raw numbers. Then call handoff_to_agent with "
        "agent_name='analyst', put the findings in the message argument, and pass "
        "context={'raw_counts': [1180, 940, 1520], 'points_found': 3}. "
        "Do not finish your turn without handing off."
    ),
    "analyst": (
        "You are the analyst. Using the handoff message and the shared context, "
        "summarise the three research findings in ONE short sentence that quotes the "
        "raw token counts. Do not call any tool. Do not hand off to anyone."
    ),
}
SWARM_ORDER = ["scout", "analyst"]
GRAPH_ORDER = ["swarm_research", "calculator", "writer"]


def run() -> dict:
    reset()
    graph_agents, graph_counters = node_agents(
        {k: ROLE_INSTRUCTIONS[k] for k in ("calculator", "writer")}, TOOLS
    )
    swarm_agents, swarm_counters = node_agents(SWARM_RESEARCH_INSTRUCTIONS, TOOLS)

    swarm = Swarm(
        nodes=[swarm_agents[n] for n in SWARM_ORDER],
        entry_point=swarm_agents["scout"],
        max_handoffs=8,
        max_iterations=8,
    )

    gb = GraphBuilder()
    add_accepted = False
    try:
        gb.add_node(swarm, "swarm_research")
        add_accepted = True
    except Exception as exc:  # noqa: BLE001
        add_error = f"{type(exc).__name__}: {exc}"
    else:
        add_error = ""

    gb.add_node(graph_agents["calculator"], "calculator")
    gb.add_node(graph_agents["writer"], "writer")
    gb.add_edge("swarm_research", "calculator")
    gb.add_edge("calculator", "writer")
    gb.set_entry_point("swarm_research")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([NodeRecorder()])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        started = time.time()
        result = graph(TASK)
        wall = time.time() - started
        run_warnings = [str(w.message) for w in caught]

    order = [n.node_id for n in result.execution_order]
    nr = result.results.get("swarm_research")
    inner = getattr(nr, "result", None) if nr else None
    nested_text = str(nr)[:400] if nr else ""
    nr_dict = json.dumps(nr.to_dict(), default=str) if nr else ""

    per_node = {}
    for name in GRAPH_ORDER:
        n = result.results.get(name)
        per_node[name] = {
            **(usage_of(n) if n else {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}),
            "status": n.status.value if n else "never ran",
            "wall_ms": n.execution_time if n else 0,
        }

    u = result.accumulated_usage
    total = u.get("totalTokens", 0)
    inner_usage = dict(inner.accumulated_usage) if inner is not None else {}
    nested_usage = per_node["swarm_research"]["totalTokens"]
    all_calls = {**{k: c.calls for k, c in graph_counters.items()},
                 **{k: c.calls for k, c in swarm_counters.items()}}
    model_calls_total = sum(all_calls.values())

    e1 = json.loads((EVIDENCE / "e1-graph-baseline.json").read_text())
    e1_tokens = e1["tokens_total"]["totalTokens"]
    e1_calls = e1["model_calls_total"]

    record = {
        **base("E4 mixed A: Graph top level + Swarm research node"),
        "swarm_is_multiagentbase": isinstance(swarm, MultiAgentBase),
        "graphbuilder_add_node_accepted": add_accepted,
        "graphbuilder_add_node_error": add_error,
        "nested_node_id": "swarm_research",
        "status": result.status.value,
        "execution_order": order,
        "nested_node_executed": "swarm_research" in order,
        "nested_node_result_python_type": type(inner).__name__ if inner else None,
        "nested_node_result_text": nested_text,
        "inner_swarm_status": inner.status.value if inner else None,
        "inner_swarm_handoff_order": [str(n) for n in getattr(inner, "node_history", [])],
        "inner_swarm_is_serial_handoff": len(getattr(inner, "node_history", [])) > 1,
        "inner_swarm_shared_context_keys": {
            k: sorted(v) for k, v in swarm.shared_context.context.items()
        },
        "swarm_object_has_shared_context": bool(swarm.shared_context.context),
        "graph_state_results_exposes_shared_context": "shared_context" in nr_dict,
        "inner_swarm_accumulated_usage": inner_usage,
        "nested_node_usage_equals_inner_swarm_usage": (
            nested_usage == inner_usage.get("totalTokens", -1)
        ),
        "tokens_total": {
            "inputTokens": u.get("inputTokens", 0),
            "outputTokens": u.get("outputTokens", 0),
            "totalTokens": total,
        },
        "graph_usage_includes_nested_swarm_tokens": (
            nested_usage == inner_usage.get("totalTokens", -1)
            and total == sum(v["totalTokens"] for v in per_node.values())
        ),
        "model_calls_total": model_calls_total,
        "model_calls_by_agent": all_calls,
        "wall_clock_s": round(wall, 3),
        "execution_time_ms": result.execution_time,
        "per_node": per_node,
        "node_turns": [
            {"node": t["node"], "duration_s": round(t.get("stop", t["start"]) - t["start"], 3)}
            for t in NODE_TURNS
        ],
        "first_inputs": {name: first_input(a) for name, a in {**graph_agents, **swarm_agents}.items()},
        "results_text": {name: str(n)[:320] for name, n in (result.results or {}).items()},
        "e1_control": {
            "tokens": e1_tokens,
            "model_calls": e1_calls,
            "wall_clock_s": e1["wall_clock_s"],
        },
        "tokens_delta_vs_e1": total - e1_tokens,
        "model_calls_delta_vs_e1": model_calls_total - e1_calls,
        "ledger": list(LEDGER),
        "run_warnings": run_warnings,
    }
    emit("e4-mixed-graph-swarm", record)
    return record


if __name__ == "__main__":
    run()
