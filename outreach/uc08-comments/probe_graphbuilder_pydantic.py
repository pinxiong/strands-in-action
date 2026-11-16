#!/usr/bin/env python3
"""Probe for Artem Tokarev's Builder Center comment on UC08 (2026-11-16).

Question: how does `workflow` fit next to `GraphBuilder` / `structured_output`,
and is there a clean Pydantic + external-state wrapper?

Part A: source-level facts. No LLM.
Part B: deterministic parse/validate probe on the EXACT downstream prompt that
        UC08 recorded from a real Bedrock run. No LLM. Input is not invented:
        usecases/08-workflow/evidence/wf-contract-passthrough.txt.

Run:
    .venv/bin/python outreach/uc08-comments/probe_graphbuilder_pydantic.py \
        > outreach/uc08-comments/evidence/probe-output.txt
"""
import importlib.metadata as md
import inspect
import json
import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

import strands
import strands_tools
from strands import Agent

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "usecases/08-workflow/evidence/wf-contract-passthrough.txt"
WF = Path(strands_tools.__file__).parent / "workflow.py"
MULTI = Path(strands.__file__).parent / "multiagent"


class CalcResult(BaseModel):
    total: int
    cost_usd: float


def main() -> None:
    print("=== ENV ===")
    print("strands-agents", md.version("strands-agents"))
    print("strands-agents-tools", md.version("strands-agents-tools"))
    print("pydantic", md.version("pydantic"))
    print("workflow.py", WF)

    print("=== A1 workflow.py integration symbols ===")
    lines = WF.read_text().splitlines()
    for kw in ["structured_output", "GraphBuilder", "BaseModel", "pydantic",
               "output_schema", "validator"]:
        hits = [i + 1 for i, line in enumerate(lines) if kw in line]
        print(f"{kw}: {len(hits)} hits {hits[:5]}")

    print("=== A2 step boundary is rendered text ===")
    for i, line in enumerate(lines, 1):
        if "context.append(f\"Results from" in line or "task_agent(task_prompt)" in line:
            print(f"{i}: {line.strip()}")
    print("Agent.structured_output", inspect.signature(Agent.structured_output))

    print("=== A3 multiagent schema symbols ===")
    for kw in ["structured_output", "BaseModel", "model_validate", "pydantic",
               "output_schema"]:
        hits = []
        for f in sorted(MULTI.rglob("*.py")):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if kw in line:
                    hits.append(f"{f.name}:{i}")
        print(f"{kw}: {len(hits)} hits {hits[:5]}")

    print("=== B recorded downstream prompt ===")
    txt = EVID.read_text()
    m = re.search(r"^downstream_prompt_full=(.*?)(?=^note=)", txt, re.S | re.M)
    assert m, "downstream_prompt_full block not found in UC08 evidence"
    prompt = m.group(1).rstrip("\n")
    print("prompt_bytes:", len(prompt.encode()))
    print("prompt_repr:", repr(prompt))

    print("=== B1 json.loads on the whole rendered prompt ===")
    try:
        json.loads(prompt)
        print("PARSE: ok")
    except json.JSONDecodeError as e:
        print("PARSE: JSONDecodeError:", e.msg, "at pos", e.pos)

    print("=== B2 extract embedded JSON object then Pydantic validate ===")
    m2 = re.search(r'\{[^{}]*"total"[^{}]*\}', prompt)
    assert m2, "no embedded JSON object in recorded prompt"
    print("extracted:", repr(m2.group(0)))
    validated = CalcResult.model_validate(json.loads(m2.group(0)))
    print("validated:", validated.model_dump())

    print("=== B3 wrong type is rejected by Pydantic ===")
    try:
        CalcResult.model_validate({"total": "not-a-number", "cost_usd": 0.002912})
        print("BAD: accepted")
    except ValidationError as e:
        err = e.errors()[0]
        print("BAD: ValidationError:", err["type"], "loc=", err["loc"])

    print("=== BOUNDED CONCLUSION ===")
    print("workflow.py has no structured_output/BaseModel/pydantic/output_schema/validator symbol")
    print("the step boundary is a rendered string; a Pydantic wrapper must parse it itself")
    print("this probe did not run a new Bedrock workflow; input is the UC08 recorded prompt")


if __name__ == "__main__":
    main()
