# Orchestrating Agents: The Graph Is Yours, the Judgment Isn't

> Verified on 2026-11-13 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. Every number below came out of a run. The scripts and raw output live in
> https://github.com/pinxiong/strands-in-action/tree/master/usecases/07-graph.
> The model is `amazon.nova-pro-v1:0`.

The last post in this series ended with a swarm that had no scheduler. Three agents
passed a task around by calling one tool, and the runtime read the absence of that
call as completion. The task is small: given a topic, produce research notes, add up
the per-node token counts and write a short brief. This post runs the same task on a
graph instead, using the same fixed input file and the same three roles, so the traces
stay comparable. I assume you have read the UC06 trace, so I will not restate it.

Here is the judgment that changes. In a swarm the model decides who runs next, because
routing is a tool call it can choose to make. In a graph that decision is gone from the
model entirely: an edge fires when a plain Python function returns `True`. You write
that function, you draw the edges, and you set the limits. The routing judgment is
yours now. The other judgment is not. Each node is still a full agent loop, and the
model inside it still decides which tools to call and what words to produce. Since
your predicate reads those words, the model still supplies the evidence your routing
runs on. Structure is deterministic. Input is not.

That split is the whole design, and most of the surprises come from it. This post walks
the mechanism through source and through runs. An edge that fires has its predicate
evaluated twice. A join runs twice because readiness is an OR. A graph with no limits warns
you and then runs forever. And one documented failure behaviour does not match what
the runtime actually does.

One scope note before the trace. This is the open-source Strands Agents SDK, a Python
library you install and run inside your own process. Bedrock supplies the model; it is
not a hosted orchestrator. Every run below happens in a single process with a handful
of nodes (two to four), one model and short tasks that finish in about half a minute.
That is a bench for inspecting a mechanism, not a sample of production multi-agent
traffic. The numbers describe the runtime's behaviour rather than the quality of any
answer.

## A predicate, not a judge

`GraphEdge` holds an optional `condition`. The method below is the entire routing
decision, and it is plain Python. There is no model call in it.

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

An edge with no condition returns `True`. An edge with one calls it and takes the
boolean. That is the deterministic half of the title.

To test what the predicate can see, I built a three-node chain. The calculator has
two outgoing edges. One leads to a writer and is guarded by `"3640" in text`, where
3640 is the token total the calculator produced from the fixed input. The other leads
to a fallback and is guarded by the opposite test. Here `text` is the concatenation of
everything in `state.results`. Because upstream results are the final text the model
wrote, the predicate is a Python string test over model output. The run finished `COMPLETED` with 5145
tokens in 31813 ms and this order: `researcher, calculator, writer`. The fallback never
ran.

The predicate was called three times, and that is the first surprise. One call rejected
the fallback edge. Two calls approved the writer edge, once when the runtime looked for
ready nodes and once when it built the writer's input. The source explains why:
`_is_node_ready_with_conditions` and `_build_node_input` each call `should_traverse`
for the same approved edge. If your condition has a side effect, it happens twice.

At every one of those three calls I snapshotted the per-node model call counters. All
three snapshots were identical: `{researcher: 2, calculator: 2, writer: 0, fallback: 0}`.
Each finished node made two model calls, one to choose a tool and one to write its final
answer. No model was consulted while routing. The decision was a string test on text
that those earlier model calls had produced.

So "the judgment isn't yours" is precise. You own the structure of the decision, but
the evidence it evaluates is written by a model you cannot fully direct. If the
calculator had phrased its answer without the number 3640, the other branch would have
run. I did not test that counterfactual, and I am not claiming it as a result.

## First parent wins

The next surprise is in how a node with several parents becomes ready. Most graph
runtimes treat a join as a barrier: wait until every parent has finished. Strands does
not. The loop returns `True` on the first satisfied incoming edge.

```python
# strands/multiagent/graph.py:1021-1038 -- verbatim, strands-agents 1.63.0
def _is_node_ready_with_conditions(self, node: GraphNode, completed_batch: list["GraphNode"]) -> bool:
    """Check if a node is ready considering conditional edges."""
    # Get incoming edges to this node
    incoming_edges = [edge for edge in self.edges if edge.to_node == node]

    # Check if at least one incoming edge condition is satisfied
    for edge in incoming_edges:
        if edge.from_node in completed_batch:
            if edge.should_traverse(self.state, invocation_state=self._current_invocation_state):
                logger.debug(
                    "from=<%s>, to=<%s> | edge ready via satisfied condition", edge.from_node.node_id, node.node_id
                )
                return True
            else:
                logger.debug(
                    "from=<%s>, to=<%s> | edge condition not satisfied", edge.from_node.node_id, node.node_id
                )
    return False
```

