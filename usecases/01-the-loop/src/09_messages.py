"""Print the shape of the conversation the model sees on each turn.

Tool results come back as a user-role message (event_loop.py:1087), so the history
the model reads on turn two is longer than the one it read on turn one. This prints
that growth one line per model call.

Run:  python src/09_messages.py
"""

from importlib.metadata import version

from strands import Agent
from strands.hooks.events import BeforeModelCallEvent
from strands.models import BedrockModel
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))


def shape(messages):
    parts = []
    for message in messages:
        kinds = sorted({next(iter(block)) for block in message.get("content", [])})
        parts.append(f"{message['role']}[{'+'.join(kinds)}]")
    return " | ".join(parts)


def log_before_model(event):
    state = event.invocation_state
    messages = event.agent.messages
    print(f"TURN cycle={str(state.get('event_loop_cycle_id'))[:8]}  messages={len(messages)}")
    print(f"     {shape(messages)}")


model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)
agent.add_hook(log_before_model, BeforeModelCallEvent)

result = agent("What is the square root of 1764, plus 8?")

print("FINAL       :", shape(agent.messages))
print("MESSAGES    :", len(agent.messages))
print("CYCLE_COUNT :", result.metrics.cycle_count)
