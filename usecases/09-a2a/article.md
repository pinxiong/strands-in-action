# Orchestrating Agents: Your Agent Leaves the Process

> Verified on 2026-11-18 against `strands-agents` 1.63.0, `a2a-sdk` 0.3.26,
> `fastapi` 0.163.2, Python 3.11 and Bedrock in `us-east-1`.
> Every number below came out of a run. The scripts and raw output live in
> <https://github.com/pinxiong/strands-in-action/tree/master/usecases/09-a2a>.
> The model is `amazon.nova-pro-v1:0`.

The task in this post is small. A fixture holds three invented per-node token
counts. An agent has to add them with a `sum_tokens` tool and save a short brief
with a `save_draft` tool. Earlier posts in this series ran the same task inside
one process on a swarm, a graph and a workflow tool. This post moves the writer
into a second OS process and calls it over HTTP with A2A (Agent-to-Agent), an
open protocol that lets one agent discover and call another. The Strands Agents
SDK wraps the writer as an `A2AServer` and the caller as an `A2AAgent`. The two
processes share one port and one file on disk. They share nothing else. Here
"orchestrating" means treating that remote agent as one node in a larger piece
of work, not coordinating several agents.

The title is a claim about evidence. Inside one process you can still inspect an
agent's token counters and the real state of a tool call. A process boundary
takes those away. Instead, the caller gets one task state and one string.
The caller's `AgentResult` reports zero tokens for a run that used 2369 on the
far side, whereas a remote tool that raises still produces `completed`. When the
reply never arrives, the remote write has already happened. This post answers
three questions with nine runs: how a remote failure is marked, what a timeout
tells you and what proves that a write succeeded when a step reports success.

One scope note before the trace. This is the open-source Strands Agents SDK, a
Python library that runs inside your own process. The SDK calls its A2A
integration experimental in a log line in its own source. Bedrock supplies the
model. Every run below uses two short prompts, one writer agent and one caller,
on loopback. That is a bench for inspecting a boundary, not a sample of
production traffic. The numbers describe what the runtime reports. They say
nothing about answer quality.

One naming note before the source. `A2AServer` wraps the writer and `A2AAgent`
wraps the caller. I write `a2a_task_state` for the field the converter puts in
`result.state`, and `stop_reason` for the field on the returned `AgentResult`.
They are different facts. Keeping them apart is most of the work below. The
fixture uses `sum_tokens`, `save_draft`, `explode` and `slow` as tool names. An
agent card is a JSON document that describes a remote agent, its transport and
its skills. An artifact is the protocol object that carries a task's output. A
receipt is a line in a JSONL file written by the server process. The key passed
to `save_draft` is an idempotency key that makes a retry harmless. I call an
outcome `unknown` when the caller cannot tell whether the write happened. I call
it `settled` when a readback finds exactly one receipt for that key.

## The boundary is one HTTP port

The point of two processes is to see what a caller can still prove when it
cannot read the other side's memory. The server half is a separate Python
process. It builds a Strands `Agent`, wraps it in `A2AServer` and serves the
Starlette app on a port. The caller half never imports that module. It creates
an `A2AAgent` with the base URL. The client then fetches the agent card before
it sends anything. That card sits at a well-known URL, and it lists the name,
the transport and the skills of the remote agent.

```python
# usecases/09-a2a/src/remote_server.py:26-27 -- verbatim, this bench
server = A2AServer(agent=remote_agent(mode), host=HOST, port=port)
uvicorn.run(server.to_starlette_app(), host=HOST, port=port, log_level="warning")
```

The timeout on the caller side is a plain `httpx` setting. It applies to card
discovery and to message sending. This matters later, because the same clock
covers both and stops the caller while the server keeps running.

```python
# strands/agent/a2a_agent.py:249-252 -- verbatim, strands-agents 1.63.0
# No client_config — create a managed httpx client, consistent with get_agent_card() path
async with httpx.AsyncClient(timeout=self.timeout) as httpx_client:
    config = ClientConfig(httpx_client=httpx_client, streaming=True)
    yield ClientFactory(config).create(agent_card)
```

The first line of that block is a source comment. The other three lines were
shifted left by eight columns to remove the class indent, while their relative
levels stayed.

## What the card tells you before any token is spent

