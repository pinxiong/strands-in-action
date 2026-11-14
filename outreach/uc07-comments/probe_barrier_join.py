"""UC07 comment probe: how do you build a strict barrier join without touching
``state.completed_nodes``?

Question (Igor Gorovyy, AWS Builder Center, comment 3M5ikNbMc4LY4cRfLEUGvEsQH3g,
2026-11-14):
  "You pointed out that join nodes act as an OR condition and can fire multiple
   times. What is your recommended pattern for implementing a strict barrier join
   in Strands without resorting to custom state hacks inside
   state.completed_nodes?"

All cases are offline and deterministic: scripted models replace Bedrock, so no LLM
is involved. Every model call reports a fixed 100 input + 20 output = 120 tokens.
No case writes to graph.state. The cases differ in topology and in what the edge
condition reads. strands-agents 1.63.0, Python 3.11.

Shape for the "late" cases (same fan-in as the article):

    A (batch 1) ---> B (batch 2)
      \               /
       +-----------> join

Batches come from the A -> B edge, not from a wall-clock delay. B uses a fixed
0.15 s scripted delay so that when a join shares a batch with B, the completion
order is stable; without it the parallel race makes the first join sometimes see
both parents. A says "no objection"; B says "VETO". The join's decision is a plain
string test on the text it is given, and applies it through a tool standing in
for an external effect. failed_parent uses a 0.5 s delay with a 0.1 s node
timeout, which makes the SDK raise an expected timeout exception.

Cases:
  no_barrier                     no conditions; the OR fires once per arriving parent
  barrier_one_edge               condition only on B -> join; A -> join still satisfies the OR
  barrier_completed_nodes        all edges read state.completed_nodes (the article's suggestion)
  barrier_results                all edges read state.results (read-only, no state writes)
  barrier_invocation_state       all edges read invocation_state filled by AfterNodeCallEvent
  barrier_results_same_batch     barrier_results with A and B as two entry points
  single_incoming_edge           topology change: drop A -> join, keep A -> B -> join
  missing_parent                 barrier_results plus a third parent that never runs
  failed_parent                  barrier_results where B hits the SDK node timeout

Evidence: evidence/barrier-join.txt (verbatim stdout), evidence/barrier-join.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.hooks import AfterNodeCallEvent, BeforeNodeCallEvent, HookProvider
from strands.models.model import Model
from strands.multiagent.graph import GraphBuilder

# failed_parent deliberately times out; the SDK logs that expected exception at
# ERROR level. Silence only that logger so stdout stays byte-for-byte reproducible.
logging.getLogger("strands.multiagent.graph").setLevel(logging.CRITICAL)

USAGE: dict[str, int] = {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}

PARENTS = {"A", "B"}
PARENTS_WITH_MISSING = {"A", "B", "C"}

LEDGER: list[dict[str, Any]] = []
ATTEMPTS: list[dict[str, Any]] = []
CONDITION_CALLS = 0
BARRIER_SEEN: set[str] = set()

A_TEXT = "A RESULT: base case, no objection."
B_TEXT = "B RESULT: VETO - the second parent flips this decision."


def reset() -> None:
    global CONDITION_CALLS
    LEDGER.clear()
    ATTEMPTS.clear()
    BARRIER_SEEN.clear()
    CONDITION_CALLS = 0


@tool
def apply_effect(decision: str, parents: str) -> str:
    """Apply one external decision.

    Args:
        decision: The decision produced by the join.
        parents: Comma-separated parent results visible in this invocation.
    """
    ATTEMPTS.append({"decision": decision, "parents": parents})
    LEDGER.append({"decision": decision, "parents": parents})
    return f"applied {decision}"


def _text(message: Any) -> str:
    """Plain text of one message dict."""
    content = message.get("content", []) if isinstance(message, dict) else []
    out = []
    for block in content:
        if isinstance(block, dict):
            out.append(block.get("text", ""))
        elif isinstance(block, str):
            out.append(block)
    return "\n".join(out)


class TextModel(Model):
    """A model that returns one fixed text."""

    def __init__(self, name: str, text: str, sleep: float = 0.0) -> None:
        self.name = name
        self.text = text
        self.sleep = sleep
        self.calls = 0
        self.config: dict[str, Any] = {"model_id": f"scripted-{name}"}

    def get_config(self) -> dict[str, Any]:
        return dict(self.config)

    def update_config(self, **kwargs: Any) -> dict[str, Any]:
        self.config.update(kwargs)
        return dict(self.config)

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("structured output is not used in this probe")

    async def stream(self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any) -> Any:
        self.calls += 1
        if self.sleep:
            await asyncio.sleep(self.sleep)
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": self.text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": dict(USAGE), "metrics": {"latencyMs": 1}}}


class DecisionModel(Model):
    """The join: a Python string test over the input, then one tool call."""

    def __init__(self) -> None:
        self.turn = 0
        self.decision = ""
        self.parents = ""
        self.calls = 0
        self.config: dict[str, Any] = {"model_id": "scripted-join"}

    def get_config(self) -> dict[str, Any]:
        return dict(self.config)

    def update_config(self, **kwargs: Any) -> dict[str, Any]:
        self.config.update(kwargs)
        return dict(self.config)

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("structured output is not used in this probe")

    def begin_invocation(self) -> None:
        self.turn = 0
        self.decision = ""
        self.parents = ""

    async def stream(self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any) -> Any:
        self.calls += 1
        if self.turn == 0:
            node_input = ""
            for message in reversed(messages or []):
                if isinstance(message, dict) and message.get("role") == "user":
                    candidate = _text(message)
                    if "Inputs from previous nodes:" in candidate:
                        node_input = candidate
                        break
            found = re.findall(r"^From (\w+):", node_input, flags=re.MULTILINE)
            self.parents = ",".join(sorted(set(found)))
            self.decision = "veto" if "VETO" in node_input else "approve"
            self.turn = 1
            args = {"decision": self.decision, "parents": self.parents}
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": f"join-effect-{self.calls}", "name": "apply_effect"}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {"metadata": {"usage": dict(USAGE), "metrics": {"latencyMs": 1}}}
            return

        self.turn = 2
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": f"DECISION {self.decision}"}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": dict(USAGE), "metrics": {"latencyMs": 1}}}


class InvocationReset(HookProvider):
    """Tell the join's model that a fresh node invocation is starting."""

    def __init__(self, model: DecisionModel) -> None:
        self.model = model

    def register_hooks(self, registry, **kwargs: Any) -> None:  # noqa: ANN001
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event) -> None:  # noqa: ANN001
        if event.node_id == "join":
            self.model.begin_invocation()


