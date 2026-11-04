"""Print the cycle ids the event loop writes into invocation_state.

`event_loop_cycle_id` is set at event_loop.py:230 and `event_loop_parent_cycle_id`
at event_loop.py:1109, right before the next cycle starts. Reading them from a hook
is the cheapest way to see that the ids in the trace come from the loop itself and
not from the tracer.

Run:  python src/06_cycle_ids.py
"""

from importlib.metadata import version

from strands import Agent
from strands.hooks.events import AfterToolsEvent, BeforeModelCallEvent
from strands.models import BedrockModel
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))


def short(value):
    return str(value)[:8] if value else "-"


def log_before_model(event):
    state = event.invocation_state
    print(
        f"MODEL CALL  cycle={short(state.get('event_loop_cycle_id'))}"
        f"  parent={short(state.get('event_loop_parent_cycle_id'))}"
    )


def log_after_tools(event):
    state = event.invocation_state
    print(
        f"TOOL RESULT cycle={short(state.get('event_loop_cycle_id'))}"
        f"  parent={short(state.get('event_loop_parent_cycle_id'))}"
        f"  parent_written_at=end_of_this_cycle"
    )


model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)

agent.add_hook(log_before_model, BeforeModelCallEvent)
agent.add_hook(log_after_tools, AfterToolsEvent)

result = agent("What is the square root of 1764, plus 8?")

print("STOP_REASON :", result.stop_reason)
print("CYCLE_COUNT :", result.metrics.cycle_count)
