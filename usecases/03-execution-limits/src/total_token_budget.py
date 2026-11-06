"""E3: total tokens compound because each call re-reads the whole conversation.

A tool loop under limits={"total_tokens": 2600}. Per-cycle input grows
every turn (each model call's input includes prior turns and the tool
schema), so cumulative total tokens climb faster than one new response
per turn. Runs against deepseek.v3.2 on Bedrock (us-east-1).
"""
import os

from strands import Agent, tool
from strands.models import BedrockModel

CAP = 2600
TARGET = 8


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
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[tick])
    result = agent("Record all 8 ticks using the tick tool, then summarize.", limits={"total_tokens": CAP})
    usage = dict(result.invocation_context.usage) if result.invocation_context else {}
    invocations = result.metrics.agent_invocations
    cycles = invocations[-1].cycles if invocations else []
    print("CAP         :", CAP)
    print("STOP_REASON :", result.stop_reason)
    print("TURNS_TAKEN :", usage.get("turns_taken"))
    print("TOTAL_TOK   :", usage.get("totalTokens"))
    print("OVERSHOOT   :", (usage.get("totalTokens") or 0) - CAP)
    print()
    print("PER-CYCLE INPUT GROWTH:")
    for i, cycle in enumerate(cycles, 1):
        u = dict(cycle.usage)
        print(
            f"  cycle {i}: input={u.get('inputTokens')} "
            f"output={u.get('outputTokens')} total={u.get('totalTokens')}"
        )


if __name__ == "__main__":
    main()
