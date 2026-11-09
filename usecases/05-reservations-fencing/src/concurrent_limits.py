"""C4: what the SDK does and does not give you when two workers call at once.

Three parts, one model (amazon.nova-pro-v1:0, us-east-1):

  part 1  one Agent instance, two threads, different prompts.
          The second call raises ConcurrencyException: an instance serializes
          its invocations (agent.py:268, ConcurrentInvocationMode.THROW default).
  part 2  one Agent instance, two threads, same prompt AND the same
          idempotency_token (agent.py:928). The duplicate does not crash and
          does not run the model twice: it waits for the inflight invocation
          and receives its cached result (_concurrency.py:183).
  part 3  two Agent instances (the multi-worker shape), one thread each,
          each invocation carrying its own limits budget. Both complete.
          Nobody shares a budget across instances.

strands-agents 1.63.0. Evidence: evidence/concurrent-limits.txt.
"""
import json
import os
import threading
import time

from strands import Agent, tool
from strands.models import BedrockModel
from strands.types.exceptions import ConcurrencyException


@tool
def tick(n: int) -> str:
    """Record one tick of a batch job.

    Args:
        n: tick number being recorded.
    """
    return f"Recorded tick {n}."


def make_agent() -> Agent:
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )
    return Agent(model=model, tools=[tick])


def invoke(agent: Agent, prompt: str, out: dict, label: str,
           limits: dict | None = None, token=None) -> None:
    kwargs = {}
    if limits is not None:
        kwargs["limits"] = limits
    if token is not None:
        kwargs["idempotency_token"] = token
    t0 = time.monotonic()
    try:
        result = agent(prompt, **kwargs)
        ctx = result.invocation_context
        out[label] = {
            "outcome": "ok",
            "stop_reason": result.stop_reason,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "usage": dict(ctx.usage) if ctx is not None else None,
        }
    except ConcurrencyException as exc:
        out[label] = {"outcome": "ConcurrencyException", "detail": str(exc)}


def main() -> None:
    model_id = os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0")

    # part 1: one instance, two concurrent callers, no token
    print(f"PART 1 one instance, two threads, different prompts; model={model_id}")
    agent = make_agent()
    out: dict = {}
    t1 = threading.Thread(target=invoke, args=(agent, "Call tick once with n=1.", out, "p1_A"))
    t2 = threading.Thread(target=invoke, args=(agent, "Call tick once with n=2.", out, "p1_B"))
    t1.start(); t2.start(); t1.join(); t2.join()
    for label in ("p1_A", "p1_B"):
        r = out[label]
        line = f"  {label}: outcome={r['outcome']}"
        if r["outcome"] == "ok":
            line += f" stop={r['stop_reason']} elapsed={r['elapsed_s']}s usage={json.dumps(r['usage'])}"
        else:
            line += f" detail={r['detail']}"
        print(line)

    # part 2: one instance, same prompt, same idempotency token
    print("PART 2 one instance, two threads, same prompt + same idempotency_token=T100")
    agent2 = make_agent()
    out2: dict = {}
    prompt = "Call tick once with n=7."
    t3 = threading.Thread(target=invoke, args=(agent2, prompt, out2, "p2_primary", None, "T100"))
    time.sleep(0.3)  # let the primary get inflight first
    t4 = threading.Thread(target=invoke, args=(agent2, prompt, out2, "p2_duplicate", None, "T100"))
    t3.start(); t4.start(); t3.join(); t4.join()
    for label in ("p2_primary", "p2_duplicate"):
        r = out2[label]
        line = f"  {label}: outcome={r['outcome']}"
        if r["outcome"] == "ok":
            line += f" stop={r['stop_reason']} elapsed={r['elapsed_s']}s usage={json.dumps(r['usage'])}"
        else:
            line += f" detail={r['detail']}"
        print(line)

    # part 3: two instances (two workers), each with its own limits budget
    print("PART 3 two instances, one thread each, each limits={'turns': 1}")
    out3: dict = {}
    ta = threading.Thread(target=invoke, args=(make_agent(), "Call tick once with n=3.", out3, "p3_A", {"turns": 1}))
    tb = threading.Thread(target=invoke, args=(make_agent(), "Call tick once with n=4.", out3, "p3_B", {"turns": 1}))
    t0 = time.monotonic()
    ta.start(); tb.start(); ta.join(); tb.join()
    wall = round(time.monotonic() - t0, 2)
    for label in ("p3_A", "p3_B"):
        r = out3[label]
        print(f"  {label}: outcome={r['outcome']} stop={r['stop_reason']} "
              f"elapsed={r['elapsed_s']}s usage={json.dumps(r['usage'])}")
    print(f"  wall_clock={wall}s (both overlapped)")

    print("VERDICT an Agent instance serializes invocations and can dedupe a repeated "
          "idempotency_token in-process; across instances each invocation carries its "
          "own limits budget, so a shared quota must live outside the SDK")


if __name__ == "__main__":
    main()
