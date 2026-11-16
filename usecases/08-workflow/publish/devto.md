---
title: "Orchestrating Agents: Less Freedom for the Model, More Certainty for You"
published: true
description: "In a Strands workflow, a Python dependency check fixes the order, but upstream results arrive as plain text. Nine real runs on strands-agents-tools 0.8.11 show a timeout that never fires, a failure reported as 100 percent success, a restart that replays zero steps, and 3944 tokens recorded only as text."
tags: ai, agents, strands, aws
canonical_url: "https://xiongpin.dev/posts/orchestrating-workflow/"
cover_image: "https://xiongpin.dev/images/orchestrating-workflow/cover-devto.png?v=1"
---

> Verified on 2026-11-16 against `strands-agents` 1.63.0, `strands-agents-tools` 0.8.11, Python 3.11 and Bedrock in `us-east-1`. Every number below came out of a run. The scripts and raw output live in <https://github.com/pinxiong/strands-in-action/tree/master/usecases/08-workflow>. The model is `amazon.nova-pro-v1:0`.

The last two posts in this series ran the same task on a swarm and on a graph. I assume you have read the UC07 trace, so I will not restate that experiment. For readers arriving here first, the fixture is one file, `brief-input.json`, holding three fictional per-node token figures. The job is to add them up with a `sum_tokens` tool and save a short brief with a `save_draft` tool. In UC06 a swarm let the model choose who ran next, because a handoff was a tool call it could decide to make. In UC07 a graph made that choice a Python predicate attached to an edge. This post takes the same fixture to the third orchestrator, the `workflow` tool from `strands-agents-tools`, where the sequence is a list you write up front.

Here is the trade in the title, stated as a mechanism. The `workflow` tool takes a list of tasks and a `dependencies` array. A task runs only when every task it depends on has reached `completed`. That check is a plain Python loop, not a model decision. You get the order, and you get it before any model call happens. What you do not get is a contract between steps: an upstream result is spliced into the next step's prompt as natural-language text, with no field, no type and no validator. Each step is still a full agent loop, and the model inside it still decides which tools to call and what words to produce.

That split is the whole design. This post walks it through source and through nine runs. Steps with no dependencies really do overlap in wall-clock time. A `timeout` you set on a task is never read. A tool that raises an exception can leave the workflow reporting 100 percent success. And the one thing the docstring promises, that you can start or resume a workflow, does not hold once any step has already completed. Two readers of earlier posts asked where replay and cost control live. `Replaying from a failed step` and `The limits that do not limit` answer both on this same fixture.

One scope note before the trace. This is the open-source Strands Agents SDK, a Python library you install and run inside your own process. The `workflow` tool is a vended tool in `strands-agents-tools`, not a hosted service or a separate orchestration engine. Bedrock supplies the model. Every run below happens in one process with two or three tasks, one model and short prompts that finish in seconds. That is a bench for inspecting a mechanism, not a sample of production traffic. The numbers describe the runtime's behaviour, not the quality of any answer.

One naming note before the source. The tool has a single entry point, `workflow(action=...)`, and the actions used below are `create`, `start`, `delete`, `pause` and `resume`. Behind them sit the functions `create_workflow`, `start_workflow`, `execute_task` and `get_ready_tasks`. I write `start` for the action and `start_workflow` for the function. The fixture chain uses the task ids `research`, `calc` and `write`. The parallel run uses `p1`, `p2` and `p3`. The two failure runs use `flaky`, `bad` and `down`. `sum_tokens`, `save_draft` and `explode` are tool names, not task ids.

## The order is yours

`create_workflow` validates a task list and writes it to a JSON file. `start` calls `get_ready_tasks` in a loop, and that function is the entire scheduler.

