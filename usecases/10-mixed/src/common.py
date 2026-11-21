"""Shared bench for UC10: three orchestrators inside one process, one fixed fixture.

UC06 (Swarm), UC07 (Graph), UC08 (Workflow) and UC09 (A2A) all ran the same
task on the same input file. UC10 runs it again so the numbers stay comparable:

    per_node_tokens   [1180, 940, 1520]     total 3640
    price_per_1k      0.0008                cost  0.002912

Three roles, one brief: researcher (read the fixture, state the points),
calculator (sum the token counts), writer (save a short brief). The question
this bench answers is what happens when a Graph, a Swarm and the vended
Workflow tool are composed in the *same* process, with no socket in between.

strands-agents 1.63.0, strands-agents-tools 0.8.11, amazon.nova-pro-v1:0 in
us-east-1, Python 3.11. Every number in the article comes out of a run of
these helpers. Nothing here is simulated.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from strands import Agent, tool
from strands.hooks import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterNodeCallEvent,
    BeforeNodeCallEvent,
    HookProvider,
)
from strands.models import BedrockModel

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data" / "brief-input.json"
EVIDENCE = ROOT / "evidence"
MODEL_ID = "amazon.nova-pro-v1:0"
REGION = "us-east-1"

# The workflow tool reads STRANDS_WORKFLOW_DIR at import time and WorkflowManager
# is a singleton that loads every *.json in that dir. Give every process its own
# dir so persisted state never leaks between experiments. Set BEFORE any import
# of strands_tools.workflow.
STATE_DIR = Path(os.environ.get("UC10_STATE_DIR") or tempfile.mkdtemp(prefix="uc10-mixed-"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["STRANDS_WORKFLOW_DIR"] = str(STATE_DIR)

# Tool side effects land here. A node/task that never ran leaves no entry.
LEDGER: list[dict] = []

# Kept references to the per-task Agents the workflow tool builds, so a probe can
# read their real accumulated_usage after the run. Keyed by task_id.
TASK_AGENTS: dict[str, Agent] = {}

# Real per-task model-call counts, recorded by an AfterModelCallEvent callback
# attached to each task Agent the workflow tool creates.
TASK_MODEL_CALLS: dict[str, int] = {}

# Wall-clock entry/exit of each workflow task. Overlapping intervals are direct
# evidence that the vended tool really ran steps in parallel.
TASK_TIMING: list[dict] = []

# Wall-clock entry/exit of Graph/Swarm node turns, from the orchestrator hooks.
NODE_TURNS: list[dict] = []

# Last run of run_brief_pipeline: lets a Graph script read the inner workflow's
# raw return + persisted state after the node's Agent has finished.
LAST_PIPELINE_RESULT: dict = {}


def model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, region_name=REGION)


def fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def reset() -> None:
    LEDGER.clear()
    TASK_AGENTS.clear()
    TASK_MODEL_CALLS.clear()
    TASK_TIMING.clear()
    NODE_TURNS.clear()
    LAST_PIPELINE_RESULT.clear()


def base(mode: str) -> dict:
    return {
        "verified_on": "2026-11-20",
        "sdk": "strands-agents 1.63.0 / strands-agents-tools 0.8.11",
        "model": "amazon.nova-pro-v1:0 (us-east-1)",
        "python": "3.11",
        "mode": mode,
        "pid": os.getpid(),
        "fixture": "data/brief-input.json (byte-identical to usecases/09-a2a)",
    }


# --------------------------------------------------------------------------
# Tools. Same three roles as UC06-UC09.
# --------------------------------------------------------------------------

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
    LEDGER.append({"tool": "sum_tokens", "t": time.time(), "total": total, "cost_usd": cost})
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
def explode() -> str:
    """A tool that always fails. Used to inject an inner failure."""
    LEDGER.append({"tool": "explode", "t": time.time()})
    raise RuntimeError("injected tool failure")


TOOLS = [read_brief_input, sum_tokens, save_draft, explode]

# One task, three roles, fixed across all nine runs (UC06-UC09 parity).
TASK = (
    "Produce the brief described in data/brief-input.json. "
    "Research first, then compute the totals, then write the brief."
)

ROLE_INSTRUCTIONS = {
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
}

# Swarm roles drive themselves with handoff_to_agent and write structured
# context into SharedContext, so E3/E7 can enumerate the final keys.
SWARM_INSTRUCTIONS = {
    "researcher": (
        "You are the researcher. Call read_brief_input, then state exactly three "
        "findings and quote the raw numbers. Then call handoff_to_agent with "
        "agent_name='calculator', put the findings in the message argument, and pass "
        "context={'raw_counts': [1180, 940, 1520], 'points_found': 3}. "
        "Do not finish your turn without handing off."
    ),
    "calculator": (
        "You are the calculator. The handoff message contains the per-node token counts. "
        "Call sum_tokens with exactly those counts, then call handoff_to_agent with "
        "agent_name='writer', put the total and the cost into the message argument, "
        "and pass context={'total': 3640, 'cost_usd': 0.002912}. "
        "Do not finish your turn without handing off."
    ),
    "writer": (
        "You are the writer. Using the handoff message, write a brief of 100 words or "
        "fewer that states the total token count and the cost in USD. Call save_draft "
        "once with the finished brief. Do not hand off to anyone."
    ),
}

# The three vended-workflow tasks (linear dependency chain). system_prompt sets
# the same role; description is the concrete instruction the task agent receives.
def _base_workflow_tasks() -> list[dict]:
    return [
        {
            "task_id": "researcher",
            "description": (
                "Call read_brief_input exactly once. State the three points in one "
                "short sentence. Do not call any other tool."
            ),
            "system_prompt": ROLE_INSTRUCTIONS["researcher"],
        },
        {
            "task_id": "calculator",
            "description": (
                "Call sum_tokens with the per-node token counts [1180, 940, 1520]. "
                "Report the total and the cost in one short sentence. "
                "Do not call any other tool."
            ),
            "system_prompt": ROLE_INSTRUCTIONS["calculator"],
            "dependencies": ["researcher"],
        },
        {
            "task_id": "writer",
            "description": (
                "Call save_draft with a brief of at most 40 words that includes the "
                "total token count and the cost in USD. Then stop."
            ),
            "system_prompt": ROLE_INSTRUCTIONS["writer"],
            "dependencies": ["calculator"],
        },
    ]


def workflow_tasks() -> list[dict]:
    """Happy path: the same three roles as Graph/Swarm."""
    return _base_workflow_tasks()


def workflow_tasks_swallowed() -> list[dict]:
    """UC08-style swallowed failure: the first task calls `explode`, whose
    RuntimeError is caught by the agent loop and returned as text. The workflow
    still sees stop_reason != 'error' and reports 100% success."""
    tasks = _base_workflow_tasks()
    tasks[0] = {
        "task_id": "researcher",
        "description": (
            "Call the explode tool exactly once. Report what happened in one short "
            "sentence. Do not call any other tool."
        ),
        "system_prompt": "You execute one deterministic step. Call the named tool once and report its result.",
    }
    return tasks


@tool
def run_brief_pipeline(mode: str = "happy") -> str:
    """Run the deterministic 3-task Workflow sub-process inside a Graph node.

    Returns the workflow tool's raw `start` result plus its persisted state as
    JSON text. The caller (a Graph node Agent) only ever sees this string.

    Args:
        mode: "happy" or "swallowed" (injects a tool-raising first task).
    """
    import json
    from strands_tools.workflow import workflow

    tasks = workflow_tasks_swallowed() if mode == "swallowed" else workflow_tasks()
    wid = f"uc10-inner-{mode}-{os.getpid()}"
    parent = Agent(
        model=model(),
        tools=TOOLS,
        system_prompt="You execute one deterministic step. Call the named tool once and report its result.",
        callback_handler=None,
    )
    workflow(action="create", workflow_id=wid, tasks=tasks, agent=parent)
    returned = workflow(action="start", workflow_id=wid, agent=parent)
    payload = {"workflow_id": wid, "inner_return": returned, "inner_state": workflow_state(wid)}
    LAST_PIPELINE_RESULT.clear()
    LAST_PIPELINE_RESULT.update(payload)
    return json.dumps(payload, default=str)


# --------------------------------------------------------------------------
# Hooks.
# --------------------------------------------------------------------------

class ModelCalls(HookProvider):
    """Count how many times one agent called the model."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(AfterModelCallEvent, self._on_call)

    def _on_call(self, event) -> None:  # noqa: ANN001
        self.calls += 1


