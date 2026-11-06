# UC03 · Execution Limits

> Verified on 2026-11-05 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. The model is `amazon.nova-pro-v1:0` (switch with `MODEL_ID=deepseek.v3.2`).
> Every number below came out of a run; raw output lives in `evidence/`.

One agent that wants to loop, four boundaries that can stop it, and what each
boundary actually measures — measured, not documented.

## What the experiments show

| Script | Boundary | Finding |
|---|---|---|
| `src/turn_limit.py` | loop turns | Run A (no limits) takes 9 turns and only ends because the tool text says so; `turns=3` stops at the cap with `limit_turns` |
| `src/turn_batching.py` | loop turns | Same 8 tool calls: 9 turns under a sequential prompt, 3 turns under a parallel prompt — a turn limit bounds model calls, not tool invocations |
| `src/turn_granularity.py` | loop turns | 5 identical runs, all 8 calls over 9 turns (0.9 calls/turn) — per-run batching varies across models and runs |
| `src/token_budget.py` | output tokens | A single-turn answer never hits the check (cap 80, actual 255, `end_turn`); a tool loop stops at the next boundary (cap 100, actual 109, `limit_output_tokens`) |
| `src/total_token_budget.py` | total tokens | Each cycle re-reads the whole conversation (input 434→559→657→755) and cumulative spend overshoots the cap at the boundary |
| `src/cancel_watchdog.py` | wall clock | Cancel during streaming returns in 3.0 s; cancel while a sync tool sleeps 20 s returns in 21.9 s — cancellation waits at safe points |
| `src/tool_quota.py` | tool quota | A `BeforeToolCallEvent` hook turns call 3+ into an error result the model reads and adapts to; the loop itself ends naturally |
| `src/limits_validation.py` | all | Unknown keys, zero and `True` all raise `TypeError` before any model call runs |

## Reproduce

From the repository root, create this use case's environment the way the top-level `README.md`
describes (`uv venv --python 3.11`, then `VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0`),
activate it and run the scripts from this directory:

```bash
cd usecases/03-execution-limits
source .venv/bin/activate
python src/limits_validation.py   # no Bedrock calls
python src/turn_limit.py          # 3 probes, ~9 turns
python src/turn_batching.py       # 2 probes
python src/turn_granularity.py    # 5 identical runs
python src/token_budget.py        # 2 probes
python src/total_token_budget.py  # 1 probe, ~4 turns
python src/cancel_watchdog.py     # 2 probes, ~25 s sleep
python src/tool_quota.py          # 1 probe
```

## Source anchors (strands-agents 1.63.0)

- `types/agent.py:150-190` — `Limits` TypedDict: `turns`, `output_tokens`, `total_tokens`, `structured_output_attempts`; "Limits are checked before each turn"; priority turns > total_tokens > output_tokens > structured_output_attempts
- `agent/invocation_context.py:87-103` — `_take_turn`: check and count in one atomic step
- `agent/invocation_context.py:229-262` — `_reached_limit` / `_reached_own_limit`: the four checks in priority order
- `agent/invocation_context.py:160-181` — `_validate_limits`: positive int, rejects bool, rejects unknown keys
- `event_loop/event_loop.py:217` — cycle start: `limit_stop_reason = invocation_context._take_turn()`
- `event_loop/event_loop.py:1166` — cancel checkpoint: `agent._deferred_cancel or agent._observe_cancellation()`
- `agent/agent.py:686-690` — the four cancellation safe points: during streaming, before tool execution, during MCP tool execution, after tool execution
- `agent/agent.py:680-735` — `agent.cancel(message=..., after_current_tools=...)`
- `hooks/events.py:221-247` — `BeforeToolCallEvent.cancel_tool`: quota mechanism
- `types/event_loop.py:42-74` — `StopReason` taxonomy incl. the four `limit_*` reasons
