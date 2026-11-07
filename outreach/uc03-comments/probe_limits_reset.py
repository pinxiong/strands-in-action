"""E3: limits reset per top-level call; result.invocation_context continues the budget."""
import os, json
from strands import Agent, tool
from strands.models import BedrockModel


@tool
def tick(n: int) -> str:
    """Record one tick of a batch job.

    Args:
        n: tick number being recorded.
    """
    return f"Recorded tick {n}."


def brief(label, result):
    ctx = result.invocation_context
    usage = dict(ctx.usage) if ctx is not None else {}
    print(f"{label}: stop={result.stop_reason} usage={json.dumps(usage)}")


def main():
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[tick])

    r1 = agent("Call tick once with n=1.", limits={"turns": 1})
    brief("CALL_A (fresh top-level, limits turns=1)", r1)

    r2 = agent("Call tick once with n=2.", limits={"turns": 1})
    brief("CALL_B (new top-level, no context passed)", r2)

    r3 = agent("Call tick once with n=3.", invocation_context=r2.invocation_context)
    brief("CALL_C (passes result.invocation_context from B)", r3)


if __name__ == "__main__":
    main()