E1 fetches the card from the other process. It costs no model call. The card
names the writer, lists two skills whose descriptions match its tool docstrings
and declares JSONRPC as the transport.

```text
a2a-card.txt (E1), selected fields rewrapped for this page:
card.protocolVersion = 0.3.0
card.preferredTransport = JSONRPC
card.defaultInputModes = ["text"]
card.defaultOutputModes = ["text"]
card.capabilities.streaming = True
card.name = brief-writer
card.skills = [{"id": "sum_tokens", ...}, {"id": "save_draft", ...}]
card.url = http://127.0.0.1:9144/
```

Two lines deserve attention. `defaultOutputModes` contains `text` and nothing
else, so the card offers no typed channel for a result. Each skill description
matches the first line of a tool docstring, so the skills describe what the
writer can do. Neither line says anything about what a completed call proves. In
short, discovery tells you where to send a message. It does not give you a
contract.

## A success is a string

E2 is the happy path. The caller asks the writer to total `[1180, 940, 1520]`,
save a brief under the idempotency key `uc09-happy` and report the receipt id.
The writer uses Bedrock, calls both tools and writes one line to the receipt
file. The caller gets an `AgentResult`.

```text
a2a-happy.txt (E2), selected fields rewrapped for this page:
caller_pid = 50427
remote_pid = 50437
result.stop_reason = end_turn
result.text = <thinking> The save_draft tool has successfully saved the brief
              and provided a receipt id. I will report the receipt id verbatim
              as requested by the user. </thinking> R-001
result.metrics = EventLoopMetrics(cycle_count=0, tool_metrics={}, ...
                 accumulated_usage={'inputTokens': 0, 'outputTokens': 0,
                                    'totalTokens': 0}, ...)
result.state.a2a_task_state = completed
on_disk_receipts = [{"receipt": "R-001", "key": "uc09-happy", "words": 5,
                     "text": "Total tokens: 3640, Cost: $0.002912",
                     "pid": 50437, ...}]
receipt_count = 1
```

The two `pid` values are different processes. In fact, that is the whole
experiment in one field. The receipt id arrives as prose, wrapped in a thinking tag on this
run. In contrast, another run of the same prompt returned just `R-001`. The caller
cannot parse it with a schema, because the protocol never sends a schema.

The reason sits in the executor. It renders the agent result with `str()` and
puts that string into one text part of one artifact.

```python
# strands/multiagent/a2a/executor.py:540-545 -- verbatim, strands-agents 1.63.0
elif final_content := str(result):
    await updater.add_artifact(
        [Part(root=TextPart(text=final_content))],
        name="agent_response",
    )
await updater.complete()
```

The converter on the caller side turns that artifact into an `AgentResult`. It
keeps the protocol task state in a separate dictionary.

```python
# strands/multiagent/a2a/_converters.py:190-192 -- verbatim, strands-agents 1.63.0
state: dict[str, str] = {}
if task_state is not None:
    state["a2a_task_state"] = task_state.value
```

As a result, the caller receives two independent facts. `stop_reason` describes
the local
conversion. `a2a_task_state` describes the remote task. The receipt lives on
disk in the other process. Inside one process a rendered string would go to the
next step. Here it goes to another machine.

## A tool failure is still a completion

E3 swaps the writer's tools for `explode`, a tool that always raises
`RuntimeError`. The caller asks for that tool once. A reader of an earlier post
asked what a downstream gate should check when a step reports success. This is
that case with a network in the middle.

```text
a2a-tool_raise.txt (E3), selected fields rewrapped for this page:
result.stop_reason = end_turn
result.text = "Error: RuntimeError - injected tool failure"
result.state.a2a_task_state = completed
receipt_count = 0
```

The task completed, although the tool raised. The exception became a sentence.
A caller that checks `stop_reason` sees `end_turn`. A caller that checks
`a2a_task_state` sees `completed`. Neither value says that a tool raised. The
string does. However, a string is not a state, so a downstream gate cannot
branch on it without parsing English. Inside one process the same failure left an
orchestrator reporting full success. Moving the step across a socket changed
the transport, not the outcome.

`receipt_count` is zero here, which is the one useful fact. No brief was saved.
The caller cannot learn that from the result. It has to read the receipt file.
E6 and E7 below show the caller doing exactly that.

## The status split

