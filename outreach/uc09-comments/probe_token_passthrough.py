"""UC09 comment probe: how can token usage cross the A2A boundary?

Question from Andres Zeballos on the Builder Center post:
"how would you get those token counts back to the caller?"

This is a deterministic, LLM-free probe. It builds REAL a2a-sdk objects and
feeds them through the REAL strands-agents converter that A2AAgent uses
(convert_response_to_agent_result), so every claim about "what the caller
receives" is measured, not inferred. It does NOT start two OS processes and
does NOT call Bedrock; the 2369 figure below is the shape of the number
recorded in the post's E8 evidence (usecases/09-a2a/evidence/a2a-cost.txt).

One variable at a time, with a control:
  A1  control: the executor's default artifact (one TextPart, no usage)
  B1  add a DataPart carrying usage to that artifact
  B2  add artifact.metadata carrying usage
  C1  encode usage as a JSON line inside a TextPart (a channel you own)
  C2  side ledger: server writes remote-usage.jsonl, caller reads it back

Versions: strands-agents 1.63.0, a2a-sdk 0.3.26, Python 3.11.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from a2a.types import (
    Artifact,
    DataPart,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TextPart,
)
from strands.multiagent.a2a._converters import convert_response_to_agent_result

USAGE = {"inputTokens": 2176, "outputTokens": 193, "totalTokens": 2369}
ANSWER_TEXT = "The receipt id is R-001."


def make_event(parts, metadata=None):
    """Build the (Task, TaskArtifactUpdateEvent) tuple A2AAgent hands to the converter."""
    artifact = Artifact(
        artifact_id="art-1",
        name="agent_response",
        parts=parts,
        metadata=metadata,
    )
    event = TaskArtifactUpdateEvent(
        task_id="task-1",
        context_id="ctx-1",
        artifact=artifact,
    )
    task = Task(
        id="task-1",
        context_id="ctx-1",
        status=TaskStatus(state=TaskState.completed),
        artifacts=[artifact],
    )
    return task, event


def caller_view(result):
    """Flatten exactly what the caller can read off its AgentResult."""
    usage = json.loads(
        json.dumps(getattr(result.metrics, "accumulated_usage", None), default=str)
    )
    texts = [
        b.get("text")
        for b in result.message.get("content", [])
        if isinstance(b, dict) and "text" in b
    ]
    return {
        "accumulated_usage": usage,
        "texts": texts,
        "state": json.loads(json.dumps(getattr(result, "state", None), default=str)),
    }


def show(label, result):
    v = caller_view(result)
    print(f"{label} caller.accumulated_usage = {json.dumps(v['accumulated_usage'], sort_keys=True)}")
    print(f"{label} caller.texts = {json.dumps(v['texts'])}")
    print(f"{label} caller.state = {json.dumps(v['state'], sort_keys=True)}")


def main() -> None:
    import importlib.metadata as md

    print("=== UC09 comment probe: token usage across the A2A boundary ===")
    print(f"strands-agents = {md.version('strands-agents')}")
    print(f"a2a-sdk = {md.version('a2a-sdk')}")
    print("converter = strands/multiagent/a2a/_converters.py :: convert_response_to_agent_result")
    print("no server process, no Bedrock call; real SDK objects through the real converter")
    print("")

    # ---- A1: control, exactly what the executor builds (executor.py:540-545) ----
    print("--- A1 control: default artifact = one TextPart(str(result)) ---")
    a1_parts = [Part(root=TextPart(text=ANSWER_TEXT))]
    a1_task, a1_event = make_event(a1_parts)
    a1 = convert_response_to_agent_result((a1_task, a1_event))
    show("A1", a1)
    print("")

    # ---- B1: add a DataPart carrying usage (protocol-native structured part) ----
    print("--- B1: add DataPart(data=USAGE); metadata untouched ---")
    b1_parts = [
        Part(root=TextPart(text=ANSWER_TEXT)),
        Part(root=DataPart(data={"accumulated_usage": USAGE})),
    ]
    b1_task, b1_event = make_event(b1_parts)
    print(f"B1 artifact.parts[1].root.data = {json.dumps(b1_event.artifact.parts[1].root.data, sort_keys=True)}")
    b1 = convert_response_to_agent_result((b1_task, b1_event))
    show("B1", b1)
    print("")

    # ---- B2: add artifact.metadata carrying usage ----
    print("--- B2: add artifact.metadata=USAGE; parts unchanged (control's one TextPart) ---")
    b2_parts = [Part(root=TextPart(text=ANSWER_TEXT))]
    b2_task, b2_event = make_event(b2_parts, metadata={"accumulated_usage": USAGE})
    print(f"B2 artifact.metadata = {json.dumps(b2_event.artifact.metadata, sort_keys=True)}")
    b2 = convert_response_to_agent_result((b2_task, b2_event))
    show("B2", b2)
    print("")

    # ---- C1: encode usage as a JSON line inside a TextPart (survives the converter) ----
    print("--- C1: append a second TextPart carrying a JSON usage line ---")
    usage_line = json.dumps({"usage": USAGE}, sort_keys=True)
    c1_parts = [
        Part(root=TextPart(text=ANSWER_TEXT)),
        Part(root=TextPart(text=usage_line)),
    ]
    c1_task, c1_event = make_event(c1_parts)
    c1 = convert_response_to_agent_result((c1_task, c1_event))
    show("C1", c1)
    recovered = None
    for t in caller_view(c1)["texts"]:
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "usage" in obj:
            recovered = obj["usage"]
    print(f"C1 caller json.loads -> usage = {json.dumps(recovered, sort_keys=True)}")
    print(f"C1 totalTokens recovered = {recovered['totalTokens'] if recovered else None}")
    print("")

    # ---- C2: side ledger, the channel E8 already used (common.py UsageRecorder) ----
    print("--- C2: server writes a usage ledger; caller reads it back by key ---")
    with tempfile.TemporaryDirectory() as state:
        ledger = Path(state) / "remote-usage.jsonl"
        # server process wrote this line from its AfterInvocationEvent hook
        ledger.write_text(
            json.dumps({"pid": 52539, "key": "uc09-cost", "accumulated_usage": USAGE}) + "\n",
            encoding="utf-8",
        )
        # caller process reads it back, keyed by the idempotency key
        rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
        match = [r for r in rows if r["key"] == "uc09-cost"]
        print(f"C2 ledger line = {ledger.read_text().strip()}")
        print(f"C2 caller readback by key 'uc09-cost' = {json.dumps(match[0] if match else None, sort_keys=True)}")
        print(f"C2 totalTokens recovered = {match[0]['accumulated_usage']['totalTokens'] if match else None}")
    print("")

    # ---- bounded conclusion, computed from the results above ----
    print("=== BOUNDED CONCLUSION ===")

    def reachable(result) -> bool:
        """Does the value 2369 appear anywhere in what the caller can read?"""
        return "2369" in json.dumps(caller_view(result))

    print(f"A1 usage all zero: {all(v == 0 for v in caller_view(a1)['accumulated_usage'].values())}")
    print(f"B1 DataPart reached artifact: {'2369' in json.dumps(b1_event.artifact.parts[1].root.data, default=str)}")
    print(f"B1 2369 reachable from caller result: {reachable(b1)}")
    print(f"B1 caller usage still all zero: {all(v == 0 for v in caller_view(b1)['accumulated_usage'].values())}")
    print(f"B2 metadata reached artifact: {'2369' in json.dumps(b2_event.artifact.metadata, default=str)}")
    print(f"B2 2369 reachable from caller result: {reachable(b2)}")
    print(f"B2 caller.state has no usage key: {'accumulated_usage' not in caller_view(b2)['state']}")
    print(f"C1 usage recovered from a TextPart: {recovered == USAGE}")
    print(f"C2 usage recovered from side ledger by key: {bool(match)}")
    print("Scope: converter-level, deterministic objects; no live server, no Bedrock,")
    print("no claim about answer quality or about a full two-process run here.")


if __name__ == "__main__":
    main()
