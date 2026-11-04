"""One tool forces the loop into a second cycle.

Run:  python src/03_tools.py
"""

from importlib.metadata import version
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)
result = agent("What is the square root of 1764, plus 8?")

print("STOP_REASON :", result.stop_reason)
print("TEXT        :", result.message["content"][0]["text"])
print("USAGE       :", result.metrics.accumulated_usage)
print("CYCLE_COUNT :", result.metrics.cycle_count)
for name, metric in result.metrics.tool_metrics.items():
    print(
        f"TOOL        : {name} calls={metric.call_count} "
        f"success={metric.success_count} error={metric.error_count}"
    )
