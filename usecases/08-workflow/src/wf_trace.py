"""E1/E2: execution order and real parallelism in the workflow tool.

linear   -- three chained steps (research -> calc -> write), same fixture as UC06/UC07
parallel -- three dependency-free steps, slow_step separates their wall-clock spans

Each mode writes evidence/<name>.json; stdout is redirected to <name>.txt.
Run from the usecase root:  .venv/bin/python src/wf_trace.py --mode linear
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIXED = [1180, 940, 1520]


def linear(wid: str) -> dict:
    tasks = [
        {"task_id": "research", "description": "Call read_brief_input once and reply with the topic sentence verbatim.", "tools": ["read_brief_input"]},
        {"task_id": "calc", "description": f"Call sum_tokens with {FIXED} and reply with its JSON verbatim.", "tools": ["sum_tokens"], "dependencies": ["research"]},
        {"task_id": "write", "description": "Using the previous results, call save_draft with a brief of 100 words or fewer containing the total and the cost.", "tools": ["save_draft"], "dependencies": ["calc"]},
    ]
    run = C.run_workflow(wid, tasks)
    rec = C.base_record("linear", wid)
    rec["extra"] = {
        "shape": "research -> calc -> write",
        "run": run,
        "note": "each step is a full Agent loop; there is no non-LLM step type",
    }
    return rec


def parallel(wid: str) -> dict:
    tasks = [
        {"task_id": "p1", "description": "Call slow_step with seconds=3, then reply 'p1 done'.", "tools": ["slow_step"]},
        {"task_id": "p2", "description": "Call slow_step with seconds=3, then reply 'p2 done'.", "tools": ["slow_step"]},
        {"task_id": "p3", "description": "Call slow_step with seconds=3, then reply 'p3 done'.", "tools": ["slow_step"]},
    ]
    run = C.run_workflow(wid, tasks)
    rec = C.base_record("parallel", wid)
    rec["extra"] = {"shape": "p1, p2, p3 (no dependencies)", "run": run}
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["linear", "parallel"], required=True)
    args = ap.parse_args()
    C.reset_ledger()
    C.install_prompt_probe()
    C.install_timing_probe()
    name = f"wf-trace-{args.mode}"
    rec = linear(name) if args.mode == "linear" else parallel(name)
    C.emit(name, rec)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
