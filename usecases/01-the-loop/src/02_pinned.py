"""Pinned model and region. Expected to succeed on a single cycle.

Run:  python src/02_pinned.py
"""

from importlib.metadata import version
import strands
from strands import Agent
from strands.models import BedrockModel

print("SDK_VERSION :", version("strands-agents"))

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(model=model, callback_handler=None)
result = agent("In one sentence, what is the largest ocean on Earth?")

print("STOP_REASON :", result.stop_reason)
print("TEXT        :", result.message["content"][0]["text"])
print("USAGE       :", result.metrics.accumulated_usage)
print("LATENCY     :", result.metrics.accumulated_metrics.get("latencyMs"))
print("CYCLE_COUNT :", result.metrics.cycle_count)
