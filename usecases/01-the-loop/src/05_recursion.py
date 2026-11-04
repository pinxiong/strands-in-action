"""Print the recursion depth of the agent loop, one line per cycle.

The loop in strands-agents 1.63.0 is recursive, not a while loop: a cycle that ran
a tool calls `recurse_event_loop`, which calls `event_loop_cycle` again. Wrapping
that one function is enough to watch the stack grow and shrink.

Run:  python src/05_recursion.py
"""

from importlib.metadata import version

import strands.event_loop.event_loop as event_loop_module
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))

_original = event_loop_module.recurse_event_loop
depth = 1


async def traced_recurse(*args, **kwargs):
    global depth
    depth += 1
    indent = "  " * (depth - 1)
    print(f"{indent}cycle {depth} begins (recursion depth {depth})")
    try:
        async for event in _original(*args, **kwargs):
            yield event
    finally:
        print(f"{indent}cycle {depth} ends")
        depth -= 1


event_loop_module.recurse_event_loop = traced_recurse

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)

print("cycle 1 begins (recursion depth 1)")
result = agent("What is the square root of 1764, plus 8?")
print("cycle 1 ends")

print("STOP_REASON :", result.stop_reason)
print("CYCLE_COUNT :", result.metrics.cycle_count)
print("TOOL_CALLS  :", list(result.metrics.tool_metrics.keys()))