The comment says "at least one", and the early `return True` is the OR. To make the
test decisive I put one parent in a later batch:

```text
A (fast, batch 1) ---> B (slow, batch 2)
  \                     /
   +----------------> join
```

`A -> B`, `A -> join` and `B -> join`. After batch 1 finishes, `join` has one incoming
edge from `A` that is already satisfied. If `join` were a barrier it would wait for `B`.
The run reported `COMPLETED` with 1365 tokens in 9473 ms and an execution order of
`A, join, B, join`.

Read that order carefully. The join ran twice. It started at the same moment as `B`,
overlapped `B`'s wall-clock interval (`overlap_pairs = [('join', 'B')]`) and finished
before `B` did. Its input contained exactly one dependency block, `From A:`. When `B`
completed, the second incoming edge became satisfied and the join was nominated again.
Readiness is an OR over edges in the completed batch, and nothing checks whether the
node has already run.

This is not a bug to report as a defect; it is the semantics you must design around. A
fan-in node can observe a partial set of parents, and it can be executed once per
arriving parent. If you need a barrier, you have to build it yourself with a condition
that inspects `state.completed_nodes`.

## State is a string, not a shared object

What a downstream node receives is not a structured state object. The runtime builds a
list of text blocks by concatenating the original task and the string form of each
completed dependency's result.

```python
# strands/multiagent/graph.py:1285-1325 -- verbatim, strands-agents 1.63.0
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

Note that `should_traverse` appears here again. That is the second predicate call from
the fork experiment. A dependency whose edge condition now returns `False` is omitted
from the input, even if the node ran and produced a result.

The linear chain shows the output of this builder verbatim. It finished `COMPLETED`
with 5109 tokens in 9863 ms, and each of the three nodes made two model calls. The
writer's first message began:

```text
Original Task: Produce the brief described in data/brief-input.json. Research first, then compute the totals, then write the brief.

Inputs from previous nodes:

From calculator:
  - Agent: The total token count is 3640, and the cost is $0.002912.
```

The researcher saw only the raw task. The calculator saw `Original Task:` plus a
`From researcher:` block. The writer saw `Original Task:` plus a `From calculator:`
block, and not the researcher's text. Each node gets one hop of history, rendered as
prose. UC06's swarm had an explicit `SharedContext` object that was re-serialized into
every downstream prompt. A graph has no equivalent channel in this path: what flows is
the string of a result, one edge at a time.

## Unbounded by default

A graph with a cycle needs a stopping rule, and the runtime does not supply one for
you. `GraphState.should_continue` only checks limits that you configured.

```python
# strands/multiagent/graph.py:161-180 -- verbatim, strands-agents 1.63.0
def should_continue(
    self,
    max_node_executions: int | None,
    execution_timeout: float | None,
) -> tuple[bool, str]:
    """Check if the graph should continue execution.

    Returns: (should_continue, reason)
    """
    # Check node execution limit (only if set)
    if max_node_executions is not None and len(self.execution_order) >= max_node_executions:
        return False, f"Max node executions reached: {max_node_executions}"

    # Check timeout (only if set)
    if execution_timeout is not None:
        elapsed = self.execution_time / 1000 + time.time() - self.start_time
        if elapsed > execution_timeout:
            return False, f"Execution timed out: {execution_timeout}s"

    return True, "Continuing"
```

Both checks are guarded by "only if set", and the fallback returns `True`. `GraphBuilder.build()` calls a validator that
warns when neither is set.

```python
# strands/multiagent/graph.py:491-504 -- verbatim, strands-agents 1.63.0
def _validate_graph(self) -> None:
    """Validate graph structure."""
    # Validate entry points exist
    entry_point_ids = {node.node_id for node in self.entry_points}
    invalid_entries = entry_point_ids - set(self.nodes.keys())
    if invalid_entries:
        raise ValueError(f"Entry points not found in nodes: {invalid_entries}")

    if self._max_node_executions is None and self._execution_timeout is None:
        warnings.warn(
            "graph has no max_node_executions or execution_timeout set; execution is unbounded",
            stacklevel=3,
        )
