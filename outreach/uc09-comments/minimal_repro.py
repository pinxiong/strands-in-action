"""Minimal, runnable repro for the UC09 comment reply.

Shows the one channel the stock converter keeps: a TextPart carrying a JSON
usage line. Feed a real a2a-sdk artifact through the real strands converter and
read back 2369 on the caller side. No server, no Bedrock, deterministic.

Run: .venv/bin/python outreach/uc09-comments/minimal_repro.py
"""

import json

from a2a.types import Artifact, Part, Task, TaskArtifactUpdateEvent, TaskState, TaskStatus, TextPart
from strands.multiagent.a2a._converters import convert_response_to_agent_result

USAGE = {"inputTokens": 2176, "outputTokens": 193, "totalTokens": 2369}
answer = Part(root=TextPart(text="The receipt id is R-001."))
carry = Part(root=TextPart(text=json.dumps({"usage": USAGE})))
artifact = Artifact(artifact_id="a1", name="agent_response", parts=[answer, carry])
event = TaskArtifactUpdateEvent(task_id="t1", context_id="c1", artifact=artifact)
task = Task(id="t1", context_id="c1", status=TaskStatus(state=TaskState.completed), artifacts=[artifact])
result = convert_response_to_agent_result((task, event))
print("caller.metrics.accumulated_usage =", dict(result.metrics.accumulated_usage))
print("caller text parts =", [b["text"] for b in result.message["content"]])
print("recovered totalTokens =", json.loads(result.message["content"][1]["text"])["usage"]["totalTokens"])
