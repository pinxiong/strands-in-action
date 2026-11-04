"""Read the OpenTelemetry span tree of a two-cycle run.

Run:  python src/04_trace.py
"""

from importlib.metadata import version
import strands
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))

StrandsTelemetry().setup_console_exporter()

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)
result = agent("What is the square root of 1764, plus 8?")

print("CYCLE_COUNT :", result.metrics.cycle_count)
print("TOTAL_TOKENS:", result.metrics.accumulated_usage.get("totalTokens"))
