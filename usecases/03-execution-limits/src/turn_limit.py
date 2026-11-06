"""E1: what a turn limit actually counts.

One tool loop, three runs, same model. Run A has no limits: the loop
ends only when the tool's own text says the batch is complete. Run B
carries limits={"turns": 3}: the loop stops at the cap with limit_turns
after three turns and three calls. Run C carries limits={"turns": 1}:
the cap cuts the loop after one turn, and no summary is ever written. A turn is one model call plus any tool
execution that follows, so a turn limit bounds model calls, not tool
invocations. Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os

from strands import Agent, tool
from strands.models import BedrockModel

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


def run(label: str, limits: dict | None) -> None:
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )
    agent = Agent(model=model, tools=[tick])
    result = agent("Record all 8 ticks using the tick tool, then summarize.", limits=limits)
    usage = dict(result.invocation_context.usage) if result.invocation_context else {}
    tool_calls = sum(
        1 for msg in agent.messages for b in msg.get("content", []) if "toolUse" in b
    )
    print(f"=== {label} ===")
    print("LIMITS      :", limits)
    print("STOP_REASON :", result.stop_reason)
    print("TURNS_TAKEN :", usage.get("turns_taken"))
    print("TOOL_CALLS  :", tool_calls)
    print("OUTPUT_TOK  :", usage.get("outputTokens"))
    print("TOTAL_TOK   :", usage.get("totalTokens"))
    print("FINAL       :", str(result).replace("\n", " ")[:200])
    print()


def main() -> None:
    run("A: no limits, the tool text is the only stop", None)
    run("B: limits turns=3, cap binds at turn 3", {"turns": 3})
    run("C: limits turns=1, cap cuts after one turn", {"turns": 1})


if __name__ == "__main__":
    main()