E5 injects a different failure. A hook raises an exception after the real
Bedrock call has finished, so the failure escapes the agent loop itself instead
of being caught inside a tool. The executor has a branch for that.

```python
# strands/multiagent/a2a/executor.py:363-372 -- verbatim, strands-agents 1.63.0
except Exception:
    # Agent execution failures transition to failed state
    logger.exception("task_id=<%s> | agent execution failed, transitioning to failed state", task.id)
    try:
        await updater.failed(
            message=updater.new_agent_message(parts=[Part(root=TextPart(text="Agent execution failed"))])
        )
    except RuntimeError:
        # Task already in terminal state (e.g., completed before error in cleanup)
        logger.debug("task_id=<%s> | task already in terminal state, cannot transition to failed", task.id)
```

Because that failure escapes the agent loop, the caller now sees a different task state.

```text
a2a-agent_raise.txt (E5), selected fields rewrapped for this page:
result.stop_reason = end_turn
result.text = Agent execution failed
result.state.a2a_task_state = failed
receipts = []
```

However, `stop_reason` is still `end_turn`. The failure is real and the protocol
marks it. The local field does not move. The converter maps every terminal task
state to the same local value.

```python
# strands/multiagent/a2a/_converters.py:16-24 -- verbatim, strands-agents 1.63.0
# Mapping from A2A TaskState to Strands stop_reason
_STATE_TO_STOP_REASON: dict[TaskState, StopReason] = {
    TaskState.completed: "end_turn",
    TaskState.failed: "end_turn",
    TaskState.canceled: "end_turn",
    TaskState.rejected: "end_turn",
    TaskState.input_required: "interrupt",
    TaskState.auth_required: "interrupt",
}
```

That table is the direct answer. `TaskState.failed` therefore maps to
`end_turn` in the same way as `TaskState.completed`. The client wrapper also needs one final event
to build a result, so it treats every terminal state as a complete event.

```python
# strands/agent/a2a_agent.py:276-290 -- verbatim, strands-agents 1.63.0
def _is_complete_event(self, event: A2AResponse) -> bool:
    """Check if an A2A event represents a complete response.

    Recognizes all terminal states (completed, failed, canceled, rejected)
    and pausing states (input_required, auth_required) as complete events.

    Args:
        event: A2A event.

    Returns:
        True if the event represents a complete response.
    """
    # Direct Message is always complete
    if isinstance(event, Message):
        return True
```

The block above stops at the direct-message branch. Here is the branch that
handles status updates, and it is the one that matters for E5.

```python
# strands/agent/a2a_agent.py:306-310 -- verbatim, strands-agents 1.63.0
# Status update - check for terminal or pausing states
if isinstance(update_event, TaskStatusUpdateEvent):
    if update_event.status and hasattr(update_event.status, "state"):
        state = update_event.status.state
        return state in _COMPLETE_STATES
```

I call this the status split. `stop_reason` is a local fact about the
conversion. `a2a_task_state` is a remote fact about a task. Neither one is a
receipt for the operation the task was supposed to perform. E3 and E5 give the
same `stop_reason` for a swallowed tool error and for a real agent failure.
Readers asked whether a `failed` or `unknown` state is even visible. The
protocol has `failed`, but it sits in `state`, not where a normal caller looks
first.

## The write that arrived without the reply

E6 is the case that decides where the gate belongs. The writer gets a `slow`
tool that writes a receipt first and then sleeps for six seconds. The caller sets
a two second timeout.

```python
# usecases/09-a2a/src/common.py:161-173 -- verbatim, this bench
@tool
def slow(seconds: int = 6, key: str = "uc09-slow") -> str:
    """Write a receipt first, then sleep before returning. Separates the write from the reply.

    Args:
        seconds: How long to block before returning.
        key: Caller-supplied idempotency key for this operation.
    """
    existing = [r for r in receipts() if r["key"] == key]
    if existing:
        receipt, duplicate = existing[0]["receipt"], True
    else:
        receipt, duplicate = f"R-{len(receipts()) + 1:03d}", False
```

```text
a2a-timeout.txt (E6), selected fields rewrapped for this page:
client_timeout_s = 2
outcome = exception
exception = A2AClientTimeoutError: Timeout Error: Client Request timed out
receipts_at_exception = [{"receipt": "R-001", "key": "uc09-slow",
                          "pid": 51993, "phase": "written_before_reply"}]
write_happened_without_reply = True
caller_could_know_from_result = False
```

