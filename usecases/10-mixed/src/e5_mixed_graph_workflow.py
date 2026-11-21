"""E5 — mixed B: a Graph top level with the vended Workflow tool embedded
inside one node as a deterministic sub-process.

The Workflow is NOT a graph node (it is a @tool function, not an AgentBase/
MultiAgentBase). A Graph node Agent calls run_brief_pipeline(), which runs the
three fixed workflow tasks. Records execution_order, the Graph's own usage,
the inner workflow's real usage, whether those inner tokens are visible to the
Graph, and a side-by-side delta against E1.

    ../../.venv/bin/python src/e5_mixed_graph_workflow.py
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent.graph import GraphBuilder

from common import (
    EVIDENCE, LAST_PIPELINE_RESULT, LEDGER, NODE_TURNS, TASK, TOOLS,
    NodeRecorder, base, emit, first_input, install_workflow_probes, node_agents,
    reset, run_brief_pipeline, task_model_calls_table, task_usage_table,
    usage_of, workflow_text,
)

INSTRUCTIONS = {
    "intake": (
        "You are the intake. Call read_brief_input exactly once and state the topic "
        "in one short sentence. Do not call any other tool."
    ),
    "wf_stage": (
        "You are the workflow stage. Call run_brief_pipeline with mode='happy' exactly "
        "once. Then report its result verbatim in one short sentence. "
        "Do not call any other tool."
    ),
    "review": (
        "You are the reviewer. State in one short sentence what the upstream stage "
        "reported. Do not call any tool."
    ),
}
ORDER = ["intake", "wf_stage", "review"]


def run() -> dict:
    reset()
    install_workflow_probes()

    agents, counters = node_agents(INSTRUCTIONS, TOOLS + [run_brief_pipeline])
    # Only wf_stage needs the pipeline tool, but sharing the tool list is harmless.

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("intake", "wf_stage")
    gb.add_edge("wf_stage", "review")
    gb.set_entry_point("intake")
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
    per_node = {}
    for name in ORDER:
        n = result.results.get(name)
        per_node[name] = {
            **(usage_of(n) if n else {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}),
            "status": n.status.value if n else "never ran",
            "wall_ms": n.execution_time if n else 0,
        }

    u = result.accumulated_usage
    graph_total = u.get("totalTokens", 0)
    inner_usage = task_usage_table()
    inner_total = sum(x["totalTokens"] for x in inner_usage.values())
    inner_calls = task_model_calls_table()
    pipeline = dict(LAST_PIPELINE_RESULT)
    inner_ret = pipeline.get("inner_return", {})
    inner_state = pipeline.get("inner_state", {})
    graph_results_keys = sorted(result.results.keys())
    inner_task_ids = ["researcher", "calculator", "writer"]
    graph_node_sum = sum(v["totalTokens"] for v in per_node.values())

    e1 = json.loads((EVIDENCE / "e1-graph-baseline.json").read_text())
    e1_tokens = e1["tokens_total"]["totalTokens"]

    record = {
        **base("E5 mixed B: Graph top level + node-embedded Workflow sub-process"),
        "workflow_is_graph_node": False,
        "workflow_embedded_via": "Graph node Agent calls run_brief_pipeline (a @tool wrapping workflow create+start)",
        "status": result.status.value,
        "execution_order": order,
        "graph_accumulated_usage": {
            "inputTokens": u.get("inputTokens", 0),
            "outputTokens": u.get("outputTokens", 0),
            "totalTokens": graph_total,
        },
        "inner_workflow_task_tokens": inner_usage,
        "inner_workflow_tokens_total": inner_total,
        "inner_workflow_model_calls": inner_calls,
        "inner_workflow_model_calls_total": sum(inner_calls.values()),
        "graph_results_keys": graph_results_keys,
        "inner_task_ids_present_as_graph_nodes": any(t in graph_results_keys for t in inner_task_ids),
        "graph_usage_equals_sum_of_its_own_nodes": graph_total == graph_node_sum,
        "inner_workflow_usage_metered_in_separate_agents": True,
        "inner_task_model_calls_in_graph_results": False,
        "inner_result_text_refed_into_graph_node": "wf_stage",
        "wf_stage_input_tokens": per_node["wf_stage"]["inputTokens"],
        "true_total_tokens_graph_plus_inner": graph_total + inner_total,
        "true_total_model_calls": sum(c.calls for c in counters.values()) + sum(inner_calls.values()),
        "graph_model_calls_total": sum(c.calls for c in counters.values()),
        "inner_start_text": workflow_text(inner_ret),
        "inner_workflow_status": inner_state.get("status"),
        "inner_task_status": {
            tid: v.get("status") for tid, v in (inner_state.get("task_results") or {}).items()
        },
        "wall_clock_s": round(wall, 3),
        "execution_time_ms": result.execution_time,
        "per_node": per_node,
        "node_turns": [
            {"node": t["node"], "duration_s": round(t.get("stop", t["start"]) - t["start"], 3)}
            for t in NODE_TURNS
        ],
        "first_inputs": {name: first_input(a) for name, a in agents.items()},
        "results_text": {name: str(n)[:320] for name, n in (result.results or {}).items()},
        "e1_control": {"tokens": e1_tokens, "model_calls": e1["model_calls_total"]},
        "graph_tokens_delta_vs_e1": graph_total - e1_tokens,
        "true_total_tokens_delta_vs_e1": (graph_total + inner_total) - e1_tokens,
        "ledger": list(LEDGER),
        "run_warnings": run_warnings,
    }
    emit("e5-mixed-graph-workflow", record)
    return record


if __name__ == "__main__":
    run()