class NodeRecorder(HookProvider):
    """Wall-clock start and stop of every Graph/Swarm node turn."""

    def register_hooks(self, registry, **kwargs) -> None:  # noqa: ANN001
        registry.add_callback(BeforeNodeCallEvent, self._before)
        registry.add_callback(AfterNodeCallEvent, self._after)

    def _before(self, event) -> None:  # noqa: ANN001
        NODE_TURNS.append({"node": event.node_id, "start": time.time()})

    def _after(self, event) -> None:  # noqa: ANN001
        for turn in reversed(NODE_TURNS):
            if turn["node"] == event.node_id and "stop" not in turn:
                turn["stop"] = time.time()
                break


def node_agents(instructions: dict[str, str], tools: list | None = None,
                descriptions: dict[str, str] | None = None):
    """Build one Agent per role, each counting its own model calls."""
    counters: dict[str, ModelCalls] = {}
    agents: dict[str, Agent] = {}
    for name, prompt in instructions.items():
        counter = ModelCalls(name)
        counters[name] = counter
        agents[name] = Agent(
            model=model(),
            tools=tools if tools is not None else TOOLS,
            system_prompt=prompt,
            name=name,
            description=(descriptions or {}).get(name, ""),
            hooks=[counter],
            callback_handler=None,
        )
    return agents, counters


