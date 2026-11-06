"""E1: does a session survive a process restart?

Run twice as two separate OS processes against the same session id.
First run tells the agent a name and a number, then lists every file the
FileSessionManager wrote to disk. Second run starts a brand new Agent
against the same session id and asks for the name back. No code carries
the fact across; only the files on disk do. Runs against
amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os
import sys

from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "sessions_tmp")
SESSION_ID = "restart-demo"


def show_tree() -> None:
    print("FILES_ON_DISK:")
    for root, _dirs, files in os.walk(STORAGE_DIR):
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, STORAGE_DIR)
            print(f"  {rel}  ({os.path.getsize(path)} bytes)")


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "first"
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
    )
    session_manager = FileSessionManager(
        session_id=SESSION_ID, storage_dir=STORAGE_DIR
    )
    agent = Agent(model=model, session_manager=session_manager, callback_handler=None)

    if phase == "first":
        reply = agent("My name is Pin and my favorite number is 42. "
                      "Just acknowledge, one short sentence.")
        print("PHASE       : first (fresh process, fresh session)")
        print("REPLY       :", str(reply).replace("\n", " ")[:200])
        print("MSG_COUNT   :", len(agent.messages))
        show_tree()
    else:
        reply = agent("What is my name and my favorite number?")
        print("PHASE       : second (fresh process, same session id)")
        print("REPLY       :", str(reply).replace("\n", " ")[:300])
        print("MSG_COUNT   :", len(agent.messages))
        show_tree()


if __name__ == "__main__":
    main()
