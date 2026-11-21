"""E6 — context bridge: enumerate exactly which fields cross the three
paradigm boundaries, measured on live objects from one real composed run.

One Graph holds all three paradigms:
    swarm_src (Swarm)  ->  wf_mid (Agent embedding the Workflow tool)  ->  sink (Agent)

Sentinels are written into each paradigm's private structured channel:
    Swarm.shared_context.context   -> "SWARM-7Q2"
    Workflow persisted task_results -> per-task status/result/metrics
    Graph.state.results             -> NodeResult(status, usage, ...)

"reaches / loses" is decided by STRUCTURED reachability (hasattr on the real
Graph-held objects and a live condition predicate), not by prose. Plain-string
leakage through tool-call / tool-result text is recorded separately and
honestly under *_in_graph_text, because a string appearing in a message is not
a field the orchestrator can branch on.

    ../../.venv/bin/python src/e6_context_bridge.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent import Swarm
from strands.multiagent.graph import GraphBuilder

from common import (
    LAST_PIPELINE_RESULT, LEDGER, TASK, TOOLS,
    base, emit, first_input, install_workflow_probes, node_agents, reset,
    run_brief_pipeline, workflow_text,
)

SENTINEL = "SWARM-7Q2"
PREDICATE_LOG: list[dict] = []

SWARM_INSTRUCTIONS = {
    "scout": (
        "You are the scout. Call read_brief_input exactly once. Then call "
        "handoff_to_agent with agent_name='analyst', put the three points in the "
        "message argument, and pass context={'sentinel': 'SWARM-7Q2', "
        "'raw_counts': [1180, 940, 1520]}. Do not finish without handing off."
    ),
    "analyst": (
        "You are the analyst. Summarise the three research findings in ONE short "
        "sentence. Do NOT mention the sentinel value. Do not call any tool. "
        "Do not hand off to anyone."
    ),
}
PIPELINE_INSTRUCTIONS = {
    "wf_mid": (
        "You are the workflow stage. Call run_brief_pipeline with mode='happy' exactly "
        "once. Then report its result in one short sentence. Do not call any other tool."
    ),
    "sink": (
        "You are the sink. State in one short sentence what the upstream stages "
        "reported. Do not call any tool."
    ),
}


def bridge_predicate(state, *, invocation_state, **kwargs) -> bool:
    """A real condition predicate: records which structured fields it can read
    from GraphState.results at routing time (and still returns True)."""
    seen = {}
    for nid, nr in (state.results or {}).items():
        seen[nid] = {
            "node_result_fields": sorted(nr.to_dict().keys()),
            "status": nr.status.value,
            "accumulated_usage_totalTokens": nr.accumulated_usage.get("totalTokens"),
            "execution_time": nr.execution_time,
        }
    PREDICATE_LOG.append({"seen_node_results": seen})
    return True


def run() -> dict:
    reset()
    PREDICATE_LOG.clear()
    install_workflow_probes()

    swarm_agents, _ = node_agents(SWARM_INSTRUCTIONS, TOOLS)
    graph_agents, _ = node_agents(PIPELINE_INSTRUCTIONS, TOOLS + [run_brief_pipeline])
    swarm = Swarm(
        nodes=[swarm_agents["scout"], swarm_agents["analyst"]],
        entry_point=swarm_agents["scout"],
        max_handoffs=8,
        max_iterations=8,
    )

    gb = GraphBuilder()
    gb.add_node(swarm, "swarm_src")
    gb.add_node(graph_agents["wf_mid"], "wf_mid")
    gb.add_node(graph_agents["sink"], "sink")
    gb.add_edge("swarm_src", "wf_mid", condition=bridge_predicate)
    gb.add_edge("wf_mid", "sink")
    gb.set_entry_point("swarm_src")
    gb.set_max_node_executions(10)
    graph = gb.build()

    started = time.time()
    result = graph(TASK)
    wall = time.time() - started

    # ---- live Graph-held objects -------------------------------------------
    graph_results_keys = sorted(result.results.keys())
    nr_swarm = result.results["swarm_src"]          # NodeResult
    sw_result = nr_swarm.result                      # SwarmResult
    nr_wf = result.results["wf_mid"]                 # NodeResult
    wf_agent_result = nr_wf.result                   # AgentResult
    node_result_fields = sorted(nr_swarm.to_dict().keys())

    # ---- STRUCTURED reachability (hasattr on the real objects) -------------
    structured = {
        "graph_noderesult_has_status": hasattr(nr_swarm, "status"),
        "graph_noderesult_has_accumulated_usage": hasattr(nr_swarm, "accumulated_usage"),
        "graph_noderesult_has_shared_context": hasattr(nr_swarm, "shared_context"),
        "swarmresult_has_shared_context": hasattr(sw_result, "shared_context"),
        "swarmresult_has_node_history": hasattr(sw_result, "node_history"),
        "graph_noderesult_has_task_results": hasattr(nr_wf, "task_results"),
        "wf_agentresult_has_task_results": hasattr(wf_agent_result, "task_results"),
    }
    swarm_channel_reaches_graph = (
        structured["graph_noderesult_has_shared_context"]
        or structured["swarmresult_has_shared_context"]
    )
    workflow_channel_reaches_graph = (
        structured["graph_noderesult_has_task_results"]
        or structured["wf_agentresult_has_task_results"]
    )
    predicate_fields = PREDICATE_LOG[-1]["seen_node_results"] if PREDICATE_LOG else {}

    # ---- real private channels ---------------------------------------------
    shared_context = json.loads(json.dumps(swarm.shared_context.context, default=str))
    sentinel_written = any(SENTINEL in json.dumps(v, default=str) for v in shared_context.values())

    inner_state = LAST_PIPELINE_RESULT.get("inner_state", {})
    inner_task_results = inner_state.get("task_results", {}) or {}
    task_result_fields = {tid: sorted(row.keys()) for tid, row in inner_task_results.items()}
    inner_ret = LAST_PIPELINE_RESULT.get("inner_return", {})
    start_return_fields = sorted(inner_ret.keys())
    start_text = workflow_text(inner_ret)

    # ---- downstream prompt + honest text-leakage annotations ---------------
    sink_prompt = first_input(graph_agents["sink"], limit=2600)
    graph_results_json = json.dumps(
        {k: v.to_dict() for k, v in result.results.items()}, default=str
    )
    text_leakage = {
        "sentinel_string_in_graph_results_text": SENTINEL in graph_results_json,
        "sentinel_string_in_sink_prompt": SENTINEL in sink_prompt,
        "task_results_word_in_graph_results_text": "task_results" in graph_results_json,
        "graph_structured_field_names_in_sink_prompt": (
            "accumulated_usage" in sink_prompt or '"status"' in sink_prompt
        ),
        "note": (
            "A raw string appearing in a message (tool-use / tool-result text) is "
            "not a structured field an orchestrator can branch on."
        ),
    }

    record = {
        **base("E6 context bridge: three paradigm data channels, enumerated"),
        "graph_status": result.status.value,
        "execution_order": [n.node_id for n in result.execution_order],
        "wall_clock_s": round(wall, 3),
        "sentinel_swarm": SENTINEL,
        "structured_reachability": structured,
        "channel_graph_state_results": {
            "object": "GraphState.results : dict[str, NodeResult]",
            "keys": graph_results_keys,
            "node_result_fields": node_result_fields,
            "predicate_eval_count": len(PREDICATE_LOG),
            "fields_predicate_read": predicate_fields,
            "reaches_condition_predicate": bool(predicate_fields),
            "reaches_downstream_node_prompt_as_structure": text_leakage["graph_structured_field_names_in_sink_prompt"],
            "what_crosses_to_next_node": "str(NodeResult) TEXT only",
        },
        "channel_swarm_shared_context": {
            "object": "Swarm.shared_context.context : dict[node_id][key]",
            "keys": {k: sorted(v) for k, v in shared_context.items()},
            "value": shared_context,
            "sentinel_written": sentinel_written,
            "reaches_graph_as_structured_field": swarm_channel_reaches_graph,
            "what_crosses_to_next_node": "str(SwarmResult) TEXT = per-node final text",
        },
        "channel_workflow": {
            "object": "persisted task_results + start return",
            "task_result_fields": task_result_fields,
            "start_return_fields": start_return_fields,
            "start_text": start_text,
            "per_task_status_on_disk": {t: r.get("status") for t, r in inner_task_results.items()},
            "reaches_graph_as_structured_field": workflow_channel_reaches_graph,
            "what_crosses_to_next_node": "one raw TEXT sentence",
        },
        "visibility_checks": text_leakage,
        "cross_boundary_matrix": [
            {"from": "Graph state.results", "to": "condition predicate",
             "reaches": node_result_fields, "loses": []},
            {"from": "Graph state.results", "to": "downstream Graph node prompt",
             "reaches": ["str(NodeResult) TEXT"],
             "loses": ["status", "accumulated_usage", "accumulated_metrics", "execution_time", "execution_count"]},
            {"from": "Swarm SharedContext", "to": "Graph state.results",
             "reaches": [], "loses": ["shared_context.context", "sentinel " + SENTINEL, "node_history", "handoff_message"]},
            {"from": "Workflow task_results", "to": "Graph state.results",
             "reaches": [],
             "loses": ["task_results.status", "task_results.result", "task_results.metrics", "per-task success bool"]},
        ],
        "sink_first_input": sink_prompt,
        "results_text": {k: str(v)[:240] for k, v in result.results.items()},
        "ledger": list(LEDGER),
    }
    emit("e6-context-bridge", record)
    return record


if __name__ == "__main__":
    run()
