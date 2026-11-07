"""E4b: cooperative cancellation via tool_context.cancel_signal.

Probe A: cancel 5 s into a tool that sleeps 20 s and ignores the signal.
The tool runs to completion anyway, and its success result stays in
agent.messages after the run ends `cancelled` — cancellation does not
roll the side effect back. Probe B: the same tool, but it waits on
tool_context.cancel_signal instead of sleeping. It exits at the 5 s
deadline. The decorator must opt in with @tool(context=True), or the
SDK raises ValueError when the signature takes ToolContext.
"""
import os
import threading
import time

from strands import Agent, tool
from strands.models import BedrockModel
from strands.types.tools import ToolContext


@tool
def slow_report() -> str:
    """Generate a compliance report. Takes about twenty seconds.

    Returns:
        The report body once the batch finishes.
    """
    time.sleep(20)
    return "report ready: all checks green"


@tool(context=True)
def slow_report_aware(tool_context: ToolContext) -> str:
    """Generate a compliance report. Takes about twenty seconds unless cancelled.

    Returns:
        The report body, or an abort note if the run was cancelled first.
    """
    if tool_context.cancel_signal.wait(20):
        return "aborted before doing any work: cancel signal received"
    return "report ready: all checks green"


def start_watchdog(agent: Agent, delay_s: float, message: str) -> threading.Thread:
    def fire() -> None:
        time.sleep(delay_s)
        agent.cancel(message=message)

    timer = threading.Thread(target=fire, daemon=True)
    timer.start()
    return timer


def dump_tool_results(agent: Agent) -> None:
    print("TOOL RESULTS IN agent.messages:")
    for msg in agent.messages:
        for block in msg.get("content", []):
            if "toolResult" in block:
                tr = block["toolResult"]
                text = tr["content"][0].get("text", "") if tr.get("content") else ""
                print(f"  [{tr['status']}] {text[:120]}")


def run_probe(label: str, tool_fn) -> None:
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[tool_fn])
    start_watchdog(agent, 5.0, "Deadline of 5 s reached.")
    t0 = time.monotonic()
    result = agent("Generate the compliance report, then tell me what it says.")
    elapsed = time.monotonic() - t0
    print(f"=== {label} ===")
    print("DEADLINE_S  :", 5)
    print("ELAPSED_S   :", round(elapsed, 1))
    print("STOP_REASON :", result.stop_reason)
    dump_tool_results(agent)
    print()


def main() -> None:
    run_probe("A: cancel-unaware tool (time.sleep)", slow_report)
    run_probe("B: cancel-aware tool (cancel_signal.wait)", slow_report_aware)


if __name__ == "__main__":
    main()
