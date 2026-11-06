"""E4: wall-clock deadline via agent.cancel(); cancellation is cooperative.

Two probes. Probe A cancels 3 s into a long model answer: streaming is a
cancellation-safe point, so the run ends almost at once. Probe B cancels
5 s into a tool that sleeps 20 s: a running sync tool is not interruptible,
so the loop ends only when the tool returns. Same cancel(), different
phases, different latencies. Runs against deepseek.v3.2 on Bedrock (us-east-1).
"""
import threading
import time

import os

from strands import Agent, tool
from strands.models import BedrockModel


@tool
def slow_report() -> str:
    """Generate a compliance report. Takes about twenty seconds.

    Returns:
        The report body once the batch finishes.
    """
    time.sleep(20)
    return "report ready: all checks green"


def start_watchdog(agent: Agent, delay_s: float, message: str) -> threading.Thread:
    def fire() -> None:
        time.sleep(delay_s)
        agent.cancel(message=message)

    timer = threading.Thread(target=fire, daemon=True)
    timer.start()
    return timer


def probe_stream_phase() -> None:
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model)
    start_watchdog(agent, 3.0, "Deadline of 3 s reached.")
    t0 = time.monotonic()
    result = agent("Write a 400-word essay about the history of lighthouses.")
    elapsed = time.monotonic() - t0
    print("=== A: cancel during model streaming ===")
    print("DEADLINE_S  :", 3)
    print("ELAPSED_S   :", round(elapsed, 1))
    print("STOP_REASON :", result.stop_reason)
    print("FINAL       :", str(result).replace("\n", " ")[:200])
    print()


def probe_tool_phase() -> None:
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[slow_report])
    start_watchdog(agent, 5.0, "Deadline of 5 s reached.")
    t0 = time.monotonic()
    result = agent("Generate the compliance report with slow_report, then tell me what it says.")
    elapsed = time.monotonic() - t0
    print("=== B: cancel while a sync tool is running ===")
    print("DEADLINE_S  :", 5)
    print("ELAPSED_S   :", round(elapsed, 1))
    print("STOP_REASON :", result.stop_reason)
    print("FINAL       :", str(result).replace("\n", " ")[:200])
    print()


def main() -> None:
    probe_stream_phase()
    probe_tool_phase()


if __name__ == "__main__":
    main()
