# Orchestrating Agents: Nobody Decides Who Goes Next

> Verified on 2026-11-11 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. Every number below came out of a run. The scripts and raw output live in
> https://github.com/pinxiong/strands-in-action/tree/master/usecases/06-swarm.
> The model is `amazon.nova-pro-v1:0`.

Three agents share one task. A researcher reads a fixed input file and states three
findings. A calculator adds up the per-node token counts and prices the total. A writer
turns the result into a short brief and saves it. Nothing in that description says who
decides which agent runs next.

No component does. There is no scheduler, no route table and no orchestrator holding a
queue. The runtime asks each agent node one question at the end of its turn, and the node
answers by calling a tool. Call the tool and control moves, because the runtime treats that call
as a request rather than an order. Say nothing and the swarm runtime declares the task complete.

That sentence is the whole design, and most of the surprises follow from it. This post
walks the mechanism through source and through runs. A node that stops talking ends the
job. A handoff dies with the node that requested it. Two runs of the same task both report
success while producing a six-word and an eight-word deliverable.

One scope note before the trace. Every run below happens in a single process with three
agents, one model and a task small enough to finish in fifteen seconds. That is a bench for
inspecting a mechanism, not a sample of production multi-agent traffic, and the numbers
describe the runtime's behaviour rather than the quality of its output.

![The handoff loop: each node either calls handoff_to_agent or ends the
swarm](/images/orchestrating-swarm/swarm-handoff-loop.png)

## The scheduler is one injected tool

`Swarm` gives every node exactly one coordination tool. The docstring below is the entire
protocol that a model sees, and the model writes the routing decision into two ordinary
arguments:

```python
# strands/multiagent/swarm.py:648-650 -- as installed, strands-agents 1.63.0
        @tool
        def handoff_to_agent(agent_name: str, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
            """Transfer control to another agent in the swarm for specialized help.
```

The runtime then runs a plain loop. After each node finishes, it looks at one field. The
trimmed branch below is the only place where control moves, and its `else` is the only
place where a swarm says it is done.

```python
# strands/multiagent/swarm.py:932-957 -- trimmed to the handoff branch and its else
                if self.state.handoff_node:
                    previous_node = current_node
                    current_node = self.state.handoff_node

                    self.state.handoff_node = None
                    self.state.current_node = current_node
                    ...
                    yield handoff_event

                else:
                    logger.debug("node=<%s> | no handoff occurred, marking swarm as complete", current_node.node_id)
                    self.state.completion_status = Status.COMPLETED
                    break
```

So the routing decision is a tool invocation, evaluated by a model, on a node that is also
doing the actual work. The decision still happens at every hop. It happens inside a model's
tool call instead of inside your code, which is what the title means: no component holds
the plan. That is what "decentralized" means here at the code level, and it is why the
pattern gives you dynamic routing without giving you a controller.

## Completion by silence

I gave the bench a task with a checkable output. The input file fixes three token counts
(1180, 940 and 1520) and a price per thousand tokens (0.0008), so the correct total is
3640 and the correct cost is 0.002912. The writer's only job is to save a brief with
those two numbers in it.

In the first run all three nodes did their part. The trace below is the run's own output:

```text
status            : completed
execution_count   : 3
node_history      : researcher -> calculator -> writer
wall clock        : 15.299s
total tokens      : 8857

  researcher  status=completed  model_calls=3 tokens=3549  in=3220  out=329  wall=6614ms
  calculator  status=completed  model_calls=3 tokens=3356  in=3132  out=224  wall=4774ms
  writer      status=completed  model_calls=2 tokens=1952  in=1798  out=154  wall=3909ms
```

Three counters in that block count different things, and the difference matters later.
`model_calls` counts round trips to the model inside one node turn, so a node that reads the
input, hands off and then writes one closing sentence logs three. `execution_count` counts
node turns that finished, which is why a timed-out node leaves it at zero. `node_history`
lists the nodes that ran to completion, in order.

The deliverable that `save_draft` received was this, in full:

```text
Total token count: 3640. Cost in USD: 0.002912.
```

Eight words, against an input file that requests a brief of one hundred words or fewer.
That count satisfies the cap literally, so a lawyer would call it compliant. A reader would
not.

Then I ran the same bench with one change. The entry node was told to summarize the topic
in a sentence and finish, with no tool calls at all. The writer, which owns `save_draft`,
never ran:

