"""UC01 - The Loop. First verification run.

What this proves:
  - which model and region the default Agent() actually calls
  - what a single invocation produces (stop_reason, text, token usage)
"""
from strands import Agent

agent = Agent()  # default BedrockModel, no explicit config
cfg = agent.model.get_config()
print("MODEL_ID :", cfg.get("model_id"))

result = agent("In one sentence, what is the largest ocean on Earth?")
print("STOP_REASON :", result.stop_reason)
print("TEXT :", result.message["content"][0]["text"])
print("USAGE :", result.metrics.accumulated_usage)
print("LATENCY_MS :", result.metrics.accumulated_metrics.latencyMs)
