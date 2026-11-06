"""E3: the model decides how many tool calls fit in one turn.

Two identical tool loops, two prompts. The sequential prompt gets one
tool call per turn. The parallel prompt tells the model it may request
several calls in one response, and all eight land in a single turn.
Both runs have no limits. A turn is one model call plus any tool
execution that follows, so a turn limit bounds model calls, not tool
invocations. Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os

from strands import Agent, tool
from strands.models import BedrockModel

TARGET = 8

SEQUENTIAL_PROMPT = (
    "Record all 8 ticks using the tick tool one at a time, waiting for each "
    "result before the next call, then summarize."
)
PARALLEL_PROMPT = (
    "Record all 8 ticks using the tick tool. You may request multiple tick "
    "calls in a single response if that is faster, then summarize."
)


@tool
def tick(progress: int) -> str:
    """Record one tick of a batch job.

    Args:
        progress: how many ticks were already recorded before this call.

    Returns:
        The total recorded so far and how many remain in the batch.
    """
    done = min(progress + 1, TARGET)
    remaining = TARGET - done
    if remaining > 0:
        return (
            f"Recorded {done}/{TARGET} ticks. {remaining} remain. "
            f"Call tick again with progress={done}."
        )
    return f"Recorded {done}/{TARGET} ticks. Batch complete."


def run(label: str, prompt: str, limits: dict | None = None) -> None:
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )
    agent = Agent(model=model, tools=[tick])
    result = agent(prompt, limits=limits)
    usage = dict(result.invocation_context.usage) if result.invocation_context else {}
    turns = usage.get("turns_taken") or 0
    tool_calls = sum(
        1 for msg in agent.messages for b in msg.get("content", []) if "toolUse" in b
    )
    print(f"=== {label} ===")
    print("LIMITS      :", limits)
    print("STOP_REASON :", result.stop_reason)
    print("TURNS_TAKEN :", turns)
    print("TOOL_CALLS  :", tool_calls)
    print("CALLS/TURN  :", f"{tool_calls / turns:.1f}" if turns else "n/a")
    print("TOTAL_TOK   :", usage.get("totalTokens"))
    print()


def main() -> None:
    run("A: sequential prompt", SEQUENTIAL_PROMPT)
    run("B: parallel prompt", PARALLEL_PROMPT)
    run("C: parallel prompt under turns=1", PARALLEL_PROMPT, {"turns": 1})


if __name__ == "__main__":
    main()