The caller has an exception, whereas the remote process has a receipt with its
own `pid`. Both are true at the same time. In other words, that is the `unknown` outcome:
the caller cannot tell whether the write happened. A crashed worker inside one
process made this an edge case. In contrast, across a process boundary a timeout
makes it an ordinary one. An exception from the client tells you that the reply did not
arrive. In other words, it says nothing about whether the write happened.

E7 shows the exit. The caller sends the same request twice with the same
idempotency key and reads the file back.

```python
# usecases/09-a2a/src/common.py:126-137 -- verbatim, this bench
@tool
def save_draft(text: str, key: str) -> str:
    """Save the finished brief under an idempotency key and return a receipt id.

    Args:
        text: The finished brief.
        key: Caller-supplied idempotency key for this operation.
    """
    existing = [r for r in receipts() if r["key"] == key]
    if existing:
        return json.dumps({"receipt": existing[0]["receipt"], "duplicate": True})
    receipt = f"R-{len(receipts()) + 1:03d}"
```

```text
a2a-readback.txt (E7), selected fields rewrapped for this page:
call 1: state.a2a_task_state = completed
call 1: receipt_count_after = 1
call 2: text ends with "The draft has been saved successfully, although it
        was a duplicate. Receipt ID: R-001."
call 2: state.a2a_task_state = completed
call 2: receipt_count_after = 1
receipt_count = 1
same_key_wrote_once = True
```

Two calls, one line on disk. The second run reports a duplicate in its prose,
but the prose is not what makes it safe. The key and the readback do. That is
what `settled` means here: exactly one receipt for that key on a readback. If
the operation writes outside the caller's process, the downstream gate needs a
receipt tied to that operation, an idempotency key so a retry is harmless and a
readback so `unknown` can become `settled`. A wrapper that owns the tool calls
helps, because it can hold the key. It does not replace the readback.

## The ledger ends at the process edge

E8 runs the same brief three ways. A local agent uses the same model and tools
in the caller's process. The remote agent runs the same prompt inside the server
process. A recorder hook in the server writes the remote usage to disk. Then the
caller reads its own `AgentResult`.

```text
a2a-cost.txt (E8), selected fields rewrapped for this page:
local_usage.accumulated_usage.inputTokens = 2126
local_usage.accumulated_usage.outputTokens = 187
local_usage.accumulated_usage.totalTokens = 2313
local_usage.cycle_count = 3
remote_side_usage = [{"pid": 52539, "accumulated_usage":
                      {"inputTokens": 2176, "outputTokens": 193,
                       "totalTokens": 2369}, "cycle_count": 3}]
caller_usage.accumulated_usage.inputTokens = 0
caller_usage.accumulated_usage.outputTokens = 0
caller_usage.accumulated_usage.totalTokens = 0
caller_usage.cycle_count = 0
converter_term_hits.usage = 0
converter_term_hits.token = 0
converter_term_hits.metric = 0
converter_total_hits = 0
```

The local run used 2313 tokens, whereas the server process used 2369 for the
same job. In contrast, the caller reports zero, with `cycle_count` zero and an
empty `tool_metrics`. Those three numbers answer a question readers asked about
an earlier post: where should a token budget live when a timed out node reports
zero? A budget checked on the caller's `AgentResult` reads zero for every remote
call, so the guardrail cannot live there at all.

The last four lines are a static scan of the server-side A2A executor module.
The words `usage`, `token` and `metric` do not appear in it once. That module is
the only place where the server turns an agent result into a protocol message,
and it puts no counters into that message. The converter on the caller side then
builds a fresh `AgentResult` with an empty metrics object.

```python
# strands/multiagent/a2a/_converters.py:194-199 -- verbatim, strands-agents 1.63.0
return AgentResult(
    stop_reason=stop_reason,
    message=message,
    metrics=EventLoopMetrics(),
    state=state,
)
```

In short, the zero in `caller_usage` above is the phenomenon. The result the
caller holds
carries an empty metrics object, so a hook attached to that result has no
counter to read. I did not attach a separate hook. If you need a ceiling, the
server has to meter itself and publish the number through a channel you own. I
did not build that channel here.

## What the orchestrators accept

