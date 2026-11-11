"""UC06 comment probe: where can a cost guardrail actually stand?

Question (Stanislav Kolenkin, AWS Builder Center, 2026-11-11):
  "A tool that keeps failing led to eleven save_draft calls and 22k tokens, and a
   timed-out node reported 0 tokens even though the model calls happened. So the
   swarm can burn budget and under-report it at the same time. In production, where
   would you put the guardrail: a token budget checked in a BeforeNodeCallEvent
   hook, a dedicated validator node before the swarm returns, or outside the swarm
   entirely, for example reconciling with Bedrock invocation logs and CloudWatch
   token metrics?"

All cases are offline and deterministic: a ScriptedModel replaces Bedrock, so no LLM
is involved. Each model call reports a fixed 100 input + 20 output = 120 tokens.
One variable changes per case. strands-agents 1.63.0, Python 3.11.

Cases:
  silent           entry node ends without a handoff; does a validator node run?
  repeat           one node turn calls save_draft four times; no tool guard
  repeat_cap       same, but BeforeToolCallEvent.cancel_tool caps executions at 2
  node_budget      BeforeNodeCallEvent hook reads the counters at each node boundary
  node_cancel      same, but the hook cancels once the counter reaches 480
  swarm_limits_kw  same as node_budget, with limits= passed to Swarm.stream_async
  timeout_tool     model stream finished (120 tokens), the tool then blocks past
                   node_timeout: what do the two counters say?
  timeout_stream   the model stream itself blocks past node_timeout
  agent_limits     standalone Agent, limits={"total_tokens": 150}: does it stop?

Evidence: evidence/guardrail-points.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from strands import Agent, tool
from strands.hooks import BeforeNodeCallEvent, BeforeToolCallEvent, HookProvider
from strands.models.model import Model
from strands.multiagent import Swarm

USAGE: dict[str, int] = {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}
LEDGER: list[str] = []


class ScriptedModel(Model):
    """A Model that replays a fixed list of turns. No network, no LLM."""

    def __init__(self, name: str, plan: list[dict[str, Any]]) -> None:
        self.name = name
        self.plan = list(plan)
        self.calls = 0
        self.config: dict[str, Any] = {"model_id": "scripted-model-1"}

    def get_config(self) -> dict[str, Any]:
        return dict(self.config)

    def update_config(self, **kwargs: Any) -> dict[str, Any]:
        self.config.update(kwargs)
        return dict(self.config)

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("structured output is not used in this probe")

    async def stream(self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any) -> Any:
        step = self.plan[min(self.calls, len(self.plan) - 1)]
        self.calls += 1
        yield {"messageStart": {"role": "assistant"}}
        if "sleep" in step:
            await asyncio.sleep(step["sleep"])
        if "tool" in step:
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {
                            "toolUseId": f"{self.name}-{self.calls}",
                            "name": step["tool"],
                        }
                    }
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step.get("args", {}))}}}}
            yield {"contentBlockStop": {}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": step.get("text", "done")}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use" if "tool" in step else "end_turn"}}
        yield {"metadata": {"usage": dict(USAGE), "metrics": {"latencyMs": 1}}}


@tool
def save_draft(text: str) -> str:
    """Save a draft. Only a real execution appends to LEDGER.

    Args:
        text: Draft text.
    """
    LEDGER.append(f"save_draft:{text}")
    return f"saved {len(text.split())} words"


@tool
def slow_step(seconds: int = 1) -> str:
    """Block long enough to blow a node timeout.

    Args:
        seconds: Seconds to sleep.
    """
    time.sleep(seconds)
    return f"slept {seconds}s"


class Boundary(HookProvider):
    """Read the two token counters at every BeforeNodeCallEvent, optionally cancel."""

    def __init__(self, cancel_at: int | None = None) -> None:
        self.cancel_at = cancel_at
        self.rows: list[dict[str, Any]] = []

    def register_hooks(self, registry: Any, **kwargs: Any) -> None:
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event: Any) -> None:
        swarm = event.source
        row = {
            "node": event.node_id,
            "swarm_totalTokens": swarm.state.accumulated_usage.get("totalTokens"),
            "hook_invocation_context": (
                "None" if getattr(event, "invocation_context", None) is None else "present"
            ),
        }
        self.rows.append(row)
        if self.cancel_at is not None and row["swarm_totalTokens"] >= self.cancel_at:
            event.cancel_node = "token budget reached"


class ToolCap(HookProvider):
    """Cancel a tool call after a fixed number of real executions."""

    def __init__(self, name: str, limit: int) -> None:
        self.name = name
        self.limit = limit
        self.attempts = 0
        self.cancelled = 0

    def register_hooks(self, registry: Any, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)

    def _before(self, event: Any) -> None:
        if event.tool_use.get("name") != self.name:
            return
        self.attempts += 1
        if self.attempts > self.limit:
            self.cancelled += 1
            event.cancel_tool = "save_draft cap reached"


def agent(name: str, plan: list[dict[str, Any]], hooks: list[Any] | None = None) -> tuple[Agent, ScriptedModel]:
    model = ScriptedModel(name, plan)
    return (
        Agent(
            model=model,
            tools=[save_draft, slow_step],
            system_prompt=f"scripted {name}",
            name=name,
            description=f"scripted {name}",
            hooks=hooks or [],
            callback_handler=None,
        ),
        model,
    )


async def collect(swarm: Swarm, task: str, **kwargs: Any) -> Any:
    result = None
    async for event in swarm.stream_async(task, **kwargs):
        if "result" in event:
            result = event["result"]
    return result


def handoff(next_node: str) -> dict[str, Any]:
    return {"tool": "handoff_to_agent", "args": {"agent_name": next_node, "message": "go"}}


def dump(label: str, payload: dict[str, Any]) -> None:
    print(f"CASE {label}")
    for key, value in payload.items():
        print(f"  {key}: {json.dumps(value, sort_keys=True)}")
    print()


async def case_silent() -> None:
    researcher, r_model = agent("researcher", [{"text": "done"}])
    validator, v_model = agent("validator", [{"text": "validated"}])
    boundary = Boundary()
    swarm = Swarm(
        nodes=[researcher, validator],
        entry_point=researcher,
        max_handoffs=6,
        max_iterations=6,
        hooks=[boundary],
    )
    result = await collect(swarm, "produce a brief")
    dump("silent", {
        "status": result.status.value,
        "node_history": [str(n) for n in result.node_history],
        "validator_status": (
            result.results["validator"].status.value if "validator" in result.results else "never ran"
        ),
        "before_node_events": [r["node"] for r in boundary.rows],
        "swarm_totalTokens": result.accumulated_usage.get("totalTokens"),
        "request_totalTokens": result.invocation_context.usage["totalTokens"],
        "researcher_model_calls": r_model.calls,
        "validator_model_calls": v_model.calls,
    })


async def case_repeat(label: str, cap: int | None) -> None:
    LEDGER.clear()
    plan = [{"tool": "save_draft", "args": {"text": f"v{i}"}} for i in range(1, 5)] + [{"text": "done"}]
    hooks = [ToolCap("save_draft", cap)] if cap is not None else []
    writer, w_model = agent("writer", plan, hooks=hooks)
    boundary = Boundary()
    swarm = Swarm(
        nodes=[writer],
        entry_point=writer,
        max_handoffs=6,
        max_iterations=6,
        hooks=[boundary],
    )
    result = await collect(swarm, "save a brief")
    tool_hook = hooks[0] if hooks else None
    dump(label, {
        "status": result.status.value,
        "node_history": [str(n) for n in result.node_history],
        "before_node_events": len(boundary.rows),
        "model_calls": w_model.calls,
        "tool_call_events": tool_hook.attempts if tool_hook else "not instrumented",
        "tool_calls_cancelled": tool_hook.cancelled if tool_hook else 0,
        "save_draft_executions": len(LEDGER),
        "save_draft_ledger": LEDGER,
        "swarm_totalTokens": result.accumulated_usage.get("totalTokens"),
        "request_totalTokens": result.invocation_context.usage["totalTokens"],
    })


async def case_node_budget(label: str, cancel_at: int | None = None, extra_kwargs: dict[str, Any] | None = None) -> None:
    plans = {
        "researcher": [handoff("calculator"), {"text": "done"}],
        "calculator": [handoff("writer"), {"text": "done"}],
        "writer": [{"text": "done"}],
    }
    agents = {name: agent(name, plan)[0] for name, plan in plans.items()}
    models = {name: a.model for name, a in agents.items()}
    boundary = Boundary(cancel_at=cancel_at)
    swarm = Swarm(
        nodes=[agents["researcher"], agents["calculator"], agents["writer"]],
        entry_point=agents["researcher"],
        max_handoffs=6,
        max_iterations=6,
        hooks=[boundary],
    )
    kwargs = dict(extra_kwargs or {})
    result = await collect(swarm, "produce a brief", **kwargs)
    dump(label, {
        "extra_kwargs": kwargs,
        "status": result.status.value,
        "node_history": [str(n) for n in result.node_history],
        "boundary_rows": boundary.rows,
        "model_calls": {name: m.calls for name, m in models.items()},
        "swarm_totalTokens": result.accumulated_usage.get("totalTokens"),
        "request_totalTokens": result.invocation_context.usage["totalTokens"],
    })


async def case_timeout(label: str, plan: list[dict[str, Any]]) -> None:
    LEDGER.clear()
    node, n_model = agent("calculator", plan)
    boundary = Boundary()
    swarm = Swarm(
        nodes=[node],
        entry_point=node,
        max_handoffs=4,
        max_iterations=4,
        node_timeout=0.25,
        hooks=[boundary],
    )
    result = await collect(swarm, "produce a brief")
    dump(label, {
        "status": result.status.value,
        "node_history": [str(n) for n in result.node_history],
        "execution_count": result.execution_count,
        "before_node_events": [r["node"] for r in boundary.rows],
        "boundary_rows": boundary.rows,
        "model_calls": n_model.calls,
        "swarm_totalTokens": result.accumulated_usage.get("totalTokens"),
        "request_totalTokens": result.invocation_context.usage["totalTokens"],
        "node_result_usage": result.results["calculator"].accumulated_usage.get("totalTokens")
        if "calculator" in result.results
        else "no node result",
    })


async def case_agent_limits() -> None:
    LEDGER.clear()
    plan = [{"tool": "save_draft", "args": {"text": f"v{i}"}} for i in range(1, 5)] + [{"text": "done"}]
    solo, s_model = agent("solo", plan)
    result = None
    async for event in solo.stream_async("save a brief", limits={"total_tokens": 150}):
        if "result" in event:
            result = event["result"]
    dump("agent_limits", {
        "stop_reason": result.stop_reason if result else "no result",
        "model_calls": s_model.calls,
        "save_draft_executions": len(LEDGER),
        "request_totalTokens": result.invocation_context.usage["totalTokens"] if result else "no result",
    })


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[
        "silent", "repeat", "repeat_cap", "node_budget", "node_cancel",
        "swarm_limits_kw", "timeout_tool", "timeout_stream", "agent_limits", "all",
    ], default="all")
    args = parser.parse_args()
    cases = {
        "silent": lambda: case_silent(),
        "repeat": lambda: case_repeat("repeat", None),
        "repeat_cap": lambda: case_repeat("repeat_cap", 2),
        "node_budget": lambda: case_node_budget("node_budget"),
        "node_cancel": lambda: case_node_budget("node_cancel", cancel_at=480),
        "swarm_limits_kw": lambda: case_node_budget(
            "swarm_limits_kw", extra_kwargs={"limits": {"total_tokens": 150}}
        ),
        "timeout_tool": lambda: case_timeout("timeout_tool", [{"tool": "slow_step", "args": {"seconds": 1}}]),
        "timeout_stream": lambda: case_timeout("timeout_stream", [{"sleep": 1.0}]),
        "agent_limits": lambda: case_agent_limits(),
    }
    selected = cases.keys() if args.case == "all" else [args.case]
    for name in selected:
        await cases[name]()


if __name__ == "__main__":
    asyncio.run(main())