```text
status            : completed
execution_count   : 1
node_history      : researcher
wall clock        : 8.167s
total tokens      : 718

  researcher  status=completed  model_calls=1 tokens=718
  calculator  status=never ran
  writer      status=never ran

tool ledger:
```

Both runs report `completed`. The second one never produced a deliverable, never called
the calculator and spent 718 tokens instead of 8857, so the status field cannot tell the
two apart, because it is not measuring the task. It is measuring whether anyone asked for
help.

I will call that state **completion by silence**, and it is the first thing to internalize
about a swarm. `completed` means the last node did not hand off, and nothing more.

That gap is not a bug in the SDK, because the loop has one input, the node's last message,
and one question, whether any node wants to go next. Since nothing in that loop reads the
deliverable, the deliverable cannot influence the status, which is why a swarm that
produced six words and a swarm that produced nothing both look healthy from the outside.

I then ran the same bench again, with no code change and no prompt change. It completed
with `execution_count: 3` and 8605 tokens, and its `save_draft` entry holds six words
against the eight words of the first run. Both traces are in `evidence/swarm-trace.txt`. So
even the happy
path has no quality gate. The swarm returns when the model stops talking, and the model
decides when to stop.

## A handoff is a state write, not a jump

The tool name suggests a jump, but the implementation is a write. When a node calls
`handoff_to_agent`, the tool stores a target and a message on the swarm's state and returns
immediately, which is why the name promises a jump while the code performs a write.

```python
# strands/multiagent/swarm.py:689-695 -- inside _handle_handoff
        self.state.handoff_node = target_node
        self.state.handoff_message = message

        # Store handoff context as shared context
        if context:
            for key, value in context.items():
                self.shared_context.add_context(current_node, key, value)
```

Control moves only after the node's turn ends, at the branch shown earlier, so two
consequences follow from that delay.

A node keeps working after it hands off, and the last handoff wins, because each call
overwrites the same field. If a model calls the tool twice in one turn, the first target
never runs.

More sharply, a handoff dies with the node that requested it. I built a node that calls
`handoff_to_agent` and then a tool that blocks for ten seconds, with `node_timeout` set to
four. The tool order hook confirms the sequence, handoff first, then the blocking call.

```text
calculator_tool_order: ["handoff_to_agent", "slow_step"]
status               : failed
execution_count      : 0
node_history         : []
handoff_node_after_run: null
writer_status        : never ran
elapsed_s            : 4.012
total_tokens         : 0
```

The rollback is deliberate, because `_rollback_uncommitted_turn` (swarm.py:703-713)
restores the handoff field to the value it had before the turn started, so a dying node
cannot promote a successor it will never brief. That is the right call for correctness and a
bad deal for observability. The node burned
model calls, and the failure report says zero tokens, because the timeout is raised around
the node's stream and the node never produced a result record at all (swarm.py:913-921).
Its usage was never added to the swarm total.

## The context is rebuilt, not forwarded

A node does not inherit the previous node's conversation, because before each node runs
the runtime resets its executor to the state it had at construction time, which wipes the
message list and the agent state together. That reset happens right before the node's agent
starts streaming.

```python
# strands/multiagent/swarm.py:999 -- in _execute_node, before the agent streams
            node.reset_executor_state()
```

It then feeds that node a text block assembled from four pieces: the handoff message, the
original user request, the list of previous agents and whatever earlier nodes wrote into
`shared_context`. Here is what the writer actually received, taken from the node's own
message list after the run:

```text
Context:
Handoff Message: The total token count is 3640 and the cost in USD is 0.002912.

User Request: Produce a short brief. The input file holds the topic, the raw points and
the per-node token counts.

Previous agents who worked on this: researcher → calculator

Other agents available for collaboration:
Agent name: researcher.
Agent name: calculator.

You have access to swarm coordination tools if you need help from other agents. If you
don't hand off to another agent, the swarm will consider the task complete.
```

Read the second line of that block again: the runtime tells every node, in its prompt,
that silence counts as completion. The instruction is not hidden in documentation, because it is
part of the text the model reads before it decides anything.

