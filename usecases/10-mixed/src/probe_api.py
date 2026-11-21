"""Local construction probe: no Bedrock call, verifies the composition API.

Run once before the nine experiments. Confirms what the installed SDK accepts
as a Graph node and how the vended workflow tool is wired. Results are printed,
not written to evidence (this is a smoke test, not a measured run).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.base import MultiAgentBase
from strands.multiagent.graph import GraphBuilder

from common import TOOLS, model


def main() -> None:
    def agent(name: str) -> Agent:
        return Agent(model=model(), tools=TOOLS, name=name,
                     system_prompt="x", callback_handler=None)

    swarm = Swarm(
        nodes=[agent("r"), agent("c"), agent("w")],
        entry_point=None,
        max_handoffs=6,
        max_iterations=6,
    )
    print("swarm isinstance MultiAgentBase:", isinstance(swarm, MultiAgentBase))
    print("swarm has _session_manager attr:", hasattr(swarm, "_session_manager"))
    print("swarm.id:", swarm.id)
    print("swarm shared_context.context keys:", list(swarm.shared_context.context.keys()))

    gb = GraphBuilder()
    gb.add_node(swarm, "swarm_node")
    gb.add_node(agent("calc"), "calc")
    gb.add_node(agent("writer"), "writer")
    gb.add_edge("swarm_node", "calc")
    gb.add_edge("calc", "writer")
    gb.set_entry_point("swarm_node")
    gb.set_max_node_executions(10)
    graph = gb.build()
    print("GraphBuilder.add_node(Swarm) accepted, node_ids:", sorted(graph.nodes.keys()))
    print("nested node executor type:", type(graph.nodes["swarm_node"].executor).__name__)

    # A2A-style / workflow-tool-as-node check: workflow is a @tool function,
    # not an AgentBase/MultiAgentBase, so it can never be a graph node directly.
    from strands_tools.workflow import workflow
    print("workflow object type:", type(workflow).__name__)
    print("workflow isinstance MultiAgentBase:", isinstance(workflow, MultiAgentBase))
    print("workflow has TOOL_SPEC:", hasattr(workflow, "TOOL_SPEC"))
    try:
        gb2 = GraphBuilder()
        gb2.add_node(workflow, "wf_node")
        print("add_node(workflow) accepted (unexpected)")
    except Exception as exc:  # noqa: BLE001
        print("add_node(workflow) rejected:", type(exc).__name__, str(exc)[:120])

    # condition predicate signature detection (graph._is_context_condition)
    from strands.multiagent.graph import _is_context_condition
    def legacy(state):
        return True
    def contextual(state, *, invocation_state, **kwargs):
        return True
    print("legacy predicate is context condition:", _is_context_condition(legacy))
    print("contextual predicate is context condition:", _is_context_condition(contextual))


if __name__ == "__main__":
    main()