def first_input(agent: Agent, limit: int = 1600) -> str:
    """The first block of an agent's message list: the exact context it was fed."""
    if not agent.messages:
        return "<no messages>"
    content = agent.messages[0].get("content", [])
    texts = [block.get("text", "") for block in content if isinstance(block, dict)]
    text = "\n".join(t for t in texts if t)
    return text[:limit] + ("..." if len(text) > limit else "")


def agent_usage(agent: Agent) -> dict:
    """Real accumulated_usage read off an Agent after its run (used for workflow tasks)."""
    metrics = getattr(agent, "event_loop_metrics", None)
    usage = getattr(metrics, "accumulated_usage", None) or {}
    return {
        "inputTokens": usage.get("inputTokens", 0),
        "outputTokens": usage.get("outputTokens", 0),
        "totalTokens": usage.get("totalTokens", 0),
    }


def usage_of(node_result) -> dict:
    """accumulated_usage from a NodeResult (Graph / Swarm)."""
    u = getattr(node_result, "accumulated_usage", {}) or {}
    return {
        "inputTokens": u.get("inputTokens", 0),
        "outputTokens": u.get("outputTokens", 0),
        "totalTokens": u.get("totalTokens", 0),
    }


# --------------------------------------------------------------------------
# Workflow probes. The vended tool builds a fresh Agent per task inside
# _create_task_agent; wrapping it lets us read usage and exact prompts. No SDK
# behaviour is changed, only observed.
# --------------------------------------------------------------------------