```

I built a two-node cycle (`ping -> pong -> ping`) with a condition that always returns
`True`. Building it with no limits produced exactly one warning: `graph has no
max_node_executions or execution_timeout set; execution is unbounded`. I did not run
that graph, because with no cap it would not terminate.

To observe the cycle I built a second copy with only a six second timeout. It reported
`FAILED` after three node executions. With `set_max_node_executions(6)` instead, it
reported `FAILED` after exactly six executions, 644 tokens and 18586 ms. Hitting the
cap is a failure, not a completed run. UC06 found that a swarm's two limits are really
one counter: the node cap and the handoff cap both read the same `node_history` length.
Here the two limits are genuinely independent, yet neither is set by default. `reset_on_revisit` also defaults to `False`, so a revisited node keeps its
message history unless you ask for a reset.

Convergence is your responsibility. The structure is yours, and so is the obligation
to prove that it stops.

## Parallel for real, and a documented behaviour that did not happen

A batch of nodes really does run concurrently. `_execute_nodes_parallel` starts one
`asyncio` task per node and merges their event streams through a shared queue. I ran
two independent entry points that each sleep for three seconds. The result was
`COMPLETED` with 2046 tokens in 5493 ms, and the wall-clock intervals intersected:
`overlap_pairs = [('right', 'left')]`. UC06 ran the same two-sleeping-branch bench on a
swarm and found no overlapping intervals, because a swarm hands off serially. That
difference is real, and it is a consequence of the two runtimes rather than of the
task.

The failure path is where the documentation and the runtime part company.
`_find_newly_ready_nodes` describes pruning:

```python
# strands/multiagent/graph.py:999-1010 -- verbatim, strands-agents 1.63.0
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
```

I injected two different failures into a graph with two branches, `bad` and `good`,
each with its own downstream node. Neither injection produced the behaviour above.

First, a tool that raises. The run finished `COMPLETED` with 1659 tokens in 4794 ms,
and all four nodes ran: `good, bad, good_downstream, bad_downstream`. The `bad` node's
status was `COMPLETED`, because a tool exception is returned to the agent as a tool
result. The agent finishes its turn normally, so the node is not failed at all.
There is no failed node to prune.

Second, `BeforeNodeCallEvent.cancel_node`, which is the human intervention point. The
hook sets `cancel_node`, and `_execute_node` responds by raising.

```python
# strands/multiagent/graph.py:1066-1072 -- verbatim, strands-agents 1.63.0
if before_event.cancel_node:
    cancel_message = (
        before_event.cancel_node if isinstance(before_event.cancel_node, str) else "node cancelled by user"
    )
    logger.debug("reason=<%s> | cancelling execution", cancel_message)
    yield MultiAgentNodeCancelEvent(node.node_id, cancel_message)
    raise RuntimeError(cancel_message)
