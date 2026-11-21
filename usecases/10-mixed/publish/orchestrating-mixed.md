---
title: Orchestrating Agents: Three Orchestrators, One Process
description: "Three Strands orchestrators in one process do not share one context. Nine real Bedrock experiments show only text crossing the boundary, a nested failure still reported as 100.0% success and token cost rising 74.5% and 192.8% in the two mixed runs."
tags: ["ai", "agents"]
canonical: "https://xiongpin.dev/posts/orchestrating-mixed/"
cover:
  image: "cover-medium.png"
---
> Originally published on [xiongpin.dev](https://xiongpin.dev/posts/orchestrating-mixed/).

> Verified on 2026-11-20 against `strands-agents` 1.63.0,
> `strands-agents-tools` 0.8.11, Python 3.11 and Bedrock in `us-east-1`.
> Every number below came from a real run. E9 aggregates those runs. The
> scripts and raw output live in
> https://github.com/pinxiong/strands-in-action/tree/master/usecases/10-mixed.
> The model is `amazon.nova-pro-v1:0`.

This post puts a Graph, the vended Workflow tool and a Swarm in one process.
There is no socket and no second process. The task comes from the last four
posts. A fixture holds three invented per-node token counts. An agent adds them
with a `sum_tokens` tool and saves a brief with a `save_draft` tool.

They do not share one context. A Graph hands a node the text of its parents'
results. A Workflow tool hands the next task a rendered string. A Swarm hands
its members a key-value `SharedContext`. They compose at the API level, not at
the data level. The adapters are the work. Nine experiments ask which fields
cross, how an inner failure is marked and what mixing costs. Only text crosses.
An inner tool failure can be reported as success. The two mixed runs use 74.5%
and 192.8% more model tokens than the pure Graph baseline E1. Inside one
process the boundary is a rendering step, not a network.

Eight runs reach Bedrock and share one fixture and one process. E9 only reads
their evidence and makes no model call. That is a bench for inspecting a
boundary, not production traffic. The numbers say nothing about answer quality.

`MultiAgentBase` is the SDK base class that both `Swarm` and `Graph` inherit
from, so a Graph node can take one as its executor. `@tool` is the SDK
decorator that turns a plain Python function into a tool an Agent can call.
`GraphState.results` holds one `NodeResult` per completed node; a condition
predicate decides whether an edge fires; `SharedContext` is the Swarm's nested
dictionary of keys per node; `task_results` is the Workflow tool's persisted
record of each task. An adapter moves a value from one of those structures into
a message the next orchestrator can read. A sentinel is a value I planted to
see whether it survives. A swallowed failure is one where the agent loop turns
a tool exception into text; an agent-level failure escapes that loop. Two
numbers carry the word "tokens". `accumulated_usage.totalTokens` is what the
runtime says a run spent, such as 4829 for E1. The 3640 in each brief is a
fixture figure from `sum_tokens` adding three invented per-node counts in
`data/brief-input.json`, not a measurement of model use.

## When not to use this

Do not mix orchestrators when a downstream step must branch on a result or when
the inner failure must be auditable. E6 shows a condition predicate can read
structured `NodeResult` fields, but a downstream node prompt gets only
`str(NodeResult)` text. E7 shows a tool that raises inside a nested Swarm
leaving the outer Graph `completed`. E8 shows the Workflow tool reporting
`100.0%` success while one of its tasks recorded an error on disk. Only an
agent-level exception made the Graph fail.

Do not mix them on a linear chain. In E1 to E5 the ledger records the same two
fixture numbers: 3640 tokens and $0.002912. The two mixed runs cost 74.5% and
192.8% more model tokens than E1 with wall clock up to 3.02x longer. I planned
parallel research inside the Swarm; the run produced a serial handoff. Mixing
buys one capability: a Graph can schedule a Swarm as a node. None of the three
pure baselines did that. Use it only if you accept a text-only boundary.

## Three channels, one process

The Graph keeps the richest record. Every finished node becomes a `NodeResult`
in `state.results`, and `_build_result` exposes that dictionary on the
`GraphResult` a caller holds.

```python
# strands/multiagent/graph.py:1164-1181 -- verbatim, strands-agents 1.63.0
node.result = node_result
node.execution_time = node_result.execution_time

if node_result.status == Status.INTERRUPTED:
    yield self._activate_interrupt(node, node_result.interrupts)
    return

if node_result.status == Status.FAILED:
    node.execution_status = Status.FAILED
    self.state.failed_nodes.add(node)
else:
    node.execution_status = Status.COMPLETED
    self.state.completed_nodes.add(node)
self.state.results[node.node_id] = node_result
self.state.execution_order.append(node)

# Accumulate metrics
self._accumulate_metrics(node_result)
```

```python
# strands/multiagent/graph.py:1327-1352 -- verbatim, strands-agents 1.63.0
def _build_result(self, interrupts: list[Interrupt]) -> GraphResult:
    """Build graph result from current state.

    Args:
        interrupts: List of interrupts collected during execution.

    Returns:
        GraphResult with current state.
    """
    return GraphResult(
        status=self.state.status,
        results=self.state.results,
        accumulated_usage=self.state.accumulated_usage,
        accumulated_metrics=self.state.accumulated_metrics,
        execution_count=self.state.execution_count,
        execution_time=self._execution_time_with_active_interval(self.state.execution_time),
        total_nodes=self.state.total_nodes,
        completed_nodes=len(self.state.completed_nodes),
        failed_nodes=len(self.state.failed_nodes),
        interrupted_nodes=len(self.state.interrupted_nodes),
        execution_order=self.state.execution_order,
        edges=self.state.edges,
        entry_points=self.state.entry_points,
        interrupts=interrupts,
        invocation_context=self._current_invocation_context,
    )
```

A condition predicate receives the state itself, so it can read those fields.

```python
# strands/multiagent/graph.py:209-224 -- verbatim, strands-agents 1.63.0
def should_traverse(self, state: GraphState, *, invocation_state: dict[str, Any]) -> bool:
    """Check if this edge should be traversed based on condition.

    Args:
        state: The current graph execution state.
        invocation_state: Runtime context passed during graph invocation.
            New-style conditions (EdgeConditionWithContext) receive this parameter.
            Legacy conditions (Callable[[GraphState], bool]) are called with state only.
    """
    condition = self.condition
    if condition is None:
        return True
    if self._check_is_context_condition(condition):
        return condition(state, invocation_state=invocation_state)
    legacy_condition = cast(LegacyEdgeCondition, condition)
    return legacy_condition(state)
```

The next Graph node does not receive that state. `_build_node_input` renders
each dependency with `str()` and puts the resulting text into the prompt.

```python
# strands/multiagent/graph.py:1284-1325 -- verbatim, strands-agents 1.63.0
# Get satisfied dependencies
dependency_results = {}
for edge in self.edges:
    if (
        edge.to_node == node
        and edge.from_node in self.state.completed_nodes
        and edge.from_node.node_id in self.state.results
    ):
        if edge.should_traverse(self.state, invocation_state=self._current_invocation_state):
            dependency_results[edge.from_node.node_id] = self.state.results[edge.from_node.node_id]

if not dependency_results:
    # No dependencies - return task as ContentBlocks
    if isinstance(self.state.task, str):
        return [ContentBlock(text=self.state.task)]
    else:
        return cast(list[ContentBlock], self.state.task)

# Combine task with dependency outputs
node_input = []

# Add original task
if isinstance(self.state.task, str):
    node_input.append(ContentBlock(text=f"Original Task: {self.state.task}"))
else:
    # Add task content blocks with a prefix
    node_input.append(ContentBlock(text="Original Task:"))
    node_input.extend(cast(list[ContentBlock], self.state.task))

# Add dependency outputs
node_input.append(ContentBlock(text="\nInputs from previous nodes:"))

for dep_id, node_result in dependency_results.items():
    node_input.append(ContentBlock(text=f"\nFrom {dep_id}:"))
    # Get all agent results from this node (flattened if nested)
    agent_results = node_result.get_agent_results()
    for result in agent_results:
        agent_name = getattr(result, "agent_name", "Agent")
        result_text = str(result)
        node_input.append(ContentBlock(text=f"  - {agent_name}: {result_text}"))

return node_input
```

`str(NodeResult)` delegates to the inner result. For a nested orchestrator that
inner result is a `MultiAgentResult`, and its `__str__` builds one line of text
per node.

```python
# strands/multiagent/base.py:66-90 -- verbatim, strands-agents 1.63.0
def __str__(self) -> str:
    """Return a human-readable string representation of the node result.

    Delegates to the inner result's string representation:
    - AgentResult: Uses AgentResult.__str__ (extracts text content)
    - MultiAgentResult: Uses MultiAgentResult.__str__ (recursive)
    - Exception: Uses the exception's string representation

    Returns:
        String representation of the node's result.
    """
    return str(self.result)

def get_agent_results(self) -> list[AgentResult]:
    """Get all AgentResult objects from this node, flattened if nested."""
    if isinstance(self.result, Exception):
        return []  # No agent results for exceptions
    elif isinstance(self.result, AgentResult):
        return [self.result]
    else:
        # Flatten nested results from MultiAgentResult
        flattened = []
        for nested_node_result in self.result.results.values():
            flattened.extend(nested_node_result.get_agent_results())
        return flattened
```

```python
# strands/multiagent/base.py:165-187 -- verbatim, strands-agents 1.63.0
def __str__(self) -> str:
    """Return a human-readable string representation of the multi-agent result.

    Priority order:
    1. Interrupts (if present) → stringified list of interrupt dicts
    2. Node results → each node's string output, prefixed with node name

    Returns:
        String representation based on the priority order above.
    """
    if self.interrupts:
        return str([interrupt.to_dict() for interrupt in self.interrupts])

    parts = []
    for node_name, node_result in self.results.items():
        # Remove only the single trailing newline that AgentResult.__str__ appends
        # as a framework separator, preserving all user-owned whitespace (leading
        # indentation, internal markdown hard-break spaces, payload trailing newlines).
        node_str = str(node_result).removesuffix("\n")
        if node_str:
            parts.append(f"{node_name}: {node_str}")

    return "\n".join(parts)
```

The Swarm keeps a different structure. `SharedContext` is a nested dictionary,
and a handoff writes the caller's context into it.

```python
# strands/multiagent/swarm.py:129-143 -- verbatim, strands-agents 1.63.0
@dataclass
class SharedContext:
    """Shared context between swarm nodes."""

    context: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_context(self, node: SwarmNode, key: str, value: Any) -> None:
        """Add context."""
        self._validate_key(key)
        self._validate_json_serializable(value)

        if node.node_id not in self.context:
            self.context[node.node_id] = {}
        self.context[node.node_id][key] = value
```

```python
# strands/multiagent/swarm.py:677-701 -- verbatim, strands-agents 1.63.0
def _handle_handoff(self, target_node: SwarmNode, message: str, context: dict[str, Any]) -> None:
    """Handle handoff to another agent."""
    # If task is already completed, don't allow further handoffs
    if self.state.completion_status != Status.EXECUTING:
        logger.debug(
            "task_status=<%s> | ignoring handoff request - task already completed",
            self.state.completion_status,
        )
        return

    current_node = cast(SwarmNode, self.state.current_node)

    self.state.handoff_node = target_node
    self.state.handoff_message = message

    # Store handoff context as shared context
    if context:
        for key, value in context.items():
            self.shared_context.add_context(current_node, key, value)

    logger.debug(
        "from_node=<%s>, to_node=<%s> | handing off from agent to agent",
        current_node.node_id,
        target_node.node_id,
    )
```

The next Swarm member still reads text. `_build_node_input` serializes the
dictionary into a bullet list in the prompt.

```python
# strands/multiagent/swarm.py:761-769 -- verbatim, strands-agents 1.63.0
# Include actual shared context, not just a mention
shared_context = context_info.get("shared_context", {})
if shared_context:
    context_text += "Shared knowledge from previous agents:\n"
    for node_name, context in shared_context.items():
        if context:  # Only include if node has contributed context
            context_text += f"• {node_name}: {context}\n"
    context_text += "\n"
```

The Swarm's own result carries `node_history`. It does not carry
`shared_context`.

```python
# strands/multiagent/swarm.py:1088-1100 -- verbatim, strands-agents 1.63.0
def _build_result(self, interrupts: list[Interrupt]) -> SwarmResult:
    """Build swarm result from current state."""
    return SwarmResult(
        status=self.state.completion_status,
        results=self.state.results,
        accumulated_usage=self.state.accumulated_usage,
        accumulated_metrics=self.state.accumulated_metrics,
        execution_count=len(self.state.node_history),
        execution_time=self.state.execution_time,
        node_history=self.state.node_history,
        interrupts=interrupts,
        invocation_context=self._current_invocation_context,
    )
```

The Workflow tool keeps a third structure on disk. Each task writes a record
with a status, a result and metrics.

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

The upstream record is spliced into the next task's prompt as text.

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

The caller of `workflow(action="start")` receives one dictionary with `content`
and `status`. The content block holds a single sentence.

```python
# strands_tools/workflow.py:690-709 -- verbatim, strands-agents-tools 0.8.11
# Workflow completed
workflow["status"] = "completed"
workflow["completed_at"] = datetime.now(timezone.utc).isoformat()
self.store_workflow(workflow_id, workflow)

# Calculate success rate
completed_count = sum(1 for result in workflow["task_results"].values() if result["status"] == "completed")
success_rate = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0

return {
    "status": "success",
    "content": [
        {
            "text": (
                f"🎉 Workflow '{workflow_id}' completed successfully! "
                f"({completed_count}/{total_tasks} tasks succeeded - {success_rate:.1f}%)"
            )
        }
    ],
}
```

Three structures, three rendering steps. In each case the next orchestrator
reads a string. The composition holds because a `MultiAgentBase` can be a
Graph node, not because any of these structures is shared.

```python
# strands/multiagent/graph.py:1078-1103 -- verbatim, strands-agents 1.63.0
if isinstance(node.executor, MultiAgentBase):
    # For nested multi-agent systems, stream their events and collect result
    multi_agent_result = None
    async for event in node.executor.stream_async(
        node_input, invocation_state, invocation_context=self._current_invocation_context
    ):
        # Forward nested multi-agent events with node context
        wrapped_event = MultiAgentNodeStreamEvent(node.node_id, event)
        yield wrapped_event
        # Capture the final result event
        if "result" in event:
            multi_agent_result = event["result"]

    # Use the captured result from streaming (no double execution)
    if multi_agent_result is None:
        raise ValueError(f"Node '{node.node_id}' did not produce a result event")

    node_result = NodeResult(
        result=multi_agent_result,
        execution_time=multi_agent_result.execution_time,
        status=multi_agent_result.status,
        accumulated_usage=multi_agent_result.accumulated_usage,
        accumulated_metrics=multi_agent_result.accumulated_metrics,
        execution_count=multi_agent_result.execution_count,
        interrupts=multi_agent_result.interrupts,
    )
```

## Three baselines, one brief

E1 runs a pure Graph with three nodes. It is the control for every cost number
below.

```text
e1-graph-baseline.txt (E1), selected fields rewrapped for this page:
status = completed
execution_order = ["researcher", "calculator", "writer"]
total_nodes = 3
failed_nodes = 0
tokens_total.inputTokens = 4455
tokens_total.outputTokens = 374
tokens_total.totalTokens = 4829
model_calls_total = 6
wall_clock_s = 10.179
ledger: sum_tokens total=3640 cost_usd=0.002912
ledger: save_draft words=6
```

The order is fixed by edges. The calculator's first prompt already contains
`From researcher:` and the researcher's answer as text. That is the boundary in
one line. The Graph knew `status` and `accumulated_usage`; the calculator got a
sentence.

E2 runs the vended Workflow tool with the same three tasks.

```text
e2-workflow-baseline.txt (E2), selected fields rewrapped for this page:
start_return_top_level_keys = ["content", "status"]
start_return_has_only_text_blocks = True
start_text = 🎉 Workflow 'e2-wf-linear' completed successfully! (3/3 tasks succeeded - 100.0%)
downstream_can_classify_each_task_from_return = False
per_task_id_appears_in_return.researcher = False
per_task_id_appears_in_return.calculator = False
per_task_id_appears_in_return.writer = False
return_carries_no_per_task_status_boolean = True
task_status_on_disk.researcher = completed
task_status_on_disk.calculator = completed
task_status_on_disk.writer = completed
per_task_tokens.researcher.totalTokens = 1563
per_task_tokens.calculator.totalTokens = 1640
per_task_tokens.writer.totalTokens = 1564
tokens_total = 4767
model_calls_total = 6
workflow_elapsed_s = 11.11
```

The disk holds one record per task with a status and an `Event Loop Metrics
Summary` for each. The return value holds one sentence with a percentage, so a
caller cannot tell which task succeeded. E2 is the cheapest run, 62 model
tokens below E1. That gap is noise from model wording, not a saving the tool
produced, so E1 stays the baseline for every percentage below.

```text
e3-swarm-baseline.txt (E3), selected fields rewrapped for this page:
status = completed
execution_count = 3
handoff_order_node_history = ["researcher", "calculator", "writer"]
shared_context_final_keys.researcher = ["points_found", "raw_counts"]
shared_context_final_keys.calculator = ["cost_usd", "total"]
shared_context_final.researcher.raw_counts = [1180, 940, 1520]
shared_context_final.calculator.total = 3640
tokens_total.totalTokens = 8234
model_calls_total = 8
wall_clock_s = 21.795
```

The Swarm is the only one of the three that keeps typed values. It also costs
70.5% more tokens than E1 and takes 2.14x as long. Each handoff rebuilds a
prompt that carries the earlier nodes' shared knowledge as text. The typed
dictionary is real. It does not leave the Swarm.

```python
# usecases/10-mixed/src/e4_mixed_graph_swarm.py:55-65 -- verbatim, this bench
swarm = Swarm(
    nodes=[swarm_agents[n] for n in SWARM_ORDER],
    entry_point=swarm_agents["scout"],
    max_handoffs=8,
    max_iterations=8,
)

gb = GraphBuilder()
add_accepted = False
try:
    gb.add_node(swarm, "swarm_research")
```

```text
e4-mixed-graph-swarm.txt (E4), selected fields rewrapped for this page:
swarm_is_multiagentbase = True
graphbuilder_add_node_accepted = True
execution_order = ["swarm_research", "calculator", "writer"]
nested_node_result_python_type = SwarmResult
nested_node_executed = True
inner_swarm_handoff_order = ["scout", "analyst"]
inner_swarm_is_serial_handoff = True
swarm_object_has_shared_context = True
graph_state_results_exposes_shared_context = False
inner_swarm_accumulated_usage.totalTokens = 4778
tokens_total.totalTokens = 8428
graph_usage_includes_nested_swarm_tokens = True
model_calls_total = 8
wall_clock_s = 23.296
tokens_delta_vs_e1 = 3599
```

The Graph ran the Swarm as one node and the Swarm handed off from `scout` to
`analyst`. That is a serial handoff, not parallel research. The Graph's usage
does include the nested Swarm's 4778 tokens, so one ledger covers this
composition. The next Graph node received two lines of `scout:` and `analyst:`
text, and the `SharedContext` keys never became a field the Graph could read.
E4 cost 74.5% more tokens than E1 and took 2.29x as long.

E5 needs an adapter. The vended Workflow tool is a `@tool` function, not a
`MultiAgentBase`, so it cannot be a Graph node. I wrapped `create` and `start`
in a tool that a Graph node Agent can call.

```python
# usecases/10-mixed/src/common.py:250-272 -- verbatim, this bench
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
```

```text
e5-mixed-graph-workflow.txt (E5), selected fields rewrapped for this page:
workflow_is_graph_node = False
workflow_embedded_via = Graph node Agent calls run_brief_pipeline (a @tool wrapping workflow create+start)
execution_order = ["intake", "wf_stage", "review"]
graph_accumulated_usage.totalTokens = 9272
inner_workflow_tokens_total = 4867
true_total_tokens_graph_plus_inner = 14139
graph_model_calls_total = 7
inner_workflow_model_calls_total = 6
true_total_model_calls = 13
inner_task_ids_present_as_graph_nodes = False
inner_task_model_calls_in_graph_results = False
graph_usage_equals_sum_of_its_own_nodes = True
wall_clock_s = 30.779
true_total_tokens_delta_vs_e1 = 9310
```

Two ledgers, not one. The Graph reports 9272 tokens for its own three nodes.
The inner Workflow tasks ran in separate Agents and used 4867 tokens. The SDK
does not add them together. I added them to get 14139, and I am saying so
plainly: that number is my sum of two real measurements, not a total any
runtime reported. The Graph's `state.results` has three keys and no key for any
inner task.

E6 plants a sentinel and asks a direct question. I told the `scout` to write
`SWARM-7Q2` into `SharedContext` and told the `analyst` not to repeat it. Then
I put a Swarm, a Workflow tool call and a sink node in one Graph and looked for
the string.

```python
# usecases/10-mixed/src/e6_context_bridge.py:39-48 -- verbatim, this bench
SENTINEL = "SWARM-7Q2"
PREDICATE_LOG: list[dict] = []

SWARM_INSTRUCTIONS = {
    "scout": (
        "You are the scout. Call read_brief_input exactly once. Then call "
        "handoff_to_agent with agent_name='analyst', put the three points in the "
        "message argument, and pass context={'sentinel': 'SWARM-7Q2', "
        "'raw_counts': [1180, 940, 1520]}. Do not finish without handing off."
    ),
```

```text
e6-context-bridge.txt (E6), selected fields rewrapped for this page:
execution_order = ["swarm_src", "wf_mid", "sink"]
sentinel_swarm = SWARM-7Q2
structured_reachability.graph_noderesult_has_status = True
structured_reachability.graph_noderesult_has_accumulated_usage = True
structured_reachability.graph_noderesult_has_shared_context = False
structured_reachability.swarmresult_has_node_history = True
structured_reachability.swarmresult_has_shared_context = False
structured_reachability.graph_noderesult_has_task_results = False
structured_reachability.wf_agentresult_has_task_results = False
channel_graph_state_results.node_result_fields = [accumulated_metrics, accumulated_usage, execution_count, execution_time, interrupts, result, status]
channel_graph_state_results.reaches_condition_predicate = True
channel_graph_state_results.reaches_downstream_node_prompt_as_structure = False
channel_graph_state_results.what_crosses_to_next_node = str(NodeResult) TEXT only
channel_swarm_shared_context.value.scout.sentinel = SWARM-7Q2
channel_swarm_shared_context.reaches_graph_as_structured_field = False
channel_workflow.task_result_fields.researcher = [completed_at, metrics, model_provider, priority, result, status, tools]
channel_workflow.reaches_graph_as_structured_field = False
channel_workflow.what_crosses_to_next_node = one raw TEXT sentence
visibility_checks.sentinel_string_in_graph_results_text = False
visibility_checks.sentinel_string_in_sink_prompt = False
visibility_checks.task_results_word_in_graph_results_text = False
visibility_checks.graph_structured_field_names_in_sink_prompt = False
```

Four crossings, one rule. A condition predicate reads `state.results` directly
and gets all seven `NodeResult` fields with nothing lost. In this run it read
`status=completed`, `accumulated_usage.totalTokens=4385` and
`execution_time=7606`. A downstream Graph node prompt gets `str(NodeResult)`
text and loses five of them. A Swarm's `SharedContext` reaches the Graph as no
structured field at all, losing the sentinel, `node_history` and the handoff
message. A Workflow tool's `task_results` reaches the Graph as no structured
field either, losing each task's `status`, `result`, `metrics` and per-task
success flag. The sentinel was written. It did not appear in the Graph results
text or in the sink's prompt. A raw string is not a field an orchestrator can
branch on. After a boundary, the caller has to own the channel that carries the
evidence.

```text
e7-failure-inner-swarm.txt (E7), selected fields rewrapped for this page:
swallowed.inner_swarm_status = completed
swallowed.graph_status = completed
swallowed.execution_order = ["swarm_src", "sink"]
swallowed.failed_nodes = 0
swallowed.downstream_sink_ran = True
swallowed.inner_error_marker_in_graph_node_text = True
swallowed.inner_error_marker_reaches_sink_prompt = True
swallowed.graph_treated_inner_failure_as_success = True
agent_raise.inner_swarm_status = failed
agent_raise.graph_status = failed
agent_raise.execution_order = ["swarm_src"]
agent_raise.failed_nodes = 1
agent_raise.downstream_sink_ran = False
agent_raise.graph_treated_inner_failure_as_success = False
```

The swallowed case is the interesting one. The inner Swarm reported
`completed`, the outer Graph reported `completed` and the sink node ran. The
error text did reach the sink's prompt as English prose. A Graph status does
not branch on prose. Only an agent-level exception turned the inner Swarm
`failed`, made the Graph fail and pruned the downstream branch. The pruning is
in the source: failed nodes are removed before their outgoing edges are walked.

```python
# strands/multiagent/graph.py:999-1019 -- verbatim, strands-agents 1.63.0
def _find_newly_ready_nodes(self, completed_batch: list["GraphNode"]) -> list["GraphNode"]:
    """Find nodes that became ready after the last execution.

    Only evaluates destination nodes of outbound edges from the completed batch,
    instead of iterating over all nodes in the graph.  Failed nodes (e.g. a
    cancelled agent) are excluded so they cannot nominate successors — their
    downstream branch is pruned while sibling branches continue.
    """
    # Strip failed/cancelled nodes so their outgoing edges are never walked.
    completed_batch = [node for node in completed_batch if node.execution_status != Status.FAILED]
    if not completed_batch:
        return []

    # Collect unique candidate nodes reachable from the completed batch
    candidates = {edge.to_node for edge in self.edges if edge.from_node in completed_batch}

    newly_ready = []
    for node in candidates:
        if self._is_node_ready_with_conditions(node, completed_batch):
            newly_ready.append(node)
    return newly_ready
```

E8 asks whether a Graph condition predicate can classify a failure inside the
Workflow sub-process. I injected the same raising tool into the first inner
task and put a fallback edge behind a predicate that looks for the error text.

```text
e8-failure-workflow-condition.txt (E8), selected fields rewrapped for this page:
graph_status = completed
execution_order = ["wf_stage", "ok_writer"]
branch_taken = ok_writer
inner_workflow_reports_100pct_success = True
inner_workflow_status = completed
inner_task_status_on_disk.researcher = completed
inner_task_status_on_disk.calculator = completed
inner_task_status_on_disk.writer = completed
inner_error_marker_in_researcher_disk_text = True
inner_researcher_disk_text = The explode tool failed with an error: "RuntimeError - injected tool failure."
inner_actually_failed = True
inner_error_marker_in_wf_stage_node_text = False
predicate_eval_count = 3
predicate_saw_inner_failure_marker = False
condition_could_classify_inner_failure = False
```

The Workflow tool reported `3/3 tasks succeeded - 100.0%`. Its researcher task
did record the error on disk. The `wf_stage` node text was the success sentence,
so the predicate evaluated three times and never saw the marker. It routed to
`ok_writer`. The reason is a single line in the tool's executor: a task is a
success whenever `stop_reason` is not `error`, and a swallowed tool exception
does not set that.

```python
# strands_tools/workflow.py:446-477 -- verbatim, strands-agents-tools 0.8.11
# Extract response content - handle both dict and custom object return types
try:
    content = (
        result.message.get("content", [])
        if hasattr(result.message, "get")
        else getattr(result.message, "content", [])
    )
except AttributeError:
    content = [{"text": str(result)}]

# Extract stop reason and metrics
try:
    stop_reason = (
        result.get("stop_reason", "") if hasattr(result, "get") else getattr(result, "stop_reason", "")
    )
    metrics = result.get("metrics") if hasattr(result, "get") else getattr(result, "metrics", None)
except AttributeError:
    stop_reason = ""
    metrics = None

# Log metrics if available
if metrics:
    metrics_text = metrics_to_string(metrics)
    logger.debug(f"Task {task_id} metrics: {metrics_text}")

# Update task status
status = "success" if stop_reason != "error" else "error"
return {
    "status": status,
    "content": content,
    "metrics": metrics_text if metrics else None,
}
```

An earlier post found the same swallowed failure reported as 100% success
inside a pure workflow. E7 and E8 show it surviving two more boundaries. The
composition did not add a failure channel. It added two places where the
failure becomes text.

```text
e9-cost-capability.txt (E9), five runs side by side:
E1  Graph only          4829 tokens    6 model calls   10.179 s   1.00x
E2  Workflow only       4767 tokens    6 model calls   11.110 s   1.09x
E3  Swarm only          8234 tokens    8 model calls   21.795 s   2.14x
E4  Graph + Swarm       8428 tokens    8 model calls   23.296 s   2.29x
E5  Graph + Workflow   14139 tokens   13 model calls   30.779 s   3.02x

deltas_vs_e1.E2.tokens_pct_vs_e1 = -1.3
deltas_vs_e1.E3.tokens_pct_vs_e1 = 70.5
deltas_vs_e1.E4.tokens_pct_vs_e1 = 74.5
deltas_vs_e1.E5.tokens_pct_vs_e1 = 192.8
E5.graph_reported_tokens = 9272
E5.inner_workflow_tokens = 4867
E5.true_total_tokens_graph_plus_inner = 14139
```

E9 also runs a construction-time probe on the installed SDK. It builds objects
and checks what each container accepts. It makes no Bedrock call, so these are
acceptance results and nothing about execution.

```text
e9-cost-capability.txt (E9), capability probe, construction only:
graph_add_swarm_node = accepted
graph_add_workflow_tool = accepted at construction (but _execute_node rejects non AgentBase/MultiAgentBase)
swarm_host_graph_node = rejected: AttributeError: 'Graph' object has no attribute '_session_manager'
workflow_task_is_dict_description = True
note = Construction-time probe only; no Bedrock model call.
```

I did not execute the rejected cases. Acceptance at construction time is not
evidence that a node runs. E4 is the executed case: the Graph scheduled the
Swarm and the nested node produced a `SwarmResult`.

The verdict is narrow. Mixing buys one capability: a Graph that schedules a
Swarm as a node. On this linear task it buys no usable data power, because E6
shows every structured field trapped behind a text boundary and E7 and E8 show
an inner failure reported as success or invisible to a predicate. Each of the
five brief-producing runs, E1 to E5, wrote the same fixture figure of 3640
tokens and $0.002912 into its ledger. Meanwhile the two mixed runs used 74.5%
and 192.8% more model tokens than the pure Graph baseline E1, with wall clock
up to 3.02x. Mix only when you need one orchestrator nested inside a Graph and
you accept a text-only boundary. Composition added a layer without removing
one: E4 used 8428 tokens against E3's 8234.

## What surprised me

I expected the mixed run to be cheaper than the pure Swarm. E4 used 8428 tokens
against E3's 8234: the Graph kept its own node prompts and paid for the nested
Swarm on top, so composition added a layer without removing one. I also expected
parallel research, but E4's Swarm handed off from `scout` to `analyst` in
sequence; a Swarm is a handoff chain, not a worker pool. The third surprise was
E5's two ledgers: the Graph meters its own nodes, the Workflow task Agents meter
themselves. No runtime holds the 14139 total. I added two real numbers by
hand.

## What this experiment does not cover

This experiment does not cover authentication or SigV4, multi-tenant context
isolation, real network partitions, streaming artifact schemas, provider-side
ledger reconciliation or answer quality and cost per useful result. It does not
cover a genuinely parallel Swarm research layer, a Graph inside a Swarm or the
Workflow tool as a direct Graph node. The E9 probe rejected one and accepted
the other at construction time; I executed neither. It does not cover a
branching graph where a predicate gates a side effect. The three questions
about what crosses the boundary, how an inner failure is marked and what mixing
costs are not in this list. E6, E7, E8 and E9 measure them.

## How I measured

All numbers come from nine experiments on 2026-11-20, with `strands-agents`
1.63.0, `strands-agents-tools` 0.8.11, `amazon.nova-pro-v1:0` in `us-east-1`,
Python 3.11 and one OS process per run. E1 to E8 reach Bedrock. E9 aggregates
the five already-run experiments and adds a construction-time probe; it makes
no model call. The token columns come from `accumulated_usage` on real results.
The 3640 in each brief is a fixture figure that `sum_tokens` computes, not a
model measurement. E2 counts the per-task Agents. E5 adds two separate real
ledgers by hand, and the text says so. Every SDK source block above is sliced
verbatim from the installed site-packages and dedented so the first code line
is flush left; the 19 blocks and the generator are in
`evidence/source-blocks.md` and `src/gen_source_blocks.py`. The text blocks
rewrap selected fields for the page width, so the byte-exact lines live in the
evidence files. Model output varies between runs.

## Try it yourself

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/10-mixed
python3 -m venv .venv && . .venv/bin/activate
pip install strands-agents==1.63.0 strands-agents-tools==0.8.11 boto3
export AWS_DEFAULT_REGION=us-east-1
```

The full source, the fixed fixture and all raw evidence are in the repository
at https://github.com/pinxiong/strands-in-action/tree/master/usecases/10-mixed.
Use Python 3.11 for the venv. The scripts hard-code `us-east-1` and
`amazon.nova-pro-v1:0` in `src/common.py` and pass the region explicitly to
`BedrockModel`, so `AWS_DEFAULT_REGION` cannot redirect these calls. Provide
credentials through `aws configure`, `AWS_PROFILE` or environment variables.
Enable model access for `amazon.nova-pro-v1:0` first. Then run the nine
experiments:

```bash
.venv/bin/python src/e1_graph_baseline.py
.venv/bin/python src/e2_workflow_baseline.py
.venv/bin/python src/e3_swarm_baseline.py
.venv/bin/python src/e4_mixed_graph_swarm.py
.venv/bin/python src/e5_mixed_graph_workflow.py
.venv/bin/python src/e6_context_bridge.py
.venv/bin/python src/e7_failure_inner_swarm.py
.venv/bin/python src/e8_failure_workflow_condition.py
.venv/bin/python src/e9_cost_capability.py
```

Each script creates its own `STRANDS_WORKFLOW_DIR` under a temporary path, so
persisted Workflow state cannot leak between experiments. The scripts clear the
shared tool ledger at startup, so run them one at a time. E9 reads the five
evidence files that E1 to E5 wrote, so run it last. `src/gen_source_blocks.py`
rebuilds the verbatim source blocks from your installed packages; the line
numbers shift if you install a different version. Read `first_prompt` or
`first_inputs` in each JSON before comparing numbers with mine: model wording
differs between runs, while `status`, `execution_order`, the sentinel checks
and the token counters do not.

## Takeaways

1. Three orchestrators compose at the API level, not at the data level. A Graph
   accepts a `Swarm` as a node because `Swarm` is a `MultiAgentBase`.
2. A downstream node prompt gets `str(NodeResult)` text and loses five of the
   seven `NodeResult` fields. `SharedContext` and `task_results` arrive as no
   structured field at all.
3. A swallowed inner failure left the outer Graph `completed`. E8 reported
   `100.0%` success with an error on disk. E5 has two ledgers: 9272 plus 4867,
   and the 14139 total is my sum. The adapters are the whole finding.