Two things about this design matter more than they look, and both come from the same
function. `shared_context` is keyed by the sending node, not the receiving one, because
`add_context` is called with `current_node` as the owner. The writer reads a dictionary of
what each peer chose to say,
not a shared whiteboard. Had the researcher passed `context={"total": 3640}`, the block
above would carry one more line, `• researcher: {'total': 3640}`, because `_build_node_input`
prints every node's entries under that node's own name. Second, everything the next node
knows is what the previous node
put into the handoff message. A detail the researcher forgets to mention is gone, and the
researcher has no way to check that the writer still has it.

That is why the same task produced a six-word and an eight-word deliverable. The writer
saw one number pair and nothing else, because the researcher's handoff message carried the
numbers and left the hundred-word cap behind in its own context.

## One counter, two names

`Swarm` accepts two limits that read like separate knobs, and the source compares both
against the same counter:

```python
# strands/multiagent/swarm.py:211-216 -- both checks read len(self.node_history)
        if len(self.node_history) >= max_handoffs:
            return False, f"Max handoffs reached: {max_handoffs}"

        # Check iteration limit
        if len(self.node_history) >= max_iterations:
            return False, f"Max iterations reached: {max_iterations}"
```

So the effective cap is the smaller of the two, and the larger one is decoration. I ran
two agents that hand the task back and forth and never finish it, once with
`max_iterations=3, max_handoffs=20` and once with `max_handoffs=3, max_iterations=20`:

```text
cap=iterations  status=failed  turns=3  history=alpha -> beta -> alpha  reason="Max iterations reached: 3"
cap=handoffs    status=failed  turns=3  history=alpha -> beta -> alpha  reason="Max handoffs reached: 3"
```

The stopping point is identical and the reason string differs, because the run that says
"Max handoffs reached" used the handoff knob and stopped on turn three, which is exactly
where the iteration knob would have stopped it. That pair is also the cleanest evidence of
dynamic routing: the route cycled because the models kept choosing to hand back, and the
runtime followed them without objecting.

Both runs also report `failed`, not `completed`. Hitting a cap marks the swarm as
failed (swarm.py:836), so an unbounded ping-pong shows up as a failure rather than a partial
success. If you plan to retry on failure, know that this case
will keep failing for as long as the prompt keeps making the agents pass the ball.

## A broken tool does not stop the swarm

The failure I expected and the failure I got were different. I gave the calculator a tool
that always raises and asked it to hand off before calling that tool. The tool invocation
failed and the node did not:

```text
status          : completed
execution_count : 2
node_history    : calculator -> writer
calculator_tool_order: ["handoff_to_agent", "explode"]
total_tokens    : 22371
elapsed_s       : 45.967
```

Strands hands the exception back to the model as a tool result, so the model read the error,
continued its turn and kept the handoff it had already requested. The writer then ran, and
it called `save_draft` eleven times in that one turn, because the model kept deciding the
brief needed saving again. Every one of those invocations succeeded.

Nothing in the swarm objected to any of it, because nothing in the swarm is watching the
deliverable and the loop only asks whether somebody wants to go next.

This is the cost of removing the controller, because a tool error is contained by the agent
loop and a slow node is contained by `node_timeout`, so neither one turns into a swarm
event. If you want a swarm that notices a wrong answer, the check has to live in a node, in
a hook or in the destination. It cannot live in the topology, because there is no topology.

## Where a human can stand

A swarm exposes two places for a person to intervene, and both are node-level.

The first is `BeforeNodeCallEvent`, where a hook can cancel a node before it starts and
carry a reason into the trace.

```text
status          : failed
execution_count : 1
node_history    : ["researcher"]
cancel_events   : [{"node": "calculator", "message": "a human stopped this node"}]
total_tokens    : 3194
```

That hook is the only pre-emption point I found, since it runs between nodes and never
inside one, so a person cannot stop a node that is already spending tokens. The same limit
applies to
the interrupt mechanism: the swarm records an interrupt between turns and resumes from a
node boundary.

The second place is the node's own agent, which can call `tool_context.interrupt` inside a
tool to pause the invocation, but that is more machinery than this post needs.

One thing a node cannot do is keep its own session, because attaching a session manager to
a node's agent makes the swarm refuse to construct.

```text
ValueError: Session persistence is not supported for Swarm agents yet.
```

That is a one-line guard at swarm.py:611-612, and it shapes what a swarm can be. A node
starts every turn from its construction state by design, so per-node memory would contradict
the pattern rather than extend it.

## What surprised me

