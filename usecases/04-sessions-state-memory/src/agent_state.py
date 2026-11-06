"""E2: what agent.state is, and what it refuses to hold.

agent.state is a per-agent key-value store that lives next to the
message history inside the session. This probe does three things.
First it writes a counter and reads it back inside one process. Then it
tries to store a raw Python object and shows the error, because state
must stay JSON-serializable. Run again with "second" and a fresh Agent
on the same session id reads the counter back after a full restart.
Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import os
import sys

from strands import Agent
from strands.models import BedrockModel
from strands.session import FileSessionManager

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "sessions_tmp")
SESSION_ID = "state-demo"


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
        agent.state.set("visits", 1)
        agent.state.set("user", {"name": "Pin", "plan": "pro"})
        print("PHASE       : first")
        print("VISITS      :", agent.state.get("visits"))
        print("USER        :", agent.state.get("user"))
        try:
            agent.state.set("bad", object())
        except Exception as exc:  # noqa: BLE001 - show whatever the SDK raises
            print("NON_JSON    :", type(exc).__name__, str(exc)[:120])
        # One real call so the session manager flushes state to disk.
        agent("Say ok.")
        print("MSG_COUNT   :", len(agent.messages))
    else:
        print("PHASE       : second (fresh process, same session id)")
        print("VISITS      :", agent.state.get("visits"))
        print("USER        :", agent.state.get("user"))


if __name__ == "__main__":
    main()
