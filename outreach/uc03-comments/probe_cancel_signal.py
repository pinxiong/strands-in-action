"""Probe B variant: a cancellation-aware tool that waits on tool_context.cancel_signal."""
import threading, time, os
from strands import Agent, tool
from strands.models import BedrockModel
from strands.types.tools import ToolContext


@tool(context=True)
def slow_report(tool_context: ToolContext) -> str:
    """Generate a compliance report. Takes about twenty seconds unless cancelled."""
    got = tool_context.cancel_signal.wait(20)
    if got:
        return "aborted before doing any work: cancel signal received"
    return "report ready: all checks green"


def main():
    model = BedrockModel(model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"), region_name="us-east-1")
    agent = Agent(model=model, tools=[slow_report])

    def fire():
        time.sleep(5.0)
        agent.cancel(message="Deadline of 5 s reached.")

    threading.Thread(target=fire, daemon=True).start()
    t0 = time.monotonic()
    result = agent("Generate the compliance report with slow_report, then tell me what it says.")
    elapsed = time.monotonic() - t0

    print("ELAPSED_S   :", round(elapsed, 1))
    print("STOP_REASON :", result.stop_reason)
    for msg in agent.messages:
        for b in msg.get("content", []):
            if "toolResult" in b:
                tr = b["toolResult"]
                txt = tr["content"][0].get("text", "") if tr.get("content") else ""
                print(f"  [{tr['status']}] {txt[:120]}")


if __name__ == "__main__":
    main()
