"""E9: can the in-process orchestrators take a remote A2AAgent as a node?

Builds one A2AAgent (which is an AgentBase, not an Agent) and tries to put it
into a Swarm, a Graph and a Workflow-style tool call. No model call is needed
for the type checks; the server exists so the card can be fetched if needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands import Agent  # noqa: E402
from strands.agent.a2a_agent import A2AAgent  # noqa: E402

from common import PORT, base, emit, reset_receipts, start_server, stop_server  # noqa: E402


def attempt(name: str, fn) -> dict:  # noqa: ANN001
    try:
        value = fn()
        return {"name": name, "outcome": "accepted", "detail": str(value)[:300]}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "outcome": "rejected", "detail": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    port = PORT + 9
    reset_receipts()
    proc = start_server("normal", port)
    record = base("swarm", port)
    try:
        remote = A2AAgent(endpoint=f"http://127.0.0.1:{port}", timeout=30)
        record["is_agent_instance"] = isinstance(remote, Agent)
        record["a2a_agent_bases"] = [c.__name__ for c in type(remote).__mro__[:4]]

        attempts = []

        def in_swarm():  # noqa: ANN202
            from strands.multiagent.swarm import Swarm

            return Swarm(nodes=[remote], entry_point=remote)

        def in_graph():  # noqa: ANN202
            from strands.multiagent.graph import GraphBuilder

            builder = GraphBuilder()
            builder.add_node(remote, "remote")
            return builder.build()

        attempts.append(attempt("Swarm(nodes=[A2AAgent])", in_swarm))
        attempts.append(attempt("GraphBuilder.add_node(A2AAgent)", in_graph))
        record["attempts"] = attempts
        emit("a2a-swarm", record)
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
