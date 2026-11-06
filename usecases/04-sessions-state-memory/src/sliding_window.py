"""E3: a session remembers everything; the model sees a window.

One agent, one session, SlidingWindowConversationManager(window_size=6).
Turn one plants a codename. Six filler turns push it out of the window.
The final turn asks for the codename back. Two counters run side by
side: len(agent.messages), what the model can see right now, and the
message count inside the session files, what the session actually
stored. The session keeps every message; the window keeps six.
Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import glob
import json
import os

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.session import FileSessionManager

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "sessions_tmp")
SESSION_ID = "window-demo"
WINDOW = 6


def stored_message_count() -> int:
    pattern = os.path.join(
        STORAGE_DIR, f"session_{SESSION_ID}", "agents", "*", "messages", "*.json"
    )
    return len(glob.glob(pattern))


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
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW),
        callback_handler=None,
    )

    def turn(prompt: str) -> str:
        reply = agent(prompt)
        return str(reply).replace("\n", " ")[:160]

    print(f"WINDOW_SIZE : {WINDOW}")
    r1 = turn("My codename is ORION. Acknowledge in one word.")
    print(f"TURN 1 plant   | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r1}")
    for i in range(2, 7):
        r = turn(f"Filler turn {i}: reply with just the word ok.")
        print(f"TURN {i} filler  | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r}")
    r_last = turn("What is my codename?")
    print(f"TURN 7 ask     | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r_last}")

    print("ROLES_IN_WINDOW:", [m["role"] for m in agent.messages])
    codename_in_window = "ORION" in json.dumps(agent.messages)
    print("ORION_VISIBLE_TO_MODEL:", codename_in_window)


if __name__ == "__main__":
    main()
