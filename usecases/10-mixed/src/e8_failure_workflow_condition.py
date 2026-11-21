"""E8 — failure injection in a Workflow sub-process, gated by a Graph
condition predicate.

The inner Workflow runs the UC08 "swallowed" case: its first task calls
`explode` (tool raises, caught as text), so the vended tool still reports
"3/3 tasks succeeded - 100.0%". A Graph condition predicate then tries to
detect that inner failure by reading state.results. It cannot: all it can see
is the wf_stage node's final TEXT, which is the success sentence.

    ../../.venv/bin/python src/e8_failure_workflow_condition.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands.multiagent.graph import GraphBuilder

from common import (
    LAST_PIPELINE_RESULT, LEDGER, ROLE_INSTRUCTIONS, TASK, TOOLS,
    base, emit, first_input, install_workflow_probes, node_agents, reset,
    run_brief_pipeline, workflow_text,
)

ERROR_MARKER = "injected tool failure"
PREDICATE_LOG: list[dict] = []

INSTRUCTIONS = {
    "wf_stage": (
        "You are the workflow stage. Call run_brief_pipeline with mode='swallowed' "
        "exactly once. Then report its result verbatim in one short sentence. "
        "Do not call any other tool."
    ),
    "ok_writer": ROLE_INSTRUCTIONS["writer"],
    "fallback": "Reply with exactly: INNER FAILURE DETECTED. Do not call any tool.",
}


def _results_text(state) -> str:
    return " ".join(str(nr) for nr in (state.results or {}).values())


def inner_looks_failed(state, *, invocation_state, **kwargs) -> bool:
    text = _results_text(state)
    hit = ERROR_MARKER in text
    PREDICATE_LOG.append({
        "edge": "wf_stage->fallback",
        "expect": f"'{ERROR_MARKER}' in state.results text",
        "hit": hit,
        "excerpt": text[:300],
    })
    return hit


def inner_looks_ok(state, *, invocation_state, **kwargs) -> bool:
    text = _results_text(state)
    hit = ERROR_MARKER not in text
    PREDICATE_LOG.append({
        "edge": "wf_stage->ok_writer",
        "expect": f"'{ERROR_MARKER}' NOT in state.results text",
        "hit": hit,
        "excerpt": text[:300],
    })
    return hit


def run() -> dict:
    reset()
    PREDICATE_LOG.clear()
    install_workflow_probes()

    agents, _ = node_agents(INSTRUCTIONS, TOOLS + [run_brief_pipeline])

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("wf_stage", "ok_writer", condition=inner_looks_ok)
    gb.add_edge("wf_stage", "fallback", condition=inner_looks_failed)
    gb.set_entry_point("wf_stage")
    gb.set_max_node_executions(10)
    graph = gb.build()

    started = time.time()
    result = graph(TASK)
    wall = time.time() - started

    order = [n.node_id for n in result.execution_order]
    inner_state = LAST_PIPELINE_RESULT.get("inner_state", {})
    inner_task_results = inner_state.get("task_results", {}) or {}
    inner_ret = LAST_PIPELINE_RESULT.get("inner_return", {})
    start_text = workflow_text(inner_ret)

    researcher_disk_text = "\n".join(
        b.get("text", "") for b in (inner_task_results.get("researcher", {}).get("result") or [])
        if isinstance(b, dict)
    )
    wf_stage_text = str(result.results["wf_stage"]) if "wf_stage" in result.results else ""

    branch = "ok_writer" if "ok_writer" in order else ("fallback" if "fallback" in order else "none")
    failed_pred_hits = [
        log["hit"] for log in PREDICATE_LOG if log["edge"] == "wf_stage->fallback"
    ]

    record = {
        **base("E8 failure injection: Workflow failure vs Graph condition predicate"),
        "graph_status": result.status.value,
        "execution_order": order,
        "branch_taken": branch,
        "wall_clock_s": round(wall, 3),
        "inner_workflow_reported": start_text,
        "inner_workflow_reports_100pct_success": "100.0%" in start_text,
        "inner_workflow_status": inner_state.get("status"),
        "inner_task_status_on_disk": {t: r.get("status") for t, r in inner_task_results.items()},
        "inner_error_marker_in_researcher_disk_text": ERROR_MARKER in researcher_disk_text,
        "inner_researcher_disk_text": researcher_disk_text[:300],
        "inner_actually_failed": ERROR_MARKER in researcher_disk_text,
        "wf_stage_node_text": wf_stage_text[:400],
        "inner_error_marker_in_wf_stage_node_text": ERROR_MARKER in wf_stage_text,
        "predicate_log": PREDICATE_LOG,
        "predicate_eval_count": len(PREDICATE_LOG),
        "predicate_saw_inner_failure_marker": any(failed_pred_hits),
        "condition_could_classify_inner_failure": any(failed_pred_hits),
        "ok_writer_first_input": first_input(agents["ok_writer"], 1200) if branch == "ok_writer" else "<not run>",
        "uc08_contrast": (
            "UC08: a swallowed tool failure is reported by the workflow as 100% "
            "success. E8: because the vended tool returns only one raw TEXT "
            "sentence, the Graph's condition predicate (which reads "
            "state.results text) cannot see the inner failure marker that sits "
            "only on the workflow's disk state. It routes to ok_writer."
        ),
        "ledger": list(LEDGER),
    }
    emit("e8-failure-workflow-condition", record)
    return record


if __name__ == "__main__":
    run()
