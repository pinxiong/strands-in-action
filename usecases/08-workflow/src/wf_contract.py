"""E3: what the workflow tool validates, and what a downstream step receives.

schema      -- declare `output_schema`/`returns`/`expects` on tasks; create accepts
               them silently, no field is enforced anywhere
passthrough -- upstream returns JSON; inspect verbatim what the downstream prompt got

Run:  .venv/bin/python src/wf_contract.py --mode schema
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIXED = [1180, 940, 1520]


def schema(wid: str) -> dict:
    tasks = [
        {
            "task_id": "research",
            "description": "Call read_brief_input once and reply with the topic verbatim.",
            "tools": ["read_brief_input"],
            "output_schema": {"type": "object", "required": ["topic"]},
            "returns": "string",
            "expects": "nothing",
            "validator": "must_contain_total",
        },
        {
            "task_id": "calc",
            "description": f"Call sum_tokens with {FIXED} and reply with its JSON verbatim.",
            "tools": ["sum_tokens"],
            "dependencies": ["research"],
            "output_schema": {"type": "object", "required": ["total", "cost_usd"]},
        },
    ]
    run = C.run_workflow(wid, tasks)
    st = C.state(wid)
    rec = C.base_record("schema", wid)
    rec["extra"] = {
        "declared_extra_fields": ["output_schema", "returns", "expects", "validator"],
        "create_response": run["created"],
        "persisted_task_keys": {t["task_id"]: sorted(t.keys()) for t in st.get("tasks", [])},
        "note": "create_workflow only checks task_id, description and that a dependency id exists; extra keys are copied verbatim and never read",
    }
    return rec


def passthrough(wid: str) -> dict:
    tasks = [
        {"task_id": "calc", "description": f"Call sum_tokens with {FIXED} and reply with ONLY the raw JSON object, no prose and no code fence.", "tools": ["sum_tokens"]},
        {"task_id": "write", "description": "Using the previous results, call save_draft with the total and cost. Then reply with the exact upstream text you were given, enclosed in <raw> tags.", "tools": ["save_draft"], "dependencies": ["calc"]},
    ]
    run = C.run_workflow(wid, tasks)
    rec = C.base_record("passthrough", wid)
    rec["extra"] = {
        "shape": "calc -> write",
        "run": run,
        "downstream_prompt_full": C.first_prompt("write", limit=4000),
        "note": "downstream receives a rendered natural-language string built by execute_task, not a typed field",
    }
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["schema", "passthrough"], required=True)
    args = ap.parse_args()
    C.reset_ledger()
    C.install_prompt_probe()
    C.install_timing_probe()
    name = f"wf-contract-{args.mode}"
    rec = schema(name) if args.mode == "schema" else passthrough(name)
    C.emit(name, rec)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
