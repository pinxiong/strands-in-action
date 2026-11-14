"""UC07 comment probe: does a late parent make a graph revise a decision?

Question (innokentyb, Dev.to, 2026-11-13):
  "The repeated join is a useful reminder that a graph edge can deliver at least
   once even when the routing predicate is deterministic. If that join triggers an
   external action rather than just writing a brief, I'd put the effect behind an
   idempotency key and record which parent results were present for that invocation.
   Have you tried a case where the late parent changes an already-produced decision,
   so the graph has to revise rather than repeat the effect?"

All cases are offline and deterministic: scripted models replace Bedrock, so no LLM
is involved. Every model call reports a fixed 100 input + 20 output = 120 tokens.
The four late cases share one topology and change only the key or the edge
conditions; same_batch is a two-entry-point control with a different topology.
strands-agents 1.63.0, Python 3.11.

Shape for the four "late" cases (same as the article's fan-in experiment):

    A (fast, batch 1) ---> B (slow, batch 2)
      \                     / 
       +----------------> join

A says "no objection"; B says "VETO". The join's decision is a plain string test
on the text it is given: VETO present -> veto, otherwise -> approve. The join
applies its decision through a tool, standing in for the external effect.

Cases:
  late_no_key        no idempotency key: two invocations, two conflicting effects
  late_fixed_key     one fixed key per task: the second effect is suppressed
  late_versioned_key key includes the parent set: both effects land, second is newer
  barrier_one_edge   only B->join waits for B: the A->join edge still returns True
  barrier_all_edges  both incoming edges wait for A and B in completed_nodes
  same_batch         A and B are two entry points, so both finish in one batch

Evidence: evidence/late-parent.txt (verbatim stdout), evidence/late-parent.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.hooks import BeforeNodeCallEvent, HookProvider
from strands.models.model import Model
from strands.multiagent.graph import GraphBuilder, GraphResult

USAGE: dict[str, int] = {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}

# Only real executions of the external effect land in LEDGER.
LEDGER: list[dict[str, Any]] = []
# Every attempted effect call lands here, including suppressed duplicates.
ATTEMPTS: list[dict[str, Any]] = []
# Idempotency keys already applied in this case.
SEEN: set[str] = set()

A_TEXT = "A RESULT: base case, no objection."
B_TEXT = "B RESULT: VETO - the late parent flips this decision."


def reset() -> None:
    LEDGER.clear()
    ATTEMPTS.clear()
    SEEN.clear()


@tool
def apply_effect(decision: str, parents: str, key: str) -> str:
    """Apply one external decision. Each key is applied at most once.

    Args:
        decision: The decision produced by the join.
        parents: Comma-separated parent results visible in this invocation.
        key: Idempotency key for the effect.
    """
    duplicate = key in SEEN
    ATTEMPTS.append({"key": key, "decision": decision, "parents": parents, "duplicate": duplicate})
    if duplicate:
        return "duplicate suppressed"
    SEEN.add(key)
    LEDGER.append({"key": key, "decision": decision, "parents": parents})
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
    """A model that returns one fixed text, optionally after a delay."""

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
    """The join: a Python string test over the input, then one tool call.

    Turn 0 of each node invocation parses the last user message, picks a decision,
    and calls apply_effect. Turn 1 ends the agent turn with a short text result.
    InvocationReset resets the turn counter before each join invocation.
    """

    def __init__(self, key_mode: str) -> None:
        self.key_mode = key_mode
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

    def _key(self) -> str:
        if self.key_mode == "unique":
            return f"brief-42:call-{len(ATTEMPTS) + 1}"
        if self.key_mode == "parents":
            return f"brief-42:parents={self.parents}"
        return "brief-42"

    async def stream(self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any) -> Any:
        self.calls += 1
        if self.turn == 0:
            # Find the most recent user message that carries node input text.
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
            args = {
                "decision": self.decision,
                "parents": self.parents,
                "key": self._key(),
            }
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


def always(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    return True


def wait_for_b(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """Barrier: only traverse B -> join once B is in completed_nodes."""
    return any(n.node_id == "B" for n in state.completed_nodes)


def wait_for_all_parents(state: Any, *, invocation_state: Any, **kwargs: Any) -> bool:
    """Barrier on every incoming edge: both parents must be in completed_nodes."""
    done = {n.node_id for n in state.completed_nodes}
    return {"A", "B"}.issubset(done)


def node_result_text(node_result: Any) -> str:
    inner = getattr(node_result, "result", node_result)
    message = getattr(inner, "message", None)
    if isinstance(message, dict):
        return _text(message).strip()
    return str(inner)[:120]


def run_case(case: str) -> dict[str, Any]:
    reset()
    same_batch = case == "same_batch"
    barrier_one_edge = case == "barrier_one_edge"
    barrier_all_edges = case == "barrier_all_edges"
    key_mode = {
        "late_no_key": "unique",
        "late_fixed_key": "fixed",
        "late_versioned_key": "parents",
        "barrier_one_edge": "fixed",
        "barrier_all_edges": "fixed",
        "same_batch": "fixed",
    }[case]

    join_model = DecisionModel(key_mode)
    agents = {
        "A": Agent(model=TextModel("A", A_TEXT), name="A", callback_handler=None),
        "B": Agent(model=TextModel("B", B_TEXT, sleep=0.3), name="B", callback_handler=None),
        "join": Agent(model=join_model, tools=[apply_effect], name="join", callback_handler=None),
    }

    gb = GraphBuilder()
    for name, agent in agents.items():
        gb.add_node(agent, name)
    if same_batch:
        gb.add_edge("A", "join", condition=always)
        gb.add_edge("B", "join", condition=always)
        gb.set_entry_point("A")
        gb.set_entry_point("B")
    else:
        gb.add_edge("A", "B")
        if barrier_all_edges:
            gb.add_edge("A", "join", condition=wait_for_all_parents)
            gb.add_edge("B", "join", condition=wait_for_all_parents)
        else:
            gb.add_edge("A", "join", condition=always)
            gb.add_edge("B", "join", condition=wait_for_b if barrier_one_edge else always)
        gb.set_entry_point("A")
    gb.set_max_node_executions(10)
    gb.set_hook_providers([InvocationReset(join_model)])

    graph = gb.build()
    result = graph("One task, one early parent, one late parent, one join.")

    join_nodes = [n for n in result.execution_order if n.node_id == "join"]
    join_refs = [id(n.result) for n in join_nodes]
    parents_seen = [a["parents"] for a in ATTEMPTS]
    decisions = [a["decision"] for a in ATTEMPTS]

    return {
        "case": case,
        "status": str(result.status),
        "execution_order": [n.node_id for n in result.execution_order],
        "join_invocations": len(ATTEMPTS),
        "parent_sets": parents_seen,
        "decisions": decisions,
        "effect_attempts": len(ATTEMPTS),
        "effects_written": len(LEDGER),
        "effect_ledger": list(LEDGER),
        "suppressed": [a["key"] for a in ATTEMPTS if a["duplicate"]],
        "final_join_result_text": node_result_text(result.results.get("join")),
        "join_result_refs_unique": len(set(join_refs)),
        "completed_nodes": result.completed_nodes,
        "execution_count": result.execution_count,
        "model_calls": {
            "A": agents["A"].model.calls,
            "B": agents["B"].model.calls,
            "join": join_model.calls,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cases",
        default="late_no_key,late_fixed_key,late_versioned_key,barrier_one_edge,barrier_all_edges,same_batch",
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
    lines.append("graph.py:1177      state.results[node.node_id] = node_result (last write wins)")
    lines.append("graph.py:1289-1293 _build_node_input includes only parents in state.completed_nodes")
    lines.append("GraphResult fields: " + ", ".join(sorted(f.name for f in fields(GraphResult))))
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
        lines.append(f"  effect_attempts: {r['effect_attempts']}")
        lines.append(f"  effects_written: {r['effects_written']}")
        lines.append(f"  effect_ledger: {r['effect_ledger']}")
        lines.append(f"  suppressed: {r['suppressed']}")
        lines.append(f"  final_join_result_text: {r['final_join_result_text']}")
        lines.append(f"  join_result_refs_unique: {r['join_result_refs_unique']}")
        lines.append(f"  completed_nodes: {r['completed_nodes']}")
        lines.append(f"  execution_count: {r['execution_count']}")
        lines.append(f"  model_calls: {r['model_calls']}")
        lines.append("")

    out = "\n".join(lines)
    print(out, end="")
    (here / "evidence" / "late-parent.txt").write_text(out, encoding="utf-8")
    (here / "evidence" / "late-parent.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
