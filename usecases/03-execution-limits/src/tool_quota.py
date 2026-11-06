"""E5: a per-tool quota with a BeforeToolCallEvent hook.

The hook counts calls to `tick` per request. After two calls it sets
`cancel_tool`, which turns every further call into an error result the
model can read. The loop itself keeps running until the model gives up
and wraps up: a quota bounds the tool, it does not stop the loop.
Runs against deepseek.v3.2 on Bedrock (us-east-1).
"""
from collections import defaultdict

import os

from strands import Agent, tool
from strands.hooks import BeforeToolCallEvent
from strands.models import BedrockModel

QUOTA = 2
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
    attempted: dict[str, int] = defaultdict(int)
    blocked: dict[str, int] = defaultdict(int)

    def quota(event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        attempted[name] += 1
        if attempted[name] > QUOTA:
            blocked[name] += 1
            event.cancel_tool = (
                f"quota exceeded: {name} allows {QUOTA} calls per request, "
                f"this was attempt {attempted[name]}"
            )

    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[tick])
    agent.add_hook(quota, BeforeToolCallEvent)

    result = agent("Record all 8 ticks using the tick tool, then summarize.")

    executed = sum(
        1
        for msg in agent.messages
        for b in msg.get("content", [])
        if "toolResult" in b and b["toolResult"]["status"] == "success"
    )
    print("QUOTA       :", QUOTA)
    print("ATTEMPTED   :", dict(attempted))
    print("BLOCKED     :", dict(blocked))
    print("EXECUTED_OK :", executed)
    print("STOP_REASON :", result.stop_reason)
    print("FINAL       :", str(result).replace("\n", " ")[:300])
    print()
    print("TOOL RESULTS SEEN BY THE MODEL:")
    for msg in agent.messages:
        for b in msg.get("content", []):
            if "toolResult" in b:
                tr = b["toolResult"]
                text = tr["content"][0].get("text", "") if tr.get("content") else ""
                print(f"  [{tr['status']}] {text[:100]}")


if __name__ == "__main__":
    main()
