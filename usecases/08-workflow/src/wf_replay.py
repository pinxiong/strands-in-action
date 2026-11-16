"""E6: replay after failure, and what it does to side effects.

There is no resume action. The only way to retry a failed step is to rewrite
`status` in the persisted JSON and call start again. This run does exactly that
and counts save_draft calls from the ledger, so we can answer the reader
question about duplicate effects and decision revision with real output.

Run:  .venv/bin/python src/wf_replay.py --mode manual
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIXED = [1180, 940, 1520]


def guarded_start(workflow, wid: str, parent, seconds: int) -> dict:
    """Call start under a wall-clock guard.

    Restarting a workflow whose earlier steps are `completed` cannot satisfy
    `while len(completed_tasks) < total_tasks`: get_ready_tasks skips those
    steps, so they are never re-added to completed_tasks and the loop spins.
    The alarm makes that hang a recorded observation instead of a stuck run.
    """
    import signal
    import time

    def on_alarm(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"restart did not return within {seconds}s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    t0 = time.time()
    try:
        out = workflow(action="start", workflow_id=wid, agent=parent)
    except Exception as exc:  # noqa: BLE001
        out = {"status": "error", "content": [{"text": f"{type(exc).__name__}: {exc}"}]}
    finally:
        elapsed = round(time.time() - t0, 2)
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    text = str(out)
    return {
        "returned": out,
        "elapsed_s": elapsed,
        "busy_loop": "did not return within" in text or elapsed >= seconds - 1,
        "seconds_budget": seconds,
    }


def manual(wid: str) -> dict:
    from strands_tools.workflow import workflow

    parent = C.parent_agent()
    tasks = [
        {"task_id": "calc", "description": f"Call sum_tokens with {FIXED} and reply with its JSON verbatim.", "tools": ["sum_tokens"]},
        {"task_id": "write", "description": "Using the previous results, call save_draft once with a short brief containing the total and cost.", "tools": ["save_draft"], "dependencies": ["calc"]},
    ]

    created = workflow(action="create", workflow_id=wid, tasks=tasks, agent=parent)
    first = guarded_start(workflow, wid, parent, 30)
    ledger_after_first = list(C.LEDGER)
    result_after_first = {
        k: v.get("result") for k, v in C.state(wid).get("task_results", {}).items()
    }

    # Force the terminal step back to pending, as an operator would have to do
    # by editing ~/.strands/workflows/<id>.json. Leave calc completed: this is
    # the "replay from the failed step" case readers asked about.
    patched = C.patch_state(wid, {"write": "pending"})
    second = guarded_start(workflow, wid, parent, 18)
    ledger_after_second = list(C.LEDGER)

    st = C.state(wid)
    rec = C.base_record("manual-replay", wid)
    rec["extra"] = {
        "shape": "calc -> write; write replayed by editing persisted JSON",
        "created": created,
        "first_start": first,
        "second_start": second,
        "ledger_after_first": ledger_after_first,
        "ledger_after_second": ledger_after_second,
        "save_draft_calls_total": sum(1 for x in ledger_after_second if x["tool"] == "save_draft"),
        "sum_tokens_calls_total": sum(1 for x in ledger_after_second if x["tool"] == "sum_tokens"),
        "result_after_first": result_after_first,
        "result_after_second": {k: v.get("result") for k, v in st.get("task_results", {}).items()},
        "patched_status_seen_by_start": {k: v.get("status") for k, v in patched["task_results"].items()},
        "final_workflow_status": st.get("status"),
        "note": "restart skips completed steps and cannot reach total_tasks, so start_workflow busy-loops; the replayed step never reran (save_draft stays at 1 call). Only a fresh delete + create would repeat the side effect, and there is no idempotency key to deduplicate it",
    }
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["manual"], required=True)
    args = ap.parse_args()
    C.reset_ledger()
    C.install_prompt_probe()
    C.install_timing_probe()
    name = "wf-replay-manual"
    rec = manual(name)
    C.emit(name, rec)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