- The runtime tells the model, in the node's prompt, that silence means done. I had assumed
  the termination rule lived in the SDK and stayed invisible to the model. It is printed in
  the context block, four lines under the user request.
- The swarm spent 8857 tokens to produce an eight-word deliverable, and 8605 tokens on the
  next run to produce a six-word one. Of the first total, 8150 tokens were input, so the
  budget went into re-reading context rather than into writing.
- Token accounting disappears on a timeout. The failed node used model calls for four
  seconds and the report says zero tokens.
- A swarm node has no parallelism to speak of. In every run the node intervals touched
  exactly, with no overlap, because the loop awaits one node stream at a time. Whatever
  else the pattern gives you, it does not give you concurrency inside one invocation.

## When not to use this

- Do not use a swarm when the route has to be auditable ahead of time. The route is a
  model's tool call, so the only record of it is `node_history` after the fact.
- Do not use a swarm to save tokens. The three nodes made eight model calls and spent 8857
  tokens to produce eight words, and 8150 of those tokens were input.
- Do not use a swarm when the deliverable has a shape requirement that nobody enforces.
  My bench asked for a brief and got eight words, twice. Nothing in the pattern checks that.
- Do not use a swarm for parallel work. This pattern routes; it does not fan out. If you
  need two agents running at once, the loop here will not do it.
- Do not expect per-node memory. The constructor rejects a session manager on a node, and
  `reset_executor_state` wipes the conversation between turns on purpose.

This experiment does not cover the repetitive handoff detector, which is off by default and
would have stopped my ping-pong pair earlier. It also does not cover resumption from a
session, where the documentation warns that recovery is at-least-once and nodes therefore
need to be idempotent (swarm.py:1163-1166). That warning matters for anyone combining this
pattern with the crash boundaries from
[article 05](https://xiongpin.dev/posts/reservations-fencing/), and I have not tested the
combination.

## How I measured

`model_calls` comes from an `AfterModelCallEvent` hook on each node's agent, and the
wall-clock intervals come from `BeforeNodeCallEvent` and `AfterNodeCallEvent` on the swarm.
Tokens are the SDK's own `accumulated_usage` per node, summed by the swarm. I recorded no
dollar cost, because Bedrock pricing differs by region and by model, and the fixture's price
per thousand tokens exists to make the arithmetic checkable rather than to model a real
bill.

## Try it yourself

Clone the repository first, then install the pinned SDK. The model calls need Bedrock access to `amazon.nova-pro-v1:0` in `us-east-1`:

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/06-swarm
uv venv --python 3.11
VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0
```

Then run the scripts that produced every number above:

```bash
python src/swarm_trace.py --mode happy       # three nodes, real handoffs, ~15s
python src/swarm_trace.py --mode silent      # entry node says nothing, ends the swarm
python src/swarm_limits.py --cap iterations  # ping-pong pair, stopped at 3
python src/swarm_limits.py --cap handoffs    # same three turns, different reason string
python src/swarm_failure.py --mode toolerror # a broken tool, a completed swarm
python src/swarm_failure.py --mode timeout   # a handoff that dies with its node
python src/swarm_failure.py --mode cancel    # a human cancelling one node
python src/swarm_failure.py --mode session   # no model call, fails at construction
```

Run the happy path twice and diff the two `save_draft` entries. The word counts in
`evidence/swarm-trace.txt` came from two such runs, and the difference is the honest
measure of how much the swarm controls its own output.

## Takeaways

- `completed` means "no node asked for help". Treat it as a liveness signal, not a quality
  signal. Put the acceptance check somewhere that can fail.
- The router is a tool in the model's tool list. That is the entire decentralization story,
  and it is why the pattern needs no configuration and offers no guarantee.
- A handoff is a state write applied after the turn. It can be overwritten inside the turn
  and it is rolled back if the node dies, so the successor a dying node named never runs.
- Each node starts from a rebuilt prompt. The handoff message plus `shared_context` is the
  entire channel between nodes, and the sender decides what crosses it.
- `max_handoffs` and `max_iterations` are the same counter. Set the one you mean and do not
  assume the other one protects you.

The next piece in the series keeps the same task and the same three roles. It replaces the
free-for-all with a graph you draw yourself. The question there is the mirror image of this
one: if you name every node and every edge, which decisions are left to the model and what
does the structure actually buy you?