E9 asks whether the in-process orchestrators can take a remote agent as a node.
An `A2AAgent` is not an `Agent`. Its method resolution order is `A2AAgent`,
`AgentBase`, `Protocol`, `Generic`.

```text
a2a-swarm.txt (E9), selected fields rewrapped for this page:
is_agent_instance = False
Swarm(nodes=[A2AAgent]) -> rejected
  AttributeError: 'A2AAgent' object has no attribute '_session_manager'
GraphBuilder.add_node(A2AAgent) -> accepted
```

A Swarm rejects the remote agent during construction. The error says the object
has no `_session_manager` attribute, which the Swarm tried to read. A
`GraphBuilder` accepts the node and builds a graph. I did not run that graph.
Acceptance at construction time is not evidence that the node executes, so I am
not claiming it does. The SDK documentation says Swarm does not support A2A.
This run shows the exact error.

## What surprised me

E4 records the raw event stream for the same happy prompt. I expected a handful
of status changes. There were 58 events.

```text
a2a-stream.txt (E4), counted from event_sequence:
total = 58
1  TaskState.submitted, update=NoneType
55 TaskState.working, update=TaskStatusUpdateEvent
1  TaskState.working, update=TaskArtifactUpdateEvent
1  TaskState.completed, update=TaskStatusUpdateEvent
```

Fifty-five `working` updates carry the stream. Exactly one artifact carries
the answer. The protocol gives the caller a rich view of a task's progress and a
single string for its result. I counted task-level events. However, the operation behind
them has only that one string. Observability of the task improved, although
observability of the operation did not.

The second surprise was the thinking tag in E2. The model wrapped `R-001` in a
`<thinking>` block on that run and returned the bare id on another. A caller
that greps for a receipt id will sometimes find it and sometimes find it inside
markup. The fixture did not change. Only the model's words did.

## When not to use this

Do not use a plain `A2AAgent` call when the operation has a side effect and you
need to know whether it happened. The result gives you a task state and a
string. It gives you neither a receipt nor a token count. Put the write behind an
idempotency key, keep the receipt in a store the caller can read and gate on a
readback.

Do not use it when you need a cost ceiling on the caller side. The caller's
usage is zero for a real remote run. Meter in the server process and publish the
number yourself.

Do not use it when a downstream step needs typed data. `defaultOutputModes` is
`text`, the artifact is `str(result)`, and a thinking tag can arrive with it. If
you need a schema, validate in the caller before you hand anything to the next
step and treat a parse failure as a failed operation rather than a shorter
answer.

Do not put an `A2AAgent` into a Swarm and expect it to work. Construction raises
`AttributeError`. A `GraphBuilder` accepts one, but I did not execute that graph,
so I cannot tell you what happens at run time.

It is a reasonable fit when the remote operation is read only, or when its side
effects are idempotent and you own the receipt store. In that case the protocol
gives you a clean discovery step, a streaming status channel and a task state
worth logging.

When a call times out, this is the sequence I would use. First, keep the same
idempotency key and retry. Second, read the receipt store for that key. Third,
if exactly one receipt is there, mark the operation `settled` and move on.
Finally, if no receipt appears after a bounded number of retries, treat the
outcome as still `unknown` and do not let a downstream step assume success.
Surface it for a human instead. This bench does not set that retry bound and
does not test what happens when the receipt store itself is unavailable.

This experiment does not cover authentication or SigV4, multi-tenant context
isolation, real network partitions, streaming artifact schemas, provider-side
ledger reconciliation or answer quality and cost per useful result. It also
does not cover executing an `A2AAgent` node inside a graph. Those are the limits
I did not test. The three questions about `failed`, `unknown` and the operation
receipt are not in this list. E3, E5, E6 and E7 measure them.

## How I measured