class ParentTracker(HookProvider):
    """Record finished node ids in the caller-owned invocation_state dict."""

    def register_hooks(self, registry, **kwargs: Any) -> None:  # noqa: ANN001
        registry.add_callback(AfterNodeCallEvent, self._after)

    def _after(self, event) -> None:  # noqa: ANN001
        BARRIER_SEEN.add(event.node_id)
        if event.invocation_state is not None:
            event.invocation_state["barrier_done"] = set(BARRIER_SEEN)


def count_call() -> None:
    """Count every condition evaluation, including the ones in _build_node_input."""
    global CONDITION_CALLS
    CONDITION_CALLS += 1


def always(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    count_call()
    return True


def all_in_completed_nodes(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """The article's suggestion: read state.completed_nodes (read-only here)."""
    count_call()
    done = {n.node_id for n in state.completed_nodes}
    return PARENTS.issubset(done)


def all_in_results(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """Read only state.results, which the runtime maintains at graph.py:1177."""
    count_call()
    return PARENTS.issubset(set(state.results))


def all_in_results_with_missing(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """A barrier that waits for a parent which never runs."""
    count_call()
    return PARENTS_WITH_MISSING.issubset(set(state.results))


def all_in_invocation_state(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """Never reads graph.state: the caller-owned dict is filled by AfterNodeCallEvent."""
    count_call()
    return PARENTS.issubset(invocation_state.get("barrier_done", set()))


def node_result_text(node_result: Any) -> str:
    if node_result is None:
        return "none (join never ran)"
    inner = getattr(node_result, "result", node_result)
    message = getattr(inner, "message", None)
    if isinstance(message, dict):
        return _text(message).strip()
    return str(inner)[:120]


def run_case(case: str) -> dict[str, Any]:
    reset()
    failed = case == "failed_parent"
    join_model = DecisionModel()
    agents = {
        "A": Agent(model=TextModel("A", A_TEXT), name="A", callback_handler=None),
        "B": Agent(model=TextModel("B", B_TEXT, sleep=0.5 if failed else 0.15), name="B", callback_handler=None),
        "C": Agent(model=TextModel("C", "C RESULT: never scheduled."), name="C", callback_handler=None),
        "join": Agent(model=join_model, tools=[apply_effect], name="join", callback_handler=None),
    }

    same_batch = case == "barrier_results_same_batch"
    single_edge = case == "single_incoming_edge"
    missing = case == "missing_parent"
    condition = {
        "no_barrier": always,
        "barrier_one_edge": all_in_results,
        "barrier_completed_nodes": all_in_completed_nodes,
        "barrier_results": all_in_results,
        "barrier_invocation_state": all_in_invocation_state,
        "barrier_results_same_batch": all_in_results,
        "single_incoming_edge": None,
        "missing_parent": all_in_results_with_missing,
        "failed_parent": all_in_results,
    }[case]

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)

    if same_batch:
        gb.add_edge("A", "join", condition=condition)
        gb.add_edge("B", "join", condition=condition)
        gb.set_entry_point("A")
        gb.set_entry_point("B")
    elif single_edge:
        gb.add_edge("A", "B")
        gb.add_edge("B", "join")
        gb.set_entry_point("A")
    elif missing:
        gb.add_edge("A", "B")
        gb.add_edge("A", "join", condition=condition)
        gb.add_edge("B", "join", condition=condition)
        gb.add_edge("C", "join", condition=condition)
        gb.set_entry_point("A")
    else:
        gb.add_edge("A", "B")
        gb.add_edge("A", "join", condition=always if case == "barrier_one_edge" else condition)
        gb.add_edge("B", "join", condition=condition)
        gb.set_entry_point("A")

    gb.set_max_node_executions(10)
    if failed:
        gb.set_node_timeout(0.1)
    hooks: list[HookProvider] = [InvocationReset(join_model)]
    if case == "barrier_invocation_state":
        hooks.append(ParentTracker())
    gb.set_hook_providers(hooks)

    graph = gb.build()
    invocation_state: dict[str, Any] = {}
    task = "One task, one early parent, one late parent, one join."
    try:
        result = graph(task, invocation_state)
        status_text = str(result.status)
        execution_order = [n.node_id for n in result.execution_order]
        join_result = result.results.get("join")
        completed_nodes = result.completed_nodes
        execution_count = result.execution_count
    except Exception as exc:  # noqa: BLE001
        if not failed:
            raise
        st = graph.state
        status_text = f"{type(exc).__name__}: {exc}"
        execution_order = [n.node_id for n in st.execution_order]
        join_result = st.results.get("join")
        completed_nodes = len(st.completed_nodes)
        execution_count = st.execution_count

    return {
        "case": case,
        "status": status_text,
        "execution_order": execution_order,
        "join_invocations": len(ATTEMPTS),
        "parent_sets": [a["parents"] for a in ATTEMPTS],
        "decisions": [a["decision"] for a in ATTEMPTS],
        "effects_written": len(LEDGER),
        "effect_ledger": list(LEDGER),
        "final_join_result_text": node_result_text(join_result),
        "condition_calls": CONDITION_CALLS,
        "barrier_done": sorted(invocation_state.get("barrier_done", set())),
        "completed_nodes": completed_nodes,
        "execution_count": execution_count,
        "results_keys": sorted(graph.state.results),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cases",
        default=(
            "no_barrier,barrier_one_edge,barrier_completed_nodes,barrier_results,"
            "barrier_invocation_state,barrier_results_same_batch,single_incoming_edge,missing_parent,failed_parent"
        ),
    )
    args = ap.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    here = Path(__file__).resolve().parent
    evidence_dir = here / "evidence"
    if not evidence_dir.is_dir():
        evidence_dir.mkdir(parents=True)
    lines: list[str] = []
    records: list[dict[str, Any]] = []
    lines.append("strands-agents 1.63.0 | scripted models, no LLM | 100 input + 20 output = 120 tokens per model call")
    lines.append("graph.py:1021-1038 _is_node_ready_with_conditions is an OR over edges in the completed batch")
    lines.append("graph.py:1177      state.results[node.node_id] = node_result (runtime-owned, no case writes it)")
    lines.append("graph.py:1286-1293 _build_node_input also calls should_traverse")
    lines.append("")

    for case in cases:
        r = run_case(case)
        records.append(r)
        lines.append(f"CASE {case}")
        lines.append(f"  status: {r['status']}")
        lines.append(f"  execution_order: {r['execution_order']}")
        lines.append(f"  join_invocations: {r['join_invocations']}")
        lines.append(f"  parent_sets: {r['parent_sets']}")
        lines.append(f"  decisions: {r['decisions']}")
        lines.append(f"  effects_written: {r['effects_written']}")
        lines.append(f"  effect_ledger: {r['effect_ledger']}")
        lines.append(f"  final_join_result_text: {r['final_join_result_text']}")
        lines.append(f"  condition_calls: {r['condition_calls']}")
        lines.append(f"  barrier_done: {r['barrier_done']}")
        lines.append(f"  completed_nodes: {r['completed_nodes']}")
        lines.append(f"  execution_count: {r['execution_count']}")
        lines.append(f"  results_keys: {r['results_keys']}")
        lines.append("")

    text = "\n".join(lines)
    (evidence_dir / "barrier-join.txt").write_text(text, encoding="utf-8")
    (evidence_dir / "barrier-join.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(text, end="" if text.endswith("\n") else "\n")


if __name__ == "__main__":
    main()
