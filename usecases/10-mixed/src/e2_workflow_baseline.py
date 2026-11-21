"""E2 — pure Workflow: the vended `workflow` tool runs the same three tasks.

Records the SHAPE of start's return value (raw text vs structure), whether a
downstream consumer can classify each task's success from that return alone,
and the real per-task token usage read off the task Agents.

    ../../.venv/bin/python src/e2_workflow_baseline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    LEDGER, TASK_TIMING,
    base, emit, install_workflow_probes, reset, run_workflow,
    task_first_prompts, task_model_calls_table, task_usage_table, workflow_tasks,
)

TASK_IDS = ["researcher", "calculator", "writer"]


def run() -> dict:
    reset()
    install_workflow_probes()
    out = run_workflow("e2-wf-linear", workflow_tasks())
    ret = out["start_returned"]
    state = out["state"]
    task_results = state.get("task_results", {})

    serialized = json.dumps(ret, default=str)
    content = ret.get("content", [])
    content_keys = [sorted(b.keys()) for b in content if isinstance(b, dict)]

    # A downstream consumer that only holds the return dict: can it tell each
    # task's status? It would need a field per task_id. Measure that directly.
    per_task_ids_in_return = {tid: (tid in serialized) for tid in TASK_IDS}
    can_classify = all(per_task_ids_in_return.values())

    usage = task_usage_table()
    calls = task_model_calls_table()
    record = {
        **base("E2 pure Workflow (vended workflow tool)"),
        "workflow_status": state.get("status"),
        "start_return_type": type(ret).__name__,
        "start_return_top_level_keys": sorted(ret.keys()),
        "start_return_content_keys": content_keys,
        "start_return_has_only_text_blocks": all(
            set(k) == {"text"} for k in content_keys
        ) if content_keys else False,
        "start_text": out["start_text"],
        "created_return": out["created"],
        "timed_out": out["timed_out"],
        "downstream_can_classify_each_task_from_return": can_classify,
        "per_task_id_appears_in_return": per_task_ids_in_return,
        "return_carries_no_per_task_status_boolean": not can_classify,
        "task_status_on_disk": {tid: task_results.get(tid, {}).get("status") for tid in TASK_IDS},
        "task_result_text_on_disk": {
            tid: "\n".join(
                b.get("text", "") for b in (task_results.get(tid, {}).get("result") or [])
                if isinstance(b, dict)
            )[:300]
            for tid in TASK_IDS
        },
        "task_metrics_on_disk": {tid: task_results.get(tid, {}).get("metrics") for tid in TASK_IDS},
        "per_task_tokens": usage,
        "tokens_total": sum(u["totalTokens"] for u in usage.values()),
        "model_calls": calls,
        "model_calls_total": sum(calls.values()),
        "workflow_elapsed_s": out["elapsed_s"],
        "task_timing": [
            {"task": t["task"], "duration_s": round(t.get("stop", t["start"]) - t["start"], 3)}
            for t in TASK_TIMING
        ],
        "first_prompts": task_first_prompts(),
        "ledger": list(LEDGER),
    }
    emit("e2-workflow-baseline", record)
    return record


if __name__ == "__main__":
    run()
