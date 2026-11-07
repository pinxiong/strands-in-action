"""E1b: limits restart per top-level call; result.invocation_context continues them.

Three calls on one agent with limits={"turns": 1}. Call A and call B are
both fresh top-level calls: each gets a fresh budget and spends real
tokens before hitting the turn cap. Call C passes B's invocation_context,
so it inherits B's already-exhausted budget: it stops at limit_turns
without spending a single new token — its usage is identical to B's.
Note that limits is a per-call argument, not an Agent constructor one.
"""
import json
import os

from strands import Agent, tool
from strands.models import BedrockModel


@tool
def tick(n: int) -> str:
    """Record one tick of a batch job.

    Args:
        n: tick number being recorded.
    """
    return f"Recorded tick {n}."


def brief(label: str, result) -> None:
    ctx = result.invocation_context
    usage = dict(ctx.usage) if ctx is not None else {}
    print(f"{label}: stop={result.stop_reason} usage={json.dumps(usage)}")


def main() -> None:
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[tick])

    r1 = agent("Call tick once with n=1.", limits={"turns": 1})
    brief("CALL_A (fresh top-level, limits turns=1)        ", r1)

    r2 = agent("Call tick once with n=2.", limits={"turns": 1})
    brief("CALL_B (new top-level, no context passed)       ", r2)

    r3 = agent("Call tick once with n=3.", invocation_context=r2.invocation_context)
    brief("CALL_C (passes result.invocation_context from B)", r3)


if __name__ == "__main__":
    main()
