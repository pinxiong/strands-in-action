"""E4: a token limit is checked between turns, so it is soft twice over.

Probe A is a single-turn answer with limits={"output_tokens": 80}: the
model's response ends the loop with end_turn before any check runs, so
the cap is never enforced at all. Probe B is the same tick tool loop
with limits={"output_tokens": 100}: the check runs at the start of each
turn, so the loop stops on the first boundary after cumulative output
passes the cap, overshooting by part of one response. Runs against
amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os

from strands import Agent, tool
from strands.models import BedrockModel

SINGLE_CAP = 80
LOOP_CAP = 100
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


def make_model() -> BedrockModel:
    return BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )


def probe_single_turn() -> None:
    agent = Agent(model=make_model())
    result = agent(
        "Write a 200-word explanation of how ocean tides work.",
        limits={"output_tokens": SINGLE_CAP},
    )
    usage = dict(result.invocation_context.usage) if result.invocation_context else {}
    output = usage.get("outputTokens") or 0
    print("=== A: single-turn answer, cap never checked ===")
    print("CAP         :", SINGLE_CAP)
    print("STOP_REASON :", result.stop_reason)
    print("OUTPUT_TOK  :", output)
    print("OVERSHOOT   :", output - SINGLE_CAP)
    print("TURNS_TAKEN :", usage.get("turns_taken"))
    print()


def probe_tool_loop() -> None:
    agent = Agent(model=make_model(), tools=[tick])
    result = agent(
        "Record all 8 ticks using the tick tool, then summarize.",
        limits={"output_tokens": LOOP_CAP},
    )
    usage = dict(result.invocation_context.usage) if result.invocation_context else {}
    output = usage.get("outputTokens") or 0
    print("=== B: tool loop, cap binds at the next boundary ===")
    print("CAP         :", LOOP_CAP)
    print("STOP_REASON :", result.stop_reason)
    print("OUTPUT_TOK  :", output)
    print("OVERSHOOT   :", output - LOOP_CAP)
    print("TURNS_TAKEN :", usage.get("turns_taken"))
    print("TOTAL_TOK   :", usage.get("totalTokens"))
    print()


def main() -> None:
    probe_single_turn()
    probe_tool_loop()


if __name__ == "__main__":
    main()
