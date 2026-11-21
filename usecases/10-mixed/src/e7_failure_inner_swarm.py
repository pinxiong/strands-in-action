"""E7 — failure injection inside a Swarm node of a Graph.

Two real Bedrock runs, two ways an inner failure can surface, one evidence file:
  swallowed    : inner agent calls `explode` (tool raises; the agent loop catches
                 it and returns it as text). Swarm finishes COMPLETED.
  agent_raise  : a hook raises AFTER the real model call, so the exception escapes
                 the agent loop. Swarm finishes FAILED.

Records the outer Graph's final status, whether it treated the inner failure as
success, and what the downstream node received. Contrast: UC08's "a tool that
raises still reports 100% success".

    ../../.venv/bin/python src/e7_failure_inner_swarm.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.hooks.events import AfterModelCallEvent
from strands.multiagent import Swarm
from strands.multiagent.graph import GraphBuilder

from common import (
    LEDGER, TASK, TOOLS,
    base, emit, first_input, node_agents, reset,
)

ERROR_MARKER = "injected tool failure"

SWARM_SWALLOWED = {
    "scout": (
        "You are the scout. Call the explode tool exactly once. Report what happened "
        "in one short sentence. Do not hand off to anyone. Do not call any other tool."
    ),
}
SWARM_AGENT_RAISE = {
    "scout": "You are the scout. Call read_brief_input once and state the topic briefly.",
}
SINK_INSTRUCTIONS = {
    "sink": (
        "You are the sink. State in one short sentence what the upstream stage "
        "reported. Do not call any tool."
    ),
}


def crash(event) -> None:  # noqa: ANN001
    raise RuntimeError("injected agent-level failure")


def one_run(mode: str) -> dict:
    reset()
    swarm_instructions = SWARM_SWALLOWED if mode == "swallowed" else SWARM_AGENT_RAISE
    swarm_agents, _ = node_agents(swarm_instructions, TOOLS)
    sink_agents, _ = node_agents(SINK_INSTRUCTIONS, [])

    if mode == "agent_raise":
        swarm_agents["scout"].hooks.add_callback(AfterModelCallEvent, crash)

    swarm = Swarm(
        nodes=[swarm_agents["scout"]],
        entry_point=swarm_agents["scout"],
        max_handoffs=6,
        max_iterations=6,
    )

    gb = GraphBuilder()
    gb.add_node(swarm, "swarm_src")
    gb.add_node(sink_agents["sink"], "sink")
    gb.add_edge("swarm_src", "sink")
    gb.set_entry_point("swarm_src")
    gb.set_max_node_executions(10)
    graph = gb.build()

    started = time.time()
    try:
        result = graph(TASK)
        graph_error = ""
    except Exception as exc:  # noqa: BLE001
        result = None
        graph_error = f"{type(exc).__name__}: {exc}"
    wall = time.time() - started

    if result is None:
        return {
            "mode": mode,
            "graph_raised": graph_error,
            "graph_status": "exception",
            "execution_order": [],
            "wall_clock_s": round(wall, 3),
        }

    order = [n.node_id for n in result.execution_order]
    nr = result.results.get("swarm_src")
    inner = getattr(nr, "result", None) if nr else None
    inner_status = inner.status.value if inner is not None else None
    node_text = str(nr) if nr else ""
    sink_ran = "sink" in order
    sink_prompt = first_input(sink_agents["sink"]) if sink_ran else "<node never ran>"

    return {
        "mode": mode,
        "graph_raised": graph_error,
        "inner_swarm_status": inner_status,
        "graph_status": result.status.value,
        "execution_order": order,
        "completed_nodes": result.completed_nodes,
        "failed_nodes": result.failed_nodes,
        "downstream_sink_ran": sink_ran,
        "inner_error_marker_in_graph_node_text": ERROR_MARKER in node_text,
        "inner_error_marker_reaches_sink_prompt": ERROR_MARKER in sink_prompt,
        "sink_first_input": sink_prompt[:900],
        "graph_node_text_swarm_src": node_text[:400],
        "graph_treated_inner_failure_as_success": (
            inner_status in ("failed", None) and result.status.value == "completed"
        ) or (ERROR_MARKER in node_text and result.status.value == "completed"),
        "wall_clock_s": round(wall, 3),
        "ledger": list(LEDGER),
    }


def run() -> dict:
    swallowed = one_run("swallowed")
    agent_raise = one_run("agent_raise")
    record = {
        **base("E7 failure injection: inner Swarm failure vs outer Graph status"),
        "swallowed": swallowed,
        "agent_raise": agent_raise,
        "uc08_contrast": (
            "UC08: a tool that raises is swallowed by the agent loop and the "
            "workflow still reports 100% success. E7 shows the same swallowed "
            "failure crossing a Swarm node boundary: the outer Graph reports "
            "COMPLETED. Only an agent-level exception (escaping the loop) turns "
            "the inner Swarm FAILED and makes the Graph FAIL + prune its branch."
        ),
        "swallowed_graph_status": swallowed.get("graph_status"),
        "swallowed_treated_as_success": swallowed.get("graph_treated_inner_failure_as_success"),
        "agent_raise_graph_status": agent_raise.get("graph_status"),
        "agent_raise_downstream_ran": agent_raise.get("downstream_sink_ran"),
    }
    emit("e7-failure-inner-swarm", record)
    return record


if __name__ == "__main__":
    run()