```

That exception is caught by the node's `except` block, which marks the node failed and
then re-raises:

```python
# strands/multiagent/graph.py:1225-1226 -- verbatim, strands-agents 1.63.0
# Re-raise to stop graph execution (fail-fast behavior)
raise
```

The whole graph aborted with `RuntimeError: cancelled by a human before the node ran`.
No `GraphResult` was produced. The graph state held `state_failed_nodes = ['bad']` and
an empty `execution_order`, but there was no result to inspect. The docstring's promise
that sibling branches continue did not hold for this path, because the exception stops
execution before `_find_newly_ready_nodes` is reached. The comment in the `except` block
is explicit about it. It says that all failures stop graph execution, and it says
"Re-raise to stop graph execution (fail-fast behavior)".

I could not produce a run in this version where a node is marked `FAILED` and the
graph still continues to a sibling branch. That is a limit of what I measured, not a
claim that the pruning code is unreachable. If you design around pruning, verify it on
your installed version first.

One more construction-time boundary: a node executor cannot be an `Agent` with a
session manager. The `Agent` constructor accepts one, but `GraphBuilder.add_node`
raises `ValueError: Session persistence is not supported for Graph agents yet.` UC06
found the same restriction in swarms.

## What surprised me

Three things. The predicate ran twice per approved edge, which means a condition with
side effects is a bug waiting to happen. The join ran twice and overlapped a parent it
was supposed to wait for, which means fan-in is an OR over arrivals rather than a
barrier. And the pruning described in a docstring did not survive contact with either
failure I injected. All three came out of the traces rather than out of reading the
source, and the third one contradicts a comment in that source.

## When not to use this

Do not use a graph when you want the model to decide the route. Routing here is a
Python predicate over state and over text that earlier nodes produced; if the decision
needs open-ended judgment, put it inside a node and let the agent choose a tool, as in
UC06. Do not assume a fan-in node sees all its parents, and do not assume it runs once.
Do not ship a cyclic graph without `set_max_node_executions` or
`set_execution_timeout`, and do not treat a cap hit as success. Do not rely on the
pruning behaviour described in `_find_newly_ready_nodes` without testing it yourself.

This experiment does not cover interrupt resumption, `serialize_state`, session-backed
graphs, cross-process A2A, or any workload larger than three short agents in one
process. It does not measure answer quality or cost per useful result. It does not
cover behaviour under model latency spikes. The two failure injections are the only ones I ran; a node that
fails through a different stop reason may behave differently.

## How I measured

Every number above is from one of eight graph runs on 2026-11-13, plus one
construction-time check, with `strands-agents` 1.63.0, `amazon.nova-pro-v1:0` in
`us-east-1`, Python 3.11, one process and no concurrency outside the graph's own
batch. Token counts are the graph's accumulated
usage reported by `GraphResult`, not my own estimate. Timings are the reported
`execution_time` in milliseconds. Wall-clock overlaps come from `BeforeNodeCallEvent`
and `AfterNodeCallEvent` timestamps recorded in the same process. Each run's raw
stdout is in `evidence/*.txt` and its raw fields in `evidence/*.json`; the fixture
input is fixed in `data/brief-input.json` and is byte-for-byte the UC06 file. Model
output varies between runs, so token counts and timings are observations of these
runs, not benchmarks. Each experiment has a control or a complement: the linear chain
against the conditional fork, the capped cycle against the timed one and parallel
entry points against the UC06 swarm trace.

## Try it yourself

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/07-graph
python3 -m venv .venv && . .venv/bin/activate
pip install strands-agents==1.63.0 boto3
export AWS_DEFAULT_REGION=us-east-1
```

The full source, the fixed fixture and all raw evidence are in
https://github.com/pinxiong/strands-in-action/tree/master/usecases/07-graph.
The scripts hard-code `us-east-1` and `amazon.nova-pro-v1:0`, so set the region as
above and provide credentials through `aws configure`, `AWS_PROFILE` or environment
variables. Enable model access for `amazon.nova-pro-v1:0` in that region first, or
Bedrock will reject the call. Then run the nine commands below. Eight of them execute
a graph; the `session` one only checks a construction-time error. The `unbounded`
command builds one limit-free graph it never runs (to capture the warning), then runs
a second copy with a six-second timeout:

```bash
.venv/bin/python src/graph_trace.py --mode linear
.venv/bin/python src/graph_trace.py --mode condition
.venv/bin/python src/graph_fanin.py --mode or
.venv/bin/python src/graph_parallel.py --mode overlap
.venv/bin/python src/graph_limits.py --mode unbounded
.venv/bin/python src/graph_limits.py --mode capped
.venv/bin/python src/graph_failure.py --mode raise
.venv/bin/python src/graph_failure.py --mode cancel
.venv/bin/python src/graph_failure.py --mode session
```

Each script writes its own `evidence/*.txt` and `evidence/*.json`. The fork condition
looks for the literal `3640` in upstream text; if your model phrases the total
differently, the other branch will run. That difference is the point of the experiment,
so check `predicate_log` before comparing your numbers with mine.

## Takeaways

1. Routing is a Python predicate, not a model decision. The model still writes the
   text that the predicate reads.
2. A predicate can be evaluated twice for the same edge, so keep conditions pure.
3. Readiness is an OR over incoming edges in the completed batch. A join can run before
   all its parents finish, and it can run more than once.
4. Downstream nodes receive a rendered string of their completed dependencies, not a
   shared state object.
5. A cycle is unbounded by default. Set a limit and treat a cap hit as `FAILED`.
6. Nodes in one batch really run in parallel, unlike a swarm's serial handoffs.
7. In 1.63.0, both failures I injected either completed the node or aborted the whole
   graph. Verify pruning on your version before depending on it.

The graph is yours. The judgment inside each node, and the words your predicates read,
are not. Design the structure for that boundary. Prove convergence separately.