```python
# strands_tools/workflow.py:560-582 -- verbatim, strands-agents-tools 0.8.11
def get_ready_tasks(self, workflow: Dict) -> List[Dict]:
    """Get list of tasks that are ready to execute (dependencies satisfied)."""
    ready_tasks = []
    for task in workflow["tasks"]:
        task_id = task["task_id"]
        # Skip completed or running tasks
        if workflow["task_results"][task_id]["status"] != "pending":
            continue

        # Check dependencies
        dependencies_met = True
        if task.get("dependencies"):
            for dep_id in task["dependencies"]:
                if workflow["task_results"][dep_id]["status"] != "completed":
                    dependencies_met = False
                    break

        if dependencies_met:
            ready_tasks.append(task)

    # Sort by priority (higher priority first)
    ready_tasks.sort(key=lambda x: x.get("priority", 3), reverse=True)
    return ready_tasks
```

There is no model call in that function. A step is ready when it is `pending` and every dependency is `completed`. Priority only sorts the batch. What the model produces can change the words in a downstream prompt, but it cannot add a step, skip a dependency or reorder the ones you declared. In this one respect, the workflow tool gives you more certainty than a swarm or a graph: the shape is fixed before the first token is spent.

The three-step chain behaved exactly that way. `research -> calc -> write` produced `order=['research', 'calc', 'write']` with no overlapping intervals. The steps started at 1794798442.900, 1794798447.472 and 1794798450.747, each about 0.1 seconds after the previous one stopped. That gap is the runtime storing state between batches, not a model thinking about what to do next.

The scheduler also runs independent steps at the same time. I gave three tasks no dependencies and had each call a tool that sleeps for three seconds. All three started at 1794798454.381 and stopped within 0.3 seconds of each other, and the trace recorded three overlapping pairs: `p1/p2`, `p1/p3` and `p2/p3`. The whole run took 6.66 seconds, not the nine a serial chain would need. So `start_workflow` really does use its thread pool. A swarm in this series handed off serially; a graph ran one batch in parallel; the workflow tool does the same for any steps you leave independent.

## There is no contract to sign

The useful question is not who runs next but what a step receives. The word "workflow" suggests declared inputs and typed outputs. The tool validates almost nothing.

```python
# strands_tools/workflow.py:495-523 -- verbatim, strands-agents-tools 0.8.11
for task in tasks:
    # Validate required fields
    if not task.get("task_id"):
        return {
            "status": "error",
            "content": [{"text": "Each task must have a task_id"}],
        }
    if not task.get("description"):
        return {
            "status": "error",
            "content": [{"text": f"Task {task['task_id']} must have a description"}],
        }

    # Add default values
    enhanced_task = task.copy()
    enhanced_task.setdefault("priority", 3)
    enhanced_task.setdefault("timeout", 300)
    enhanced_task.setdefault("dependencies", [])

    # Validate dependencies
    dep_task_ids = {t.get("task_id") for t in tasks}
    for dep_id in enhanced_task["dependencies"]:
        if dep_id not in dep_task_ids:
            return {
                "status": "error",
                "content": [{"text": f"Task {task['task_id']} has invalid dependency: {dep_id}"}],
            }

    enhanced_tasks.append(enhanced_task)
```

Two required keys, three defaults and a check that each dependency names a task that exists. Because the code copies the whole dict with `task.copy()` and never rejects unknown keys, I declared `output_schema`, `returns`, `expects` and `validator` on one task. `create` returned success. All four keys were written into the persisted JSON verbatim. No code read them. The task's stored keys were `dependencies`, `description`, `expects`, `output_schema`, `priority`, `returns`, `task_id`, `timeout`, `tools` and `validator`. Declaring a schema does not create one.

What actually crosses the boundary is a string.

```python
# strands_tools/workflow.py:413-430 -- verbatim, strands-agents-tools 0.8.11
# Build context from dependent tasks
context = []
if task.get("dependencies"):
    for dep_id in task["dependencies"]:
        dep_result = workflow["task_results"].get(dep_id, {})
        if dep_result.get("status") == "completed" and dep_result.get("result"):
            # Format the dependency results
            dep_content = []
            for msg in dep_result["result"]:
                if isinstance(msg, dict) and msg.get("text"):
                    dep_content.append(msg["text"])
            if dep_content:
                context.append(f"Results from {dep_id}:\n" + "\n".join(dep_content))

# Build comprehensive task prompt with context
task_prompt = task["description"]
if context:
    task_prompt = "Previous task results:\n" + "\n\n".join(context) + "\n\nCurrent Task:\n" + task_prompt
```

