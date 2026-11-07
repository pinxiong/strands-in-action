# Draft replies (Dev.to comments on "The Limits That Don't Limit")

## Reply 1 — to Pierre-Laurent Medori

All three held up when I re-ran them against 1.63.0, and the first one changes what the article should say. The numbers below are from my runs; the line numbers are from the installed `strands-agents==1.63.0`.

**1. `cancelled` does not roll the tool back — confirmed, with the exact reason.**

The event loop appends the tool result *before* it observes the cancellation:

```python
# strands/event_loop/event_loop.py:1135
await agent._append_messages(tool_result_message, invocation_context=invocation_context)

# strands/event_loop/event_loop.py:1166
if agent._deferred_cancel or agent._observe_cancellation():
```

So a run that ends `cancelled` can still carry a success result for a tool that already ran. I re-ran the article's 20-second tool probe with a transcript dump — `agent.cancel()` fired 5 s into a `time.sleep(20)` tool:

```
ELAPSED_S   : 21.7
STOP_REASON : cancelled
TOOL RESULTS IN agent.messages:
  [success] report ready: all checks green
```

The loop waited for the tool, recorded its result, and then stopped. `cancelled` is a statement about the loop, not about the side effect. If the tool can charge a card, the retry path needs an idempotency key and a read-back of the effect's own record before retrying — not just a check of `stop_reason`.

**2. `tool_context.cancel_signal` — confirmed, and this is the part the article left out.**

It is the documented cooperative exit. From the `ToolContext` docstring at `strands/types/tools.py:191-195`:

> cancel_signal: Cancellation signal for this tool call. Poll `cancel_signal.is_set()` between steps, or forward it to an API that accepts one (e.g. `MCPClient.call_tool_async`). A tool that ignores it runs to completion.

One gotcha I hit while testing: the decorator must opt in, or the SDK refuses the signature — write `@tool(context=True)`, otherwise you get `ValueError("@tool(context) must be set if passing in ToolContext param")` (`strands/tools/decorator.py:183`).

Same probe with the sleep swapped for the wait:

```python
@tool(context=True)
def slow_report(tool_context: ToolContext) -> str:
    got = tool_context.cancel_signal.wait(20)
    if got:
        return "aborted before doing any work: cancel signal received"
    return "report ready: all checks green"
```

Output:

```
ELAPSED_S   : 5.0
STOP_REASON : cancelled
  [success] aborted before doing any work: cancel signal received
```

5.0 s instead of 21.7 s, and nothing was done. The `time.sleep(20)` in the article was the deliberate worst case, but the text never says the cooperative version exists. I am adding it to the deadline section.

**3. Limits restart per top-level call — confirmed, and it is documented behavior, not an accident.**

From the `Limits` docstring at `strands/types/agent.py:165-166`:

> Usage starts from zero on each top-level call; pass `result.invocation_context` to a later call to continue on the same limits and usage.

`AgentResult` carries the handle: field at `strands/agent/agent_result.py:50`, with the docstring at :37-40 ("Pass it as `invocation_context` to a later call to continue on the same limits and usage"). One detail that cost me a minute: `limits` is a per-call argument, not a constructor one (`strands/agent/agent.py:929`).

Measured with `limits={"turns": 1}` on one agent, three calls:

```
CALL_A (fresh top-level, limits turns=1):         stop=limit_turns usage={"turns_taken": 1, "inputTokens": 408, "outputTokens": 47, "totalTokens": 455}
CALL_B (new top-level, no context passed):        stop=limit_turns usage={"turns_taken": 1, "inputTokens": 493, "outputTokens": 47, "totalTokens": 540}
CALL_C (passes result.invocation_context from B): stop=limit_turns usage={"turns_taken": 1, "inputTokens": 493, "outputTokens": 47, "totalTokens": 540}
```

B got a fresh budget and spent 540 real tokens. C, given B's context, spent zero — its usage is identical to B's, meaning it never reached the model: the inherited budget was already exhausted, so the first turn check stopped it.

**On your question** — one context across retries, or cap attempts in the queue: neither alone, and which applies depends on what the retry *is*.

- Retry as **continuation of the same request** (resume after a cancel, or after a limit stop): keep the one `invocation_context`. Re-spending that budget is legitimate — it is the same request finishing.
- Retry as **a new attempt of the same job**: fresh budget per attempt, cap the attempts one level up. An attempt that inherits an exhausted budget just dies at the same wall (that is call C above), and an attempt with no job-level counter has no ceiling on total spend across attempts. The job total belongs outside the agent, with the queue.

## Reply 2 — to Kent Bodrov

Confirmed, and the hook is even narrower than "per-invocation": in the article's probe the counter is a plain `defaultdict` in the caller's closure (`src/tool_quota.py:42`), registered on one agent instance (`src/tool_quota.py:57`). Two workers on the same job are two processes with two counters, so 2 + 2 attempts both pass. It is a per-process budget, not a per-job one — fine for bounding one run, useless for bounding a job.

Your design is the right shape. Concretely:

1. **Reserve before the attempt**: a conditional write on a job-level record (DynamoDB conditional put on `job_id`, or Redis `INCR` with a TTL as the cheap version). The atomicity has to live in the store, not in any worker.
2. **Tie the reservation to the side effect**: the attempt id becomes the idempotency key handed to the tool that performs the external effect, so a replayed attempt is a no-op at the effect, not a second charge.
3. **Release only after confirmation**: on timeout or crash, reconcile by reading the effect's own idempotency record — not by assuming nothing happened.

Step 3 is where this connects to the thread above: in 1.63.0 a `cancelled` invocation can still have run its tool to completion and recorded the result (the loop appends the tool result at `strands/event_loop/event_loop.py:1135` and only then checks cancellation at `:1166`). So "the run was cancelled" is not grounds for releasing the reservation. Release on cancel and you have built a double-spend.
