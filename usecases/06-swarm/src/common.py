"""Shared bench for UC06: one task, three roles, fixed input.

Everything the article says about a swarm run has to come out of a run of this
file's helpers, so the fixture data is fixed here and never generated:

    per_node_tokens   [1180, 940, 1520]     total 3640
    price_per_1k      0.0008                cost  0.002912

The three roles are the shared bench from PLAN.md section 3.2, so UC07-UC09 can
run the same task and their traces stay comparable.

strands-agents 1.63.0, amazon.nova-pro-v1:0, us-east-1.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from strands import Agent, tool
from strands.hooks import (
    AfterModelCallEvent,
    AfterNodeCallEvent,
    BeforeNodeCallEvent,
    BeforeToolCallEvent,
    HookProvider,
)
from strands.models import BedrockModel

MODEL_ID = "amazon.nova-pro-v1:0"
REGION = "us-east-1"
FIXTURE = Path(__file__).resolve().parent.parent / "data" / "brief-input.json"

# Tool side effects land here. A node that never ran leaves no entry.
LEDGER: list[dict] = []


def model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, region_name=REGION)


def reset_ledger() -> None:
    LEDGER.clear()


@tool
def read_brief_input() -> str:
    """Read the fixed brief input: topic, raw points and the per-node token counts."""
    return FIXTURE.read_text()


@tool
def sum_tokens(counts: list[int]) -> str:
    """Add the per-node token counts and price the total.

    Args:
        counts: Token counts, one per node.
    """
    data = json.loads(FIXTURE.read_text())
    total = sum(counts)
    cost = round(total / 1000 * data["price_per_1k_tokens"], 6)
    LEDGER.append({"tool": "sum_tokens", "t": time.time(), "total": total})
    return json.dumps({"total": total, "cost_usd": cost})


@tool
def save_draft(text: str) -> str:
    """Save the final brief. This is the only tool that writes the deliverable.

    Args:
        text: The finished brief.
    """
    words = len(text.split())
    LEDGER.append({"tool": "save_draft", "t": time.time(), "words": words, "text": text[:400]})
    return f"saved {words} words"


@tool
def slow_step(seconds: int = 8) -> str:
    """Sleep for a while, then return. Used to blow a node timeout.

    Args:
        seconds: How long to block.
    """
    time.sleep(seconds)
    LEDGER.append({"tool": "slow_step", "t": time.time()})
    return f"slept {seconds}s"


@tool
def explode() -> str:
    """A tool that always fails. Used to inject a node-level failure."""
    LEDGER.append({"tool": "explode", "t": time.time()})
    raise RuntimeError("injected tool failure")


class ToolOrder(HookProvider):
    """Record the order a node called its tools, coordination tool included."""

    def __init__(self) -> None:
        self.order: list[str] = []

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(BeforeToolCallEvent, self._before)

    def _before(self, event) -> None:  # noqa: ANN001
        self.order.append(event.tool_use.get("name", "?"))


class ModelCalls(HookProvider):
    """Count how many times one node's agent called the model."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(AfterModelCallEvent, self._on_call)

    def _on_call(self, event) -> None:  # noqa: ANN001
        self.calls += 1


class NodeRecorder(HookProvider):
    """Wall-clock start and stop of every node turn, from the swarm's own hooks."""

    def __init__(self) -> None:
        self.turns: list[dict] = []
        self._open: dict[str, float] = {}

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(BeforeNodeCallEvent, self._before)
        registry.add_callback(AfterNodeCallEvent, self._after)

    def _before(self, event) -> None:  # noqa: ANN001
        self._open[event.node_id] = time.time()
        self.turns.append({"node": event.node_id, "start": time.time()})

    def _after(self, event) -> None:  # noqa: ANN001
        for turn in reversed(self.turns):
            if turn["node"] == event.node_id and "stop" not in turn:
                turn["stop"] = time.time()
                break


class Canceller(HookProvider):
    """Cancel one node before it runs: the human intervention point of a swarm."""

    def __init__(self, target: str, message: str) -> None:
        self.target = target
        self.message = message

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event) -> None:  # noqa: ANN001
        if event.node_id == self.target:
            event.cancel_node = self.message


def node_agents(instructions: dict[str, str], tools: list, descriptions: dict[str, str] | None = None):
    """Build one agent per role, each counting its own model calls."""
    counters: dict[str, ModelCalls] = {}
    agents: dict[str, Agent] = {}
    for name, prompt in instructions.items():
        counter = ModelCalls(name)
        counters[name] = counter
        agents[name] = Agent(
            model=model(),
            tools=tools,
            system_prompt=prompt,
            name=name,
            description=(descriptions or {}).get(name, ""),
            hooks=[counter],
            callback_handler=None,
        )
    return agents, counters


def first_input(agent: Agent, limit: int = 700) -> str:
    """The first block of an agent's message list: the context the swarm fed it."""
    if not agent.messages:
        return "<no messages>"
    content = agent.messages[0].get("content", [])
    texts = [block.get("text", "") for block in content if isinstance(block, dict)]
    text = "\n".join(t for t in texts if t)
    return text[:limit] + ("..." if len(text) > limit else "")


def overlaps(turns: list[dict]) -> list[tuple[str, str]]:
    """Pairs of node turns whose wall-clock intervals intersect."""
    pairs = []
    closed = [t for t in turns if "start" in t and "stop" in t]
    for i, a in enumerate(closed):
        for b in closed[i + 1 :]:
            if a["start"] < b["stop"] and b["start"] < a["stop"]:
                pairs.append((a["node"], b["node"]))
    return pairs
