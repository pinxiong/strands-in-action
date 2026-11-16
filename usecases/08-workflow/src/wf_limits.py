"""E7/E8: the limits that do not limit, and the missing cost ledger.

timeout -- a task declares timeout=1 but slow_step(3) runs to completion;
           pause/resume actions are also probed (both return "not implemented").
ledger  -- parse the per-task token line out of the persisted metrics TEXT and
           compare it with the provider-side usage recorded in the task agent's
           own messages. Answers: is there a machine-readable budget checkpoint?

Run:  .venv/bin/python src/wf_limits.py --mode ledger
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIXED = [1180, 940, 1520]


def timeout(wid: str) -> dict:
    from strands_tools.workflow import workflow

    parent = C.parent_agent()
    tasks = [
        {"task_id": "slow", "description": "Call slow_step with seconds=3, then reply 'done'.", "tools": ["slow_step"], "timeout": 1},
    ]
    created = workflow(action="create", workflow_id=wid, tasks=tasks, agent=parent)
    import time

    t0 = time.time()
    start = workflow(action="start", workflow_id=wid, agent=parent)
    elapsed = round(time.time() - t0, 2)

    rec = C.base_record("timeout", wid)
    rec["extra"] = {
        "declared_timeout_s": C.state(wid)["tasks"][0].get("timeout"),
        "elapsed_s": elapsed,
        "created": created,
        "start": start,
        "pause": workflow(action="pause", workflow_id=wid, agent=parent),
        "resume": workflow(action="resume", workflow_id=wid, agent=parent),
        "note": "task['timeout'] is stored by create_workflow but never read by execute_task; there is no budget or pause hook at the workflow layer",
    }
    return rec


def provider_usage(task_id: str) -> dict:
    """Sum the usage blocks the provider attached to this task agent's messages."""
    agent = C.TASK_AGENTS.get(task_id)
    if agent is None:
        return {"error": "no task agent captured"}
    tin = tout = 0
    calls = 0
    for msg in agent.messages:
        usage = (msg.get("metadata") or {}).get("usage") or {}
        if usage:
            calls += 1
            tin += int(usage.get("inputTokens", 0) or 0)
            tout += int(usage.get("outputTokens", 0) or 0)
    return {"input": tin, "output": tout, "total": tin + tout, "usage_blocks": calls}


def ledger(wid: str) -> dict:
    tasks = [
        {"task_id": "research", "description": "Call read_brief_input once and reply with the topic sentence verbatim.", "tools": ["read_brief_input"]},
        {"task_id": "calc", "description": f"Call sum_tokens with {FIXED} and reply with its JSON verbatim.", "tools": ["sum_tokens"], "dependencies": ["research"]},
        {"task_id": "write", "description": "Using the previous results, call save_draft with a brief of 100 words or fewer containing the total and cost.", "tools": ["save_draft"], "dependencies": ["calc"]},
    ]
    run = C.run_workflow(wid, tasks)
    st = C.state(wid)

    parsed = {}
    for tid, r in st.get("task_results", {}).items():
        text = r.get("metrics") or ""
        m = re.search(r"Tokens: in=(\d+), out=(\d+), total=(\d+)", text)
        parsed[tid] = {
            "metrics_is_plain_text": isinstance(r.get("metrics"), str),
            "metrics_has_structured_fields": isinstance(r.get("metrics"), dict),
            "token_line": m.group(0) if m else None,
            "from_text": {"in": int(m.group(1)), "out": int(m.group(2)), "total": int(m.group(3))} if m else None,
            "provider_side": provider_usage(tid),
        }

    totals = {
        "sum_of_text_totals": sum(v["from_text"]["total"] for v in parsed.values() if v["from_text"]),
        "sum_of_provider_totals": sum(v["provider_side"].get("total", 0) for v in parsed.values()),
        "fixture_declared_total": sum(FIXED),
        "workflow_level_total_field": st.get("total_tokens", "<absent>"),
        "workflow_level_budget_field": st.get("budget", "<absent>"),
    }

    rec = C.base_record("ledger", wid)
    rec["extra"] = {
        "shape": "research -> calc -> write",
        "run": run,
        "per_task": parsed,
        "totals": totals,
        "note": "the only persisted accounting is a human-readable metrics string per task; no cross-task total, no budget checkpoint, no validator result",
    }
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["timeout", "ledger"], required=True)
    args = ap.parse_args()
    C.reset_ledger()
    C.install_prompt_probe()
    C.install_timing_probe()
    name = f"wf-limits-{args.mode}"
    rec = timeout(name) if args.mode == "timeout" else ledger(name)
    C.emit(name, rec)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
