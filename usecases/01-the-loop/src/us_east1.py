"""UC01 - try the same default model against us-east-1 explicitly."""
from strands import Agent
from strands.models import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
)
agent = Agent(model=model)
result = agent("In one sentence, what is the largest ocean on Earth?")
print("STOP_REASON :", result.stop_reason)
print("TEXT :", result.message["content"][0]["text"])
print("USAGE :", result.metrics.accumulated_usage)
print("LATENCY_MS :", result.metrics.accumulated_metrics.latencyMs)
