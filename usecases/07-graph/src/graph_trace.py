"""E1/E2: a three-node chain, and a conditional fork whose predicates read model text.

Usage (from usecases/07-graph):
    ../../.venv/bin/python src/graph_trace.py --mode linear
    ../../.venv/bin/python src/graph_trace.py --mode condition

Every number printed here comes out of a real Bedrock run. stdout is the raw evidence.
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
    LEDGER,
    PREDICATE_LOG,
    ModelCalls,
    NodeRecorder,
    emit,
    model,
    node_agents,
    reset_ledger,
    summarize,
)
from strands import Agent

INSTRUCTIONS = {
    "researcher": (
        "You are the researcher. Call read_brief_input exactly once. "
        "Then state the three points in one short sentence. "
        "Do not call any other tool and do not write a brief."
    ),
    "calculator": (
        "You are the calculator. Call sum_tokens with the per-node token counts "
        "[1180, 940, 1520]. Then report the total and the cost in one short sentence. "
        "Do not call any other tool."
    ),
    "writer": (
        "You are the writer. Call save_draft with a brief of at most 40 words that "
        "includes the total token count and the cost in USD. Then stop."
    ),
    "fallback": "Reply with exactly: NO TOTAL IN UPSTREAM TEXT. Do not call any tool.",
}

TOOLS = ["read_brief_input", "sum_tokens", "save_draft", "slow_step", "explode"]

# Imported lazily so the module works when a mode needs no tools.
from src.common import explode, read_brief_input, save_draft, slow_step, sum_tokens  # noqa: E402

TOOL_OBJECTS = [read_brief_input, sum_tokens, save_draft, slow_step, explode]

# Set in run() so a predicate can snapshot how many model calls have happened
# at the exact moment routing is decided. This is the direct evidence for F1.
_COUNTERS: dict = {}


def _model_call_snapshot() -> dict:
    return {name: c.calls for name, c in _COUNTERS.items()}


def condition_true(state, *, invocation_state, **kwargs) -> bool:
    """A pure Python predicate. It reads the text the model produced upstream."""
    text = " ".join(str(nr) for nr in (state.results or {}).values())
    hit = "3640" in text
    PREDICATE_LOG.append(
        {
            "edge": "calculator->writer",
            "expect": "3640 in upstream text",
            "hit": hit,
            "completed": sorted(n.node_id for n in state.completed_nodes),
            "upstream_excerpt": text[:160],
            "model_calls_at_eval": _model_call_snapshot(),
        }
    )
    return hit


def condition_false(state, *, invocation_state, **kwargs) -> bool:
    """Complement of condition_true: exactly one of the two edges can fire."""
    text = " ".join(str(nr) for nr in (state.results or {}).values())
    hit = "3640" not in text
    PREDICATE_LOG.append(
        {
            "edge": "calculator->fallback",
            "expect": "3640 not in upstream text",
            "hit": hit,
            "completed": sorted(n.node_id for n in state.completed_nodes),
            "upstream_excerpt": text[:160],
            "model_calls_at_eval": _model_call_snapshot(),
        }
    )
    return hit


def run(mode: str) -> None:
    reset_ledger()
    agents, counters = node_agents(
        {k: v for k, v in INSTRUCTIONS.items() if k != "fallback"}, TOOL_OBJECTS
    )
    fallback_counter = ModelCalls("fallback")
    agents["fallback"] = Agent(
        model=model(),
        system_prompt=INSTRUCTIONS["fallback"],
        name="fallback",
        callback_handler=None,
        hooks=[fallback_counter],
    )
    counters["fallback"] = fallback_counter
    _COUNTERS.clear()
    _COUNTERS.update(counters)

    recorder = NodeRecorder()
    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)

    if mode == "linear":
        gb.add_edge("researcher", "calculator")
        gb.add_edge("calculator", "writer")
    else:
        gb.add_edge("researcher", "calculator")
        gb.add_edge("calculator", "writer", condition=condition_true)
        gb.add_edge("calculator", "fallback", condition=condition_false)

    gb.set_entry_point("researcher")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([recorder])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = gb.build()
        build_warnings = [str(w.message) for w in caught]
        result = graph(
            "Produce the brief described in data/brief-input.json. "
            "Research first, then compute the totals, then write the brief."
        )
        run_warnings = [str(w.message) for w in caught]

    record = summarize(
        result,
        agents,
        counters,
        recorder,
        extra={
            "mode": mode,
            "build_warnings": build_warnings,
            "run_warnings": run_warnings,
            "predicate_evals": len(PREDICATE_LOG),
        },
    )
    emit(f"graph-trace-{mode}", record)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["linear", "condition"], required=True)
    run(ap.parse_args().mode)
