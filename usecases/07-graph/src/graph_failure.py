"""E6: what a failure actually does to a Graph (measured, not assumed).

Usage (from usecases/07-graph):
    ../../.venv/bin/python src/graph_failure.py --mode raise
    ../../.venv/bin/python src/graph_failure.py --mode cancel
    ../../.venv/bin/python src/graph_failure.py --mode session

Three distinct outcomes on strands-agents 1.63.0:

  raise   A tool raising an exception does NOT fail the node. The agent finishes
          its turn normally, so the node is COMPLETED and its downstream runs.
  cancel  BeforeNodeCallEvent.cancel_node raises RuntimeError out of
          _execute_node. The whole graph aborts; no GraphResult is produced.
  session GraphBuilder.add_node rejects an Agent with a session manager.

The docstring of _find_newly_ready_nodes says failed nodes are pruned while
sibling branches continue. That path is not reached by either injected failure
in this version: graph.py's comment says "All failures ... stop graph execution"
and "Re-raise to stop graph execution (fail-fast behavior)". stdout is raw evidence.

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strands import Agent
from strands.multiagent.graph import GraphBuilder
from strands.session.file_session_manager import FileSessionManager

from src.common import (
    Canceller,
    NodeRecorder,
    emit,
    explode,
    model,
    node_agents,
    reset_ledger,
    summarize,
)

PROMPTS = {
    "bad": (
        "You are the failing branch. Call explode exactly once. "
        "If it fails, reply: BAD BRANCH FAILED."
    ),
    "good": (
        "You are the healthy branch. Do not call any tool. "
        "Reply with exactly: GOOD BRANCH DONE."
    ),
    "bad_downstream": "Reply with exactly: BAD DOWNSTREAM RAN.",
    "good_downstream": "Reply with exactly: GOOD DOWNSTREAM RAN.",
}


def run(mode: str) -> None:
    reset_ledger()
    tooling = [explode] if mode == "raise" else []
    agents, counters = node_agents(
        {k: v for k, v in PROMPTS.items() if k in ("bad", "good")}, tooling
    )
    from src.common import ModelCalls

    for name in ("bad_downstream", "good_downstream"):
        c = ModelCalls(name)
        agents[name] = Agent(
            model=model(), system_prompt=PROMPTS[name], name=name,
            callback_handler=None, hooks=[c],
        )
        counters[name] = c

    if mode == "session":
        # The Agent constructor accepts a session manager; GraphBuilder.add_node
        # is where Graph rejects it (graph.py:301-307). Test that exact boundary.
        sm = FileSessionManager(session_id="uc07-probe")
        with_session = Agent(
            model=model(), name="with_session",
            session_manager=sm, callback_handler=None,
        )
        constructor_error = "<no error raised>"
        try:
            GraphBuilder().add_node(with_session, "with_session")
        except Exception as exc:  # noqa: BLE001
            constructor_error = f"{type(exc).__name__}: {exc}"
        print(f"mode=session add_node_error={constructor_error}")
        emit("graph-failure-session", {
            "status": "construction_check",
            "execution_order": [],
            "total_nodes": 0, "completed_nodes": 0, "failed_nodes": 0,
            "execution_count": 0, "execution_time_ms": 0,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "model_calls": {}, "turns": [], "overlaps": [],
            "ledger": [], "predicate_log": [],
            "first_inputs": {}, "results_text": {},
            "extra": {
                "mode": mode,
                "checked_at": "GraphBuilder.add_node",
                "add_node_error": constructor_error,
            },
        })
        return

    recorder = NodeRecorder()
    hooks = [recorder]
    if mode == "cancel":
        hooks.append(Canceller("bad", "cancelled by a human before the node ran"))

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("bad", "bad_downstream")
    gb.add_edge("good", "good_downstream")
    gb.set_entry_point("bad")
    gb.set_entry_point("good")
    gb.set_max_node_executions(10)
    gb.set_hook_providers(hooks)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        build_warnings = [str(w.message) for w in caught]
        try:
            result = graph("Two branches. One of them fails.")
            graph_error = "<no exception>"
        except Exception as exc:  # noqa: BLE001
            result = None
            graph_error = f"{type(exc).__name__}: {exc}"
        run_warnings = [str(w.message) for w in caught]

    if result is None:
        # cancel_node aborts the entire graph. Record what actually happened
        # instead of inventing a GraphResult that never existed.
        order = [n.node_id for n in graph.state.execution_order]
        print(f"mode={mode} graph_error={graph_error}")
        emit(f"graph-failure-{mode}", {
            "status": "ABORTED_NO_RESULT",
            "execution_order": order,
            "total_nodes": 0, "completed_nodes": 0, "failed_nodes": 0,
            "execution_count": 0, "execution_time_ms": 0,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "model_calls": {name: c.calls for name, c in counters.items()},
            "turns": [], "overlaps": [], "ledger": [], "predicate_log": [],
            "first_inputs": {}, "results_text": {},
            "extra": {
                "mode": mode,
                "graph_error": graph_error,
                "result_produced": False,
                "state_execution_order": order,
                "state_failed_nodes": [n.node_id for n in graph.state.failed_nodes],
                "build_warnings": build_warnings,
                "run_warnings": run_warnings,
            },
        })
        return

    record = summarize(
        result, agents, counters, recorder,
        extra={
            "mode": mode,
            "warnings": build_warnings + run_warnings,
            "graph_error": graph_error,
            "bad_node_status": str(
                result.results["bad"].status
            ) if "bad" in (result.results or {}) else "<missing>",
            "bad_downstream_ran": "bad_downstream" in [n.node_id for n in result.execution_order],
            "good_downstream_ran": "good_downstream" in [n.node_id for n in result.execution_order],
        },
    )
    emit(f"graph-failure-{mode}", record)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["raise", "cancel", "session"], required=True)
    run(ap.parse_args().mode)

