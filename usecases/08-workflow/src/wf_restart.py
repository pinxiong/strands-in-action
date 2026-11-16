"""E9: cross-process restart, the docstring's "state preservation across restarts".

Three separate processes share one state directory via UC08_STATE_DIR:

  create  -- process A creates a two-step workflow (a -> b), does not start it
  start   -- process B loads the JSON from disk and runs both steps
  restart -- process C loads the same JSON again and calls start once more

start_workflow's completed_tasks set starts empty on every call and only counts
steps it ran itself, so any workflow that already has `completed` steps can
never satisfy `while len(completed_tasks) < total_tasks`. This experiment makes
that visible with a wall-clock guard instead of hanging.

Run:
  UC08_STATE_DIR=/tmp/uc08-restart-state .venv/bin/python src/wf_restart.py --phase create
  ... --phase start
  ... --phase restart
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

WID = "restart-probe"


def tasks() -> list[dict]:
    return [
        {"task_id": "a", "description": "Call read_brief_input once and reply with the topic verbatim.", "tools": ["read_brief_input"]},
        {"task_id": "b", "description": "Call sum_tokens with [1180,940,1520] and reply with its JSON verbatim.", "tools": ["sum_tokens"], "dependencies": ["a"]},
    ]


def guarded_start(workflow, parent, seconds: int) -> dict:
    def on_alarm(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"start did not return within {seconds}s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    t0 = time.time()
    try:
        out = workflow(action="start", workflow_id=WID, agent=parent)
    except Exception as exc:  # noqa: BLE001
        out = {"status": "error", "content": [{"text": f"{type(exc).__name__}: {exc}"}]}
    finally:
        elapsed = round(time.time() - t0, 2)
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    return {
        "returned": out,
        "elapsed_s": elapsed,
        "busy_loop": "did not return within" in str(out) or elapsed >= seconds - 1,
        "seconds_budget": seconds,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["create", "start", "restart"], required=True)
    phase = ap.parse_args().phase
    C.install_prompt_probe()
    C.install_timing_probe()
    from strands_tools.workflow import workflow

    parent = C.parent_agent()
    before = {k: v.get("status") for k, v in C.state(WID).get("task_results", {}).items()}

    if phase == "create":
        out = workflow(action="create", workflow_id=WID, tasks=tasks(), agent=parent)
        rec = {"phase": phase, "create": out, "status_before": before,
               "status_after": {k: v.get("status") for k, v in C.state(WID)["task_results"].items()}}
    else:
        out = guarded_start(workflow, parent, 14)
        st = C.state(WID)
        rec = {"phase": phase, "start": out, "status_before": before,
               "workflow_status_after": st.get("status"),
               "status_after": {k: v.get("status") for k, v in st.get("task_results", {}).items()},
               "ledger_tools": [x["tool"] for x in C.LEDGER],
               "order": C.order()}

    name = f"wf-restart-{phase}"
    (C.EVIDENCE / f"{name}.json").write_text(json.dumps({
        "verified_on": "2026-11-16", "sdk": "strands-agents 1.63.0 / strands-agents-tools 0.8.11",
        "model": "amazon.nova-pro-v1:0 (us-east-1)", **rec,
    }, indent=2, default=str))
    print("WROTE", name)
    for k, v in rec.items():
        print(f"{k}={v}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