The downstream step gets its own `description` prefixed with a rendered block of whatever text the upstream model emitted. Here is the exact first prompt of the `write` step in the linear run:

````text
Previous task results:
Results from calc:
The result from the sum_tokens tool is:

```json
{ "total": 3640, "cost_usd": 0.002912 }
```

Current Task:
Using the previous results, call save_draft with a brief of 100 words or fewer containing the total and the cost.
````

The `3640` in that prompt is a fictional figure from the fixture's `per_node_tokens` field, not a measurement of what this workflow consumed. I keep the two apart throughout.

I asked the upstream step to return only raw JSON. In the passthrough run it did: the downstream prompt contained `{"total": 3640, "cost_usd": 0.002912}` as a bare line. But that is a model being cooperative, not a runtime guarantee. In the linear run the same numbers arrived wrapped in prose and a Markdown code fence. In other runs the model's `<thinking>` block was part of the text. There is no place in the task dict to say "this step returns an integer", no deserialisation and no validation before the next step starts.

Two readers of the graph post asked about exactly this boundary. One wanted to know how to keep a repeated join from repeating a side effect; the other asked what happens when a late result changes a decision already produced. The graph answer was that `state.results` overwrites and there is no revision field. The workflow answer is one level earlier: there is nowhere to put a version, an idempotency key or a veto, because the only thing passed between steps is text. If you need exactly-once effects here, build an idempotency ledger yourself outside the workflow and key it to something other than a task id.

## A failure the scheduler cannot see

A task can fail in two very different ways, and the tool treats them almost oppositely.

First, let a tool raise. I gave `flaky` a tool whose body raises `RuntimeError` and made `write` depend on it. The Strands agent loop catches a tool exception and returns it to the model as text, so the model simply reported the failure in natural language. The workflow saw `stop_reason != "error"` and marked `flaky` as `completed`. `start` returned:

```text
🎉 Workflow 'wf-failure-swallowed' completed successfully! (2/2 tasks succeeded - 100.0%)
```

The downstream prompt then read `Results from flaky:` followed by a sentence explaining that `explode` had failed. `write` ran normally and called `sum_tokens`. Nothing in `task_results` says a failure occurred. The call log has one `explode` entry, but the tool does not expose that to the scheduler. An injected failure is not a failed step. This is why a validator cannot live at the workflow layer: there is no signal for it to inspect.

Second, make the model call itself fail. I set one task's `model_settings` to a model id that does not exist. Bedrock raised `ValidationException`. `execute_task` returned `status="error"`. `start_workflow` wrote `bad: error` to the state file. Its dependent `down` stayed `pending`, because `get_ready_tasks` requires every dependency to be `completed` and `error` is not `completed`. The loop then had nothing ready and nothing running. With an 18 second wall-clock guard, `start` never returned; the state file still said `status: "running"` and `down: pending` when I stopped it.

Both outcomes matter. A failure can be invisible and reported as success, or it can park the workflow in a state from which the scheduler never exits. Neither one gives you a retry point.

## Replaying from a failed step

The `start_workflow` docstring says "Start or resume workflow execution with true parallel processing". The loop that decides when it is done is this:

```python
# strands_tools/workflow.py:602-628 -- verbatim, strands-agents-tools 0.8.11
# Track completed tasks and active futures
completed_tasks = set()
active_futures = {}
total_tasks = len(workflow["tasks"])

while len(completed_tasks) < total_tasks:
    # Get all ready tasks
    ready_tasks = self.get_ready_tasks(workflow)

    # Prepare tasks for parallel submission with batching
    tasks_to_submit = []
    max_concurrent = self.task_executor.max_workers
    current_batch_size = min(len(ready_tasks), max_concurrent - len(active_futures))

    for task in ready_tasks[:current_batch_size]:
        task_id = task["task_id"]
        if task_id not in active_futures and task_id not in completed_tasks:
            # Namespace task_id with workflow_id to prevent conflicts
            namespaced_task_id = f"{workflow_id}:{task_id}"
            tasks_to_submit.append(
                (
                    namespaced_task_id,
                    self.execute_task,
                    (task, workflow),
                    {},
                )
            )
```