All numbers come from nine experiments on 2026-11-18, with `strands-agents`
1.63.0, `a2a-sdk` 0.3.26, `fastapi` 0.163.2, `amazon.nova-pro-v1:0` in
`us-east-1`, Python 3.11 and two OS processes per call. The fixture
`data/brief-input.json` is byte-for-byte the file used in the earlier posts in
this series. E1 and E9 make no model call. Every other experiment reaches
Bedrock at least once. E7 and E8 each make two agent invocations. Token counts
come from `accumulated_usage` on the real agent result, recorded inside the
server process by an `AfterInvocationEvent` hook. The caller counts come from the
`AgentResult` that `A2AAgent` returns. Wall-clock time is measured around the
call. Each experiment writes its own `evidence/*.txt` and `evidence/*.json`. The
text blocks above rewrap selected fields for the page width, so the byte-exact
lines live in those files. Model output varies between runs, so the receipt ids
and word counts are observations of these runs, not benchmarks. Every failure
run has a control: the swallowed tool error against the real agent failure, the
timeout against the readback, and the local agent against the remote one. The
static scan counts case-insensitive substring hits in the installed
`executor.py`. It found zero.

## Try it yourself

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/09-a2a
python3 -m venv .venv && . .venv/bin/activate
pip install "strands-agents[a2a]==1.63.0" a2a-sdk==0.3.26 \
  fastapi==0.163.2 uvicorn==0.54.0 boto3
export AWS_DEFAULT_REGION=us-east-1
```

The `[a2a]` suffix is an optional extra that brings in the protocol's HTTP
server dependencies. The explicit pins match the versions used for these runs.
The full source, the fixed fixture and all raw evidence are in
<https://github.com/pinxiong/strands-in-action/tree/master/usecases/09-a2a>.
Use Python 3.11 for the venv. The scripts hard-code `us-east-1` and
`amazon.nova-pro-v1:0` in `src/common.py` and pass the region explicitly to
`BedrockModel`, so `AWS_DEFAULT_REGION` is only a boto3 default. Provide
credentials through `aws configure`, `AWS_PROFILE` or environment variables.
Enable model access for `amazon.nova-pro-v1:0` in that region first. Bedrock
will reject the call otherwise. Then run the nine experiments:

```bash
.venv/bin/python src/probe_card.py
.venv/bin/python src/probe_trace.py --mode happy
.venv/bin/python src/probe_trace.py --mode tool_raise
.venv/bin/python src/probe_trace.py --mode stream
.venv/bin/python src/probe_failure.py --mode agent_raise
.venv/bin/python src/probe_failure.py --mode timeout
.venv/bin/python src/probe_failure.py --mode readback
.venv/bin/python src/probe_cost.py
.venv/bin/python src/probe_swarm.py
```

Each script starts its own server process on a port between 9144 and 9152,
waits for the agent card, runs the probe and terminates the server.
Consequently, you do not need two terminals. The receipts and server logs go to `/tmp/uc09-a2a` unless
you set `UC09_STATE_DIR`, and every script clears that directory at startup, so
run them one at a time. The timeout probe waits about eight seconds after the
exception to let the remote write finish. `probe_cost.py` runs one local agent
and one remote call, so it takes longer than the others. Read `first_prompt` in
each JSON before comparing your numbers with mine: the exact words the model
produces differ between runs, while the receipt, the task states and the token
counters do not.

## Takeaways

1. An A2A call gives the caller a task state and a string. `defaultOutputModes`
   is `text`, and the executor builds the artifact with `str(result)`.
2. A remote tool that raises still produces `completed` and `end_turn`, with the
   exception rendered as a sentence. That failure mode survives the socket.
3. An agent-level exception produces `a2a_task_state = failed`, but
   `stop_reason` stays `end_turn`. The wrapper treats every terminal state as a
   complete event, so the two fields are a status split and neither is a receipt.
4. A client timeout says the reply did not arrive. On this bench the receipt was
   already on disk in the other process, so the outcome is `unknown`.
5. A retry with the same idempotency key wrote once across two calls. The
   readback, not the prose reply, turns `unknown` into `settled`.
6. The local run used 2313 tokens and the remote process used 2369. The caller
   reported zero, and the executor module contains no `usage`, `token` or
   `metric` reference at all. A cost gate cannot sit on the caller's result.
7. The stream carried 58 events, with 55 `working` updates and one artifact.
   Task progress is observable. The operation behind the task is not.
8. An `A2AAgent` is not an `Agent`. Swarm rejects it with `AttributeError`, and
   a `GraphBuilder` accepts it at construction time only, which I did not run.
9. Put the receipt, the idempotency key and the metering outside the agent. The
   process boundary did not create the contract. It made the missing one
   impossible to ignore.

The agent left the process. The evidence stayed behind, so go and read it.
