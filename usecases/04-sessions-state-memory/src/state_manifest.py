"""E3b: pinning invariants in agent.state and injecting them as a manifest.

Same setup as E3 (SlidingWindowConversationManager(window_size=6), one
session, seven turns), with one difference: the codename also goes into
agent.state, and a BeforeInvocationEvent hook rewrites the system prompt
on every invocation with a <manifest> block built from that state.

The SDK does not do this for you: agent.state is serialized and restored
by the session manager, but it is never added to the prompt. The hook is
what turns stored state into something the model can read.

Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import glob
import json
import os

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.hooks import BeforeInvocationEvent
from strands.models import BedrockModel
from strands.session import FileSessionManager

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "sessions_tmp")
SESSION_ID = "manifest-demo"
WINDOW = 6
BASE_PROMPT = "You are a concise assistant."


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
        system_prompt=BASE_PROMPT,
        session_manager=session_manager,
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW),
        callback_handler=None,
    )

    def inject_manifest(event: BeforeInvocationEvent) -> None:
        manifest = json.dumps(agent.state.get(), sort_keys=True)
        agent.system_prompt = f"{BASE_PROMPT}\n\n<manifest>\n{manifest}\n</manifest>"

    agent.add_hook(inject_manifest, BeforeInvocationEvent)

    def turn(prompt: str) -> str:
        reply = agent(prompt)
        return str(reply).replace("\n", " ")[:160]

    print(f"WINDOW_SIZE : {WINDOW}")
    agent.state.set("profile", {"codename": "ORION"})
    r1 = turn("My codename is ORION. Acknowledge in one word.")
    print(f"TURN 1 plant   | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r1}")
    print(f"STATE_ON_DISK  | profile={agent.state.get('profile')}")
    for i in range(2, 7):
        r = turn(f"Filler turn {i}: reply with just the word ok.")
        print(f"TURN {i} filler  | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r}")
    before_ask = json.dumps(agent.messages)
    print("ORION_IN_MESSAGES_BEFORE_ASK:", "ORION" in before_ask)
    print("ROLES_BEFORE_ASK:", [m["role"] for m in agent.messages])
    r_last = turn("What is my codename? Answer with the codename only.")
    print(f"TURN 7 ask     | msgs={len(agent.messages):2d} stored={stored_message_count():2d} | {r_last}")
    print("ORION_IN_SYSTEM_PROMPT:", "ORION" in (agent.system_prompt or ""))


if __name__ == "__main__":
    main()
