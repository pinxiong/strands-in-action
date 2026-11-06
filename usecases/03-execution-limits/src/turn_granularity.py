"""E2: how many tool calls fit in one turn is up to the model.

Five identical runs, no limits. A turn is one model call plus any tool
execution that follows, and the model decides how many tool calls to
request per response: some runs spread eight calls across eight turns,
one run packed all eight into a single turn. A turn limit therefore
bounds model calls, not tool invocations. Runs against
amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os

from strands import Agent, tool
from strands.models import BedrockModel

TARGET = 8
RUNS = 5


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


def main() -> None:
    print(f"same prompt, {RUNS} runs, no limits")
    print("run | turns | tool_calls | calls_per_turn")
    for i in range(1, RUNS + 1):
        model = BedrockModel(
            model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
            region_name="us-east-1",
        )
        agent = Agent(model=model, tools=[tick])
        result = agent("Record all 8 ticks using the tick tool, then summarize.")
        usage = dict(result.invocation_context.usage) if result.invocation_context else {}
        turns = usage.get("turns_taken") or 0
        tool_calls = sum(
            1 for msg in agent.messages for b in msg.get("content", []) if "toolUse" in b
        )
        ratio = f"{tool_calls / turns:.1f}" if turns else "n/a"
        print(f" {i}  |  {turns}   |     {tool_calls}     |    {ratio}")


if __name__ == "__main__":
    main()
