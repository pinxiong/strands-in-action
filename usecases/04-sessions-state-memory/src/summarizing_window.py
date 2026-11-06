"""E4: same overflow, but the window summarizes instead of dropping.

Same codename experiment as sliding_window.py, same five filler turns,
but the conversation manager is SummarizingConversationManager. That
manager never summarizes on a message count; it fires only when the
context window overflows, or proactively when projected input tokens
cross a ratio of the model's context window. Here proactive compression
is armed at 0.005% of the 300k-token window (about 15 tokens) so the
small demo conversation trips it.
The final turn asks for the codename again, and the oldest message in
the window is printed to show the summary that replaced it. Runs
against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import json
import os

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session import FileSessionManager

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "sessions_tmp")
SESSION_ID = "summary-demo"
THRESHOLD = float(os.environ.get("COMPRESSION_THRESHOLD", "0.00005"))


def main() -> None:
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )
    session_manager = FileSessionManager(
        session_id=SESSION_ID, storage_dir=STORAGE_DIR
    )
    agent = Agent(
        model=model,
        session_manager=session_manager,
        conversation_manager=SummarizingConversationManager(
            summary_ratio=0.3,
            preserve_recent_messages=2,
            proactive_compression={"compression_threshold": THRESHOLD},
        ),
        callback_handler=None,
    )
    print(f"THRESHOLD   : {THRESHOLD}")

    def turn(prompt: str) -> str:
        reply = agent(prompt)
        return str(reply).replace("\n", " ")[:160]

    r1 = turn("My codename is ORION. Acknowledge in one word.")
    print(f"TURN 1 plant   | msgs={len(agent.messages):2d} | {r1}")
    for i in range(2, 7):
        r = turn(f"Filler turn {i}: reply with just the word ok.")
        print(f"TURN {i} filler  | msgs={len(agent.messages):2d} | {r}")
    r_last = turn("What is my codename?")
    print(f"TURN 7 ask     | msgs={len(agent.messages):2d} | {r_last}")

    print("ROLES_IN_WINDOW:", [m["role"] for m in agent.messages])
    codename_in_window = "ORION" in json.dumps(agent.messages)
    print("ORION_VISIBLE_TO_MODEL:", codename_in_window)
    first_text = json.dumps(agent.messages[0])[:400] if agent.messages else ""
    print("OLDEST_MESSAGE_IN_WINDOW:", first_text)


if __name__ == "__main__":
    main()
