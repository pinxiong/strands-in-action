"""E5: a cycle is unbounded by default; a cap turns it into FAILED.

Usage (from usecases/07-graph):
    ../../.venv/bin/python src/graph_limits.py --mode unbounded
    ../../.venv/bin/python src/graph_limits.py --mode capped

`GraphBuilder._validate_graph` warns when neither limit is set. `GraphState.
should_continue` only stops when one of them is configured.

The unbounded mode does two things, because a graph with no limit at all would
never terminate: it builds one with no limits to capture the warning, then it
builds a second one with only a short execution_timeout and runs it to show the
cycle never converges on its own. Both halves are reported. stdout is raw evidence.

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strands.multiagent.graph import GraphBuilder

from src.common import (
    NodeRecorder,
    emit,
    node_agents,
    reset_ledger,
    summarize,
)

PROMPTS = {
    "ping": "Reply with exactly: PING. Do not call any tool.",
    "pong": "Reply with exactly: PONG. Do not call any tool.",
}

MAX = 6


def always(state, *, invocation_state, **kwargs) -> bool:
    """A pure Python predicate: routing here never needs the model."""
    return True


def build(mode: str, recorder: NodeRecorder):
    agents, counters = node_agents(PROMPTS, [])
    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    gb.add_edge("ping", "pong")
    gb.add_edge("pong", "ping", condition=always)
    gb.set_entry_point("ping")
    gb.set_hook_providers([recorder])
    if mode == "capped":
        gb.set_max_node_executions(MAX)
    elif mode == "timeout_only":
        gb.set_execution_timeout(6)
    # mode == "no_limits": set neither, on purpose.
    return agents, counters, gb


def run(mode: str) -> None:
    reset_ledger()
    recorder = NodeRecorder()
    evidence_name = f"graph-limits-{mode}"
    extra: dict = {"mode": mode}

    if mode == "unbounded":
        # Half 1: no limits at all. Build only, never run.
        no_limit_recorder = NodeRecorder()
        _, _, gb_nolimit = build("no_limits", no_limit_recorder)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            gb_nolimit.build()
            extra["no_limits_build_warnings"] = [str(w.message) for w in caught]
        extra["no_limits_run"] = "not executed: with no cap the cycle never terminates"

        # Half 2: only a timeout, so we can observe the cycle keep bouncing.
        mode = "timeout_only"

    agents, counters, gb = build(mode, recorder)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        extra["build_warnings"] = [str(w.message) for w in caught]
        result = graph("Bounce between the two nodes.")
        extra["run_warnings"] = [str(w.message) for w in caught]

    extra["max_node_executions"] = MAX if mode == "capped" else None
    extra["execution_timeout"] = 6 if mode == "timeout_only" else None
    extra["node_executions"] = len(result.execution_order)

    record = summarize(result, agents, counters, recorder, extra=extra)
    emit(evidence_name, record)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["unbounded", "capped"], required=True)
    run(ap.parse_args().mode)
