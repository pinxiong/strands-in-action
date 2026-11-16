"""Shared bench for UC08: one task, three roles, fixed input.

This is the same bench as UC06 and UC07 (PLAN.md section 3.2), so the Workflow
traces stay comparable with the Swarm and Graph traces. The fixture is fixed and
never generated:

    per_node_tokens   [1180, 940, 1520]     total 3640
    price_per_1k      0.0008                cost  0.002912

Every number in the article comes out of a run of these helpers.

strands-agents 1.63.0, strands-agents-tools 0.8.11,
amazon.nova-pro-v1:0, us-east-1.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

MODEL_ID = "amazon.nova-pro-v1:0"
REGION = "us-east-1"
FIXTURE = Path(__file__).resolve().parent.parent / "data" / "brief-input.json"
EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"

# Each workflow run gets its own state directory so persisted JSON never leaks
# between runs (WorkflowManager is a singleton and loads every file in its dir).
# UC08_STATE_DIR lets the restart experiment split one workflow across two processes.
STATE_DIR = Path(os.environ.get("UC08_STATE_DIR") or tempfile.mkdtemp(prefix="uc08-workflow-"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["STRANDS_WORKFLOW_DIR"] = str(STATE_DIR)

# Tool side effects land here. A task that never ran leaves no entry.
LEDGER: list[dict] = []

# _create_task_agent is wrapped by the probe so we can read the exact prompt
# each task received. Keyed by task_id.
TASK_AGENTS: dict[str, Agent] = {}

# Wall-clock entry/exit of each task, recorded by wrapping execute_task.
TIMING: list[dict] = []


def model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, region_name=REGION)


def reset_ledger() -> None:
    LEDGER.clear()
    TASK_AGENTS.clear()
    TIMING.clear()


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
def slow_step(seconds: int = 3) -> str:
    """Sleep for a while, then return. Used to separate completion times.

    Args:
        seconds: How long to block.
    """
    time.sleep(seconds)
    LEDGER.append({"tool": "slow_step", "t": time.time(), "seconds": seconds})
    return f"slept {seconds}s"


@tool
def explode() -> str:
    """A tool that always fails. Used to inject a task-level failure."""
    LEDGER.append({"tool": "explode", "t": time.time()})
    raise RuntimeError("injected tool failure")


TOOLS = [read_brief_input, sum_tokens, save_draft, slow_step, explode]


def parent_agent() -> Agent:
    """The parent agent the workflow tool inherits its model and tools from."""
    return Agent(
        model=model(),
        tools=TOOLS,
        system_prompt="You execute one deterministic step. Call the named tool once and report its result.",
        callback_handler=None,
    )


def install_prompt_probe() -> None:
    """Keep a reference to every task agent the workflow tool creates.

    The workflow tool builds a fresh Agent per task inside _create_task_agent.
    Holding that reference lets us read agent.messages[0] afterwards: the exact
    prompt the step received, including any upstream results the runtime spliced
    into it. No SDK behaviour is changed, only observed.
    """
    from strands_tools.workflow import WorkflowManager

    original = WorkflowManager._create_task_agent

    def traced(self, task):  # noqa: ANN001
        agent = original(self, task)
        TASK_AGENTS[task["task_id"]] = agent
        return agent

    WorkflowManager._create_task_agent = traced


def install_timing_probe() -> None:
    """Record wall-clock entry/exit of every execute_task call.

    start_workflow submits ready tasks to a ThreadPoolExecutor, so overlapping
    intervals here are direct evidence that steps really ran in parallel.
    """
    from strands_tools.workflow import WorkflowManager

    original = WorkflowManager.execute_task

    def timed(self, task, workflow):  # noqa: ANN001
        entry = {"task": task["task_id"], "start": time.time()}
        TIMING.append(entry)
        try:
            return original(self, task, workflow)
        finally:
            entry["stop"] = time.time()

    WorkflowManager.execute_task = timed


def overlaps() -> list[tuple[str, str]]:
    """Pairs of tasks whose wall-clock intervals intersect."""
    pairs = []
    closed = [t for t in TIMING if "stop" in t]
    for i, a in enumerate(closed):
        for b in closed[i + 1 :]:
            if a["start"] < b["stop"] and b["start"] < a["stop"]:
                pairs.append((a["task"], b["task"]))
    return pairs


def order() -> list[str]:
    """Execution order by task start time."""
    return [t["task"] for t in sorted(TIMING, key=lambda x: x["start"])]


def first_prompt(task_id: str, limit: int = 1200) -> str:
    """The first message of one task agent: everything the step was given."""
    agent = TASK_AGENTS.get(task_id)
    if agent is None or not agent.messages:
        return "<task never ran>"
    content = agent.messages[0].get("content", [])
    texts = [b.get("text", "") for b in content if isinstance(b, dict)]
    text = "\n".join(t for t in texts if t)
    return text[:limit] + ("..." if len(text) > limit else "")


def state(workflow_id: str) -> dict:
    """Read the persisted workflow JSON verbatim."""
    path = STATE_DIR / f"{workflow_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def patch_state(workflow_id: str, changes: dict[str, str]) -> dict:
    """Manually edit persisted task statuses. This is the only replay mechanism
    the workflow tool leaves us: there is no resume action, so a failed step is
    restarted by rewriting its status in the JSON file and calling start again.
    """
    path = STATE_DIR / f"{workflow_id}.json"
    data = json.loads(path.read_text())
    for task_id, status in changes.items():
        data["task_results"][task_id]["status"] = status
        if status == "pending":
            data["task_results"][task_id]["result"] = None
    path.write_text(json.dumps(data, indent=2))
    return data


def base_record(mode: str, workflow_id: str) -> dict:
    """Common fields every evidence record carries."""
    st = state(workflow_id)
    results = st.get("task_results", {})
    return {
        "verified_on": "2026-11-16",
        "sdk": "strands-agents 1.63.0 / strands-agents-tools 0.8.11",
        "model": "amazon.nova-pro-v1:0 (us-east-1)",
        "mode": mode,
        "workflow_status": st.get("status"),
        "task_status": {k: v.get("status") for k, v in results.items()},
        "task_results": {
            k: {"status": v.get("status"), "result": v.get("result"), "metrics": v.get("metrics")}
            for k, v in results.items()
        },
        "order": order(),
        "overlaps": overlaps(),
        "timing": [
            {"task": t["task"], "start": round(t["start"], 3), "stop": round(t.get("stop", t["start"]), 3)}
            for t in TIMING
        ],
        "ledger": list(LEDGER),
        "first_prompts": {tid: first_prompt(tid) for tid in results},
    }


def run_workflow(workflow_id: str, tasks: list[dict], seconds: int = 30) -> dict:
    """Create + start one workflow, with a wall-clock guard.

    A task that ends in `error` leaves its dependants `pending` forever, and
    start_workflow loops until completed_tasks == total_tasks. The guard makes
    that observable: we record how long start took and whether it ever returned,
    instead of hanging the whole run. The exception raised by the alarm is
    swallowed by start_workflow's own `except Exception`, which is itself one of
    the behaviours this article reports.
    """
    import signal
    from strands_tools.workflow import workflow

    parent = parent_agent()
    created = workflow(action="create", workflow_id=workflow_id, tasks=tasks, agent=parent)

    def on_alarm(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"start_workflow did not return within {seconds}s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    started = time.time()
    try:
        returned = workflow(action="start", workflow_id=workflow_id, agent=parent)
        timed_out = False
    except Exception as exc:  # noqa: BLE001
        returned = {"status": "error", "content": [{"text": f"{type(exc).__name__}: {exc}"}]}
        timed_out = False
    finally:
        elapsed = time.time() - started
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

    # start_workflow catches the alarm itself, so detect the busy loop by the
    # message it wrote into its own return value.
    text = json.dumps(returned, default=str)
    busy_loop = "did not return within" in text or elapsed >= seconds - 1
    return {
        "created": created,
        "start_returned": returned,
        "elapsed_s": round(elapsed, 2),
        "busy_loop": busy_loop,
        "seconds_budget": seconds,
    }


def emit(name: str, record: dict) -> None:
    """Write one run's raw fields to evidence/ and echo a readable stdout line."""
    out = EVIDENCE / f"{name}.json"
    out.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {out.name}")
    print(f"verified_on={record['verified_on']} sdk={record['sdk']} model={record['model']}")
    print(f"mode={record['mode']} workflow_status={record['workflow_status']}")
    print(f"task_status={record['task_status']}")
    print(f"order={record['order']} overlaps={record['overlaps']}")
    print(f"ledger={record['ledger']}")
    for tid, prompt in record["first_prompts"].items():
        print(f"--- first_prompt[{tid}] ---\n{prompt}")
    for key, value in record.get("extra", {}).items():
        print(f"{key}={value}")