The loop body continues past this excerpt. Here are the lines that write a finished future back into the state and add its id to the set:

```python
# strands_tools/workflow.py:660-667 -- verbatim, strands-agents-tools 0.8.11
workflow["task_results"][task_id] = {
    **workflow["task_results"][task_id],
    "status": ("completed" if result["status"] == "success" else "error"),
    "result": content,
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "metrics": result.get("metrics"),
}
completed_tasks.add(task_id)
```

And here is the tail of every iteration:

```python
# strands_tools/workflow.py:685-688 -- verbatim, strands-agents-tools 0.8.11
self.store_workflow(workflow_id, workflow)

# Brief pause to prevent tight loop
time.sleep(0.1)
```

`completed_tasks` is a fresh empty set on every call. Its `add` calls happen only after a future submitted by this call returns, as the second block shows. A step that was already `completed` when the call began is skipped by `get_ready_tasks`, so it never produces a future and never reaches an `add`. If a workflow has any history, the set cannot reach `total_tasks`. With nothing ready and no active futures, each iteration only stores the state again and sleeps 0.1 seconds, as the third block shows. That is the spin the guard has to stop.

I tested that across three separate processes sharing one state directory. The first process only called `create`, leaving both steps `pending`. The second process loaded that JSON from disk and ran both steps in 7.75 seconds, reporting 2/2 succeeded, so file persistence itself works. The third process loaded the same, now fully `completed`, workflow and called `start` again. It did not return within 14 seconds. Its trace shows an empty execution order. Both steps were still `completed` and the workflow was still `running`. `start` is not a resume.

The two actions that sound like recovery are stubs:

```python
# strands_tools/workflow.py:1159-1162 -- verbatim, strands-agents-tools 0.8.11
elif action in ["pause", "resume"]:
    return {
        "status": "error",
        "content": [{"text": f"🚧 Action '{action}' is not yet implemented"}],
```

Both actions return the same `not yet implemented` error.

There is one more trap. Since state lives in a JSON file, editing that file looks like a way to reset a step. I ran `calc -> write` to completion, rewrote `write` back to `pending` in the JSON and called `start` again. `write` did not rerun. The call log still held exactly one `save_draft` call. The state file was overwritten back to `completed`. The call spun until the guard stopped it. `WorkflowManager` is a singleton that keeps each workflow in memory, and `store_workflow` writes that in-memory copy on every loop iteration. The file is a snapshot, not the source of truth for a running process.

So the honest answer to "which step can I replay from" is: none, through this tool. The usable recovery is `delete` followed by `create` and a fresh `start`, which reruns every step. That is where the reader's side-effect question lands with full force. A fresh run repeats `save_draft` with no idempotency key, no version of the earlier decision and no marker that a decision was revised. In my first run `save_draft` was called once with the brief built from the fixture's fictional 3640 tokens. A restart from scratch would call it again with whatever the model produces that time. If the effect is a write to an external system, the workflow tool gives you nothing to deduplicate it with.

This experiment did not test concurrent writes, a crash between the effect and the state write or a real store's deduplication semantics. It used one process and an in-memory call log. Those are the cases you would have to prove before trusting a workflow that writes anything you cannot overwrite.

## The limits that do not limit

Two readers of the swarm post asked where a cost guardrail belongs and whether a deterministic validator could check a token total and record timed-out turns separately. A reply promised to measure those counters on this same fixture in a follow-up. The graph post did not do it, so this section closes that gap for the workflow tool on the same `brief-input.json` used by UC06 and UC07.

