"""E4/E5: two kinds of failure, with opposite outcomes.

swallowed -- explode() raises inside a tool; the SDK turns it into natural-language
             text, the task still reports `completed`, workflow reports 100%.
real     -- an invalid model id makes execute_task return status=error; its
             dependant stays `pending` forever and start_workflow busy-loops.

Run:  .venv/bin/python src/wf_failure.py --mode swallowed
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIXED = [1180, 940, 1520]


def swallowed(wid: str) -> dict:
    tasks = [
        {"task_id": "flaky", "description": "Call explode once, then briefly report what happened.", "tools": ["explode"]},
        {"task_id": "write", "description": f"Using the previous results, call sum_tokens with {FIXED} and reply with its JSON verbatim.", "tools": ["sum_tokens"], "dependencies": ["flaky"]},
    ]
    run = C.run_workflow(wid, tasks)
    rec = C.base_record("swallowed", wid)
    rec["extra"] = {"shape": "flaky -> write", "run": run, "injected": "explode() raises RuntimeError"}
    return rec


def real(wid: str) -> dict:
    tasks = [
        {"task_id": "bad", "description": "Say hello.", "model_provider": "bedrock", "model_settings": {"model_id": "definitely.not.a.real.model"}},
        {"task_id": "down", "description": "Summarize the previous results.", "dependencies": ["bad"]},
    ]
    run = C.run_workflow(wid, tasks, seconds=18)
    rec = C.base_record("real", wid)
    rec["extra"] = {
        "shape": "bad -> down",
        "run": run,
        "injected": "invalid Bedrock model id raises ValidationException inside execute_task",
        "pause": None,
    }
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["swallowed", "real"], required=True)
    args = ap.parse_args()
    C.reset_ledger()
    C.install_prompt_probe()
    C.install_timing_probe()
    name = f"wf-failure-{args.mode}"
    rec = swallowed(name) if args.mode == "swallowed" else real(name)
    C.emit(name, rec)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