def install_workflow_probes() -> None:
    from strands.hooks.events import AfterModelCallEvent
    from strands_tools.workflow import WorkflowManager

    original_create = WorkflowManager._create_task_agent
    original_execute = WorkflowManager.execute_task

    def traced_create(self, task):  # noqa: ANN001
        agent = original_create(self, task)
        tid = task["task_id"]
        TASK_AGENTS[tid] = agent
        TASK_MODEL_CALLS.setdefault(tid, 0)

        def on_model_call(event, tid=tid):  # noqa: ANN001
            TASK_MODEL_CALLS[tid] = TASK_MODEL_CALLS.get(tid, 0) + 1

        agent.hooks.add_callback(AfterModelCallEvent, on_model_call)
        return agent

    def timed_execute(self, task, workflow):  # noqa: ANN001
        entry = {"task": task["task_id"], "start": time.time()}
        TASK_TIMING.append(entry)
        try:
            return original_execute(self, task, workflow)
        finally:
            entry["stop"] = time.time()

    WorkflowManager._create_task_agent = traced_create
    WorkflowManager.execute_task = timed_execute


def workflow_state(workflow_id: str) -> dict:
    path = STATE_DIR / f"{workflow_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def workflow_text(ret: dict) -> str:
    """The raw text the vended tool puts in its content list."""
    return "\n".join(
        block.get("text", "") for block in ret.get("content", []) if isinstance(block, dict)
    )


def run_workflow(workflow_id: str, tasks: list[dict], seconds: int = 90) -> dict:
    """create + start one workflow, with a wall-clock guard.

    A task that ends in `error` leaves its dependants `pending` forever and
    start_workflow loops until completed_tasks == total_tasks. The alarm makes
    that observable instead of hanging the process; the exception is swallowed
    by start_workflow's own `except Exception`, which is itself a behaviour we
    report (UC08). Returns the raw create/start dicts plus the persisted state.
    """
    import signal
    from strands_tools.workflow import workflow

    parent = Agent(
        model=model(),
        tools=TOOLS,
        system_prompt="You execute one deterministic step. Call the named tool once and report its result.",
        callback_handler=None,
    )
    created = workflow(action="create", workflow_id=workflow_id, tasks=tasks, agent=parent)

    def on_alarm(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"start_workflow did not return within {seconds}s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    started = time.time()
    try:
        returned = workflow(action="start", workflow_id=workflow_id, agent=parent)
    except Exception as exc:  # noqa: BLE001
        returned = {"status": "error", "content": [{"text": f"{type(exc).__name__}: {exc}"}]}
    finally:
        elapsed = time.time() - started
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

    text = workflow_text(returned)
    return {
        "created": created,
        "start_returned": returned,
        "start_text": text,
        "elapsed_s": round(elapsed, 2),
        "timed_out": "did not return within" in text or elapsed >= seconds - 1,
        "state": workflow_state(workflow_id),
    }


def task_usage_table() -> dict:
    """Real per-task token usage read off the kept Agent references."""
    return {tid: agent_usage(a) for tid, a in TASK_AGENTS.items()}


def task_model_calls_table() -> dict:
    return dict(TASK_MODEL_CALLS)


def task_first_prompts(limit: int = 1400) -> dict:
    """Exact first prompt each workflow task Agent received."""
    return {tid: first_input(a, limit) for tid, a in TASK_AGENTS.items()}


# --------------------------------------------------------------------------
# Evidence writer (same style as UC09: .json raw fields + .txt flattened).
# --------------------------------------------------------------------------

def emit(name: str, record: dict) -> None:
    """Write one run's raw fields to evidence/ and echo a readable stdout line."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"{name}.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    lines: list[str] = []

    def walk(prefix: str, value) -> None:  # noqa: ANN001
        if isinstance(value, dict):
            for key, item in value.items():
                walk(f"{prefix}.{key}" if prefix else key, item)
        elif isinstance(value, list):
            lines.append(f"{prefix} = {json.dumps(value, default=str)}")
        else:
            lines.append(f"{prefix} = {value}")

    walk("", record)
    text = "\n".join(lines) + "\n"
    (EVIDENCE / f"{name}.txt").write_text(text, encoding="utf-8")
    print(text, end="")