First the boundary. `create_workflow` calls `enhanced_task.setdefault("timeout", 300)`, and nothing else in the file reads `task["timeout"]`. I declared `timeout=1` on a task that calls a tool sleeping for three seconds. It ran for 7.06 seconds and finished `completed`. The declared value is stored in the JSON, ignored by `execute_task` and never passed to the model or the agent. There is no workflow-level budget either: the persisted workflow has no `total_tokens` and no `budget` key. Both came back absent. Because no code reads the declared timeout, no task ever reaches a timed-out status. There is no timed-out turn to record separately either.

Second the accounting. Each task's `metrics` field is a string produced by `metrics_to_string()`, not a structured object. All three tasks in the `ledger` run reported `metrics_is_plain_text: true` and `metrics_has_structured_fields: false`. The token line looks like this:

```text
Tokens: in=1093, out=89, total=1182
```

For the three steps the lines were 1182, 1325 and 1437 tokens, summing to 3944. I independently summed the `usage` blocks the provider attached to each task agent's own messages and got 3944 as well. The numbers agree, but that is my arithmetic, not the tool's. To check a budget you must parse a human-readable string or read each agent's messages yourself, then add the tasks up. The fixture's `per_node_tokens` field declares 3640 fictional input tokens; the measured 3944 is what three real agent loops actually consumed. They are different things and I have kept them apart.

So on this same fixture: there is no budget checkpoint to hook, no validator step that the scheduler would treat as deterministic and no machine-readable accounting to compare against a provider bill. Every step is a full agent with its own model calls, so a "validator" you add as a task is one more LLM call whose judgment the workflow cannot verify. If you need a hard cost ceiling, it has to sit outside this tool, around the whole run.

## What surprised me

The docstring mismatch was the sharpest result. A function that says "Start or resume" cannot resume. The reason is a single line, `completed_tasks = set()`, placed outside the loop over persisted state. I expected a resume path that skips finished work and runs the rest. Instead any prior completion makes the termination condition unreachable. I had to put a wall-clock guard around `start` just to record that it never returns.

The second surprise was how quietly a failure can pass. A tool raising an exception produced a 100 percent success report, because the agent loop turned the exception into prose. The scheduler only sees a `stop_reason`. That makes "did this step succeed" a question the workflow tool cannot answer.

The third was that edits to the state file are overwritten by the running singleton. Persistence is real across processes that start fresh. It is useless as a control surface inside one.

## When not to use this

Do not use the `workflow` tool when a step's output has to be parsed as data. You get a rendered string, and the next model may phrase it differently on the next run. Put the structured handoff in your own store and pass a key.

Do not use it when you need to retry a failed step. There is no resume. The `pause` and `resume` actions are stubs. Restarting a workflow with history does not terminate. A fresh run repeats every side effect.

Do not use it when you need a hard time or cost ceiling. The per-task `timeout` is not read, and the only accounting is a text field per task.

It is a reasonable fit when the order is genuinely fixed, steps are independent enough to run in parallel and every side effect is idempotent or disposable. In that case the dependency check is cheap and honest: it is a Python loop over a list you control.

## How I measured

All numbers come from nine workflow runs and three cross-process restart phases on 2026-11-16, with `strands-agents` 1.63.0, `strands-agents-tools` 0.8.11, `amazon.nova-pro-v1:0` in `us-east-1`, Python 3.11 and one process per run. The fixture `data/brief-input.json` is byte-for-byte the UC06 and UC07 file. Token counts are from each task agent's `metrics` string and independently from the `usage` blocks in its messages, not my estimate. Wall-clock overlaps come from a wrapper around `execute_task` that records entry and exit in the same process. Each run's verbatim stdout is in `evidence/*.txt` and its raw fields in `evidence/*.json`. Model output varies between runs, so token counts and timings are observations of these runs, not benchmarks. The busy-loop runs were stopped by a wall-clock guard; the guard's exception is itself caught by `start_workflow` and appears in its return value, which is why those runs have an `error` result and a `running` state file. Every experiment has a control or a complement: the chained run against the parallel one, the swallowed failure against the real one and the fresh-process `start` against the third-process `restart`.

