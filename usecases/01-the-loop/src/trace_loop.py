"""UC01 - prove the loop runs more than one cycle when a tool is involved.

A question that forces a tool call, so we can count the cycles and see
the tool use, not just a single text reply.
"""
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

model = BedrockModel(model_id="amazon.nova-pro-v1:0", region_name="us-east-1")
agent = Agent(tools=[calculator], model=model)

result = agent("What is the square root of 1764, plus 8?")
print("STOP_REASON :", result.stop_reason)
print("TEXT :", result.message["content"][0]["text"])
print("USAGE :", result.metrics.accumulated_usage)
print("CYCLE_COUNT :", result.metrics.cycle_count)
print("TOOL_NAMES  :", list(result.metrics.tool_metrics))
for name, m in result.metrics.tool_metrics.items():
    print(f"  tool={name} calls={m.call_count} success={m.success_count} err={m.error_count}")