## Try it yourself

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/08-workflow
python3 -m venv .venv && . .venv/bin/activate
pip install strands-agents==1.63.0 strands-agents-tools==0.8.11 boto3
export AWS_DEFAULT_REGION=us-east-1
```

The full source, the fixed fixture and all raw evidence are in
<https://github.com/pinxiong/strands-in-action/tree/master/usecases/08-workflow>.
Use Python 3.11 for the venv. The scripts hard-code `us-east-1` and `amazon.nova-pro-v1:0` in `src/common.py` and pass the region explicitly to `BedrockModel`, so `AWS_DEFAULT_REGION` is only a boto3 default and cannot redirect these calls. Provide credentials through `aws configure`, `AWS_PROFILE` or environment variables. Enable model access for `amazon.nova-pro-v1:0` in that region first. Bedrock will reject the call otherwise. Then run the nine experiments:

```bash
.venv/bin/python src/wf_trace.py --mode linear
.venv/bin/python src/wf_trace.py --mode parallel
.venv/bin/python src/wf_contract.py --mode schema
.venv/bin/python src/wf_contract.py --mode passthrough
.venv/bin/python src/wf_failure.py --mode swallowed
.venv/bin/python src/wf_failure.py --mode real
.venv/bin/python src/wf_replay.py --mode manual
.venv/bin/python src/wf_limits.py --mode timeout
.venv/bin/python src/wf_limits.py --mode ledger
```

The two `wf_trace` modes produce the trace in `The order is yours`. The two `wf_contract` modes produce the schema and passthrough results in `There is no contract to sign`. The two `wf_failure` modes produce the swallowed and real failures. `wf_replay.py --mode manual` is the edited-state-file experiment in `Replaying from a failed step`, where the JSON is rewritten to `pending` by hand. The two `wf_limits` modes produce the timeout and the token accounting.

The three restart phases need a shared state directory across separate processes. `create` writes the workflow, `start` runs it in a fresh process and `restart` calls `start` on the completed one:

```bash
D=/tmp/uc08-restart-state && rm -rf "$D" && mkdir -p "$D"
UC08_STATE_DIR="$D" .venv/bin/python src/wf_restart.py --phase create
UC08_STATE_DIR="$D" .venv/bin/python src/wf_restart.py --phase start
UC08_STATE_DIR="$D" .venv/bin/python src/wf_restart.py --phase restart
```

Each script writes its own `evidence/*.txt` and `evidence/*.json`. Three runs deliberately do not terminate on their own: `wf_failure.py --mode real`, `wf_replay.py --mode manual` on its second `start` and `wf_restart.py --phase restart`. The scripts guard them with a wall-clock alarm and record the hang. Do not run those three without the guard. The exact upstream text a step receives differs between runs, so read `first_prompts` in each JSON before comparing your numbers with mine.

## Takeaways

1. The dependency graph fixes the order and is checked in Python, with no model call. Independent steps really run in parallel.
2. `create_workflow` validates two keys and a dependency id. Anything else you declare, including an output schema, is stored and ignored.
3. A downstream step receives rendered natural-language text, not typed data. Prose, thinking traces and Markdown fences all travel with it.
4. A tool exception can become prose, leaving the step `completed` and the run reporting 100 percent success. Only an `error` status changes anything.
5. An `error` step leaves its dependants `pending` forever, so the loop has nothing ready and `start_workflow` never returns. A restart stalls for a different reason: `completed_tasks` is rebuilt empty on each call.
6. `pause` and `resume` are not implemented; editing the state JSON is overwritten by the in-memory singleton. Recovery is a full delete and rerun, which repeats side effects.
7. The per-task `timeout` is never read, so no step is ever marked timed out and there is no timed-out turn to record separately. The only accounting is a human-readable metrics string. On this fixture three steps used 3944 tokens, with no workflow-level total or budget field.
8. There is no validator step and no budget checkpoint at this layer. Put structured handoffs, idempotency keys and cost ceilings outside the tool.

The order is yours. The contract, the retry and the bill are still yours too, just not in the ways the task list suggests.
