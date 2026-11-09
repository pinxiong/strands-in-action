# When "Not Found" Doesn't Mean "Never Happened"

> Verified on 2026-11-09 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. Every number below came out of a run, and the scripts live in
> `usecases/05-reservations-fencing/src/` with raw output in `evidence/`. The model in
> the agent experiments is `amazon.nova-pro-v1:0`.

A reader of [article 03](https://xiongpin.dev/posts/execution-limits/) left three questions
under the piece, and each one tightened on the last. A limit counts what happens inside one
call, so what stops two concurrent attempts from each spending a full remaining quota? When
a request was submitted but the response was lost, how do you know that "not found" means
"never happened"? And when the crash lands before or after the side effect, is returning
the capacity safe in both cases?

Those questions share one blind spot. Limits, leases and lookups all answer questions
about a moment in time, which is why the answers stop being true the moment after they
are given. This post builds the smallest system that fails, fails it on purpose and then
makes it safe twice, once at the reservation and once at the destination.

One scope note before anything else. The experiments here are threads on one machine with
real clock leases, and the "external system" is an object guarded by a thread lock. This is
a simulation of a distributed system, not a distributed system, and I will not claim
otherwise. What the simulation gives you is exact, repeatable timing evidence for the state
machines involved, which is the part most explanations wave their hands at.

## What the SDK already gives you

The natural first question is whether any of this is already built in, so I probed the
boundary of what one `Agent` instance does when two workers call it at once.

Two threads invoked the same instance with different prompts. The first call won. The
second one raised:

```text
ConcurrencyException: Agent is already processing a request.
Concurrent invocations are not supported.
```

That is the documented default. The constructor argument `concurrent_invocation_mode`
defaults to `THROW`. `UNSAFE_REENTRANT` is the explicit opt-out for code that accepts
the risk
([agent.py:268](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/agent.py),
[types/agent.py:205](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/types/agent.py)).

The second probe was more interesting. The call signature accepts an `idempotency_token`
([agent.py:928](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/agent.py)).
When a second thread called the same instance with the same prompt and the same token,
the duplicate did not crash and did not run the model twice. It waited for the inflight
invocation and received its cached result. Both threads reported identical usage, 948 total
tokens each, because only one invocation ever ran
([_concurrency.py:183](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)).

So the SDK already distinguishes "concurrent invocations" from "the same request twice."
It handles the second one correctly. The third probe found the boundary. Two separate
instances, one thread each, each invocation carrying `limits={"turns": 1}`, both ran to
`stop_reason="limit_turns"` with identical per-invocation budgets of 453 total tokens. No
budget was shared between them, and none could be, because each instance tracks its own
invocation lock and its own usage
([_concurrency.py:107](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)).

In short, the SDK serializes an instance, dedupes a repeated token in-process and budgets
each instance separately. A quota that several workers must share is still yours to build,
which is where leases come in and where the trouble starts.

## What a lease can and cannot tell you

The minimal system has one capacity slot, one worker that reserves it and one external
system, a ticket service, that records side effects. The worker reserves the slot, performs
the effect and confirms. If the worker dies anywhere in that sequence, the lease on the
slot expires after one second of real clock time, and a janitor thread observes the expiry
and decides what to believe.

The naive policy treats expiry as proof of innocence: the slot is free, so the operation
never happened, so a retry worker re-executes the job. I crashed the worker after the effect
had landed but before the confirmation and ran the race five times.

```text
POLICY=naive CRASH=after-effect
  trial 1: expiry@1.0s effect@0.205s retry@1.204s effects=2 duplicates=1
  trial 5: expiry@1.009s effect@0.201s retry@1.214s effects=2 duplicates=1
SUMMARY trials=5 duplicate_writes_total=5 capacity_returned_while_effect_exists=5/5
```

Every run wrote the ticket twice. Every run handed the capacity back while a completed
effect was sitting in the external system. The lease told the truth, just not the truth the
policy needed. "The worker stopped reporting" is a fact about the worker.
"The operation did not happen" is a fact about the external system, which a lease cannot
see.

The reconcile policy separates the two facts. On expiry it holds the reservation in an
`outcome_unknown` state and asks the external system whether the idempotency key exists
before touching capacity. When the crash lands after the effect, the lookup finds the
ticket, so the reservation settles as `confirmed_existing` and no retry runs. Across five
trials there were zero duplicate writes. When the crash lands before the effect, the lookup
finds nothing, so the reservation settles as `unused` and the capacity returns. The retry
that follows is correct, because there was nothing to duplicate. Both crash points, one
policy, no damage.

## Two states, not one

The fix above looks like a policy flag, but it is a state machine change. The naive
policy has one terminal state for an expired reservation: `unused`. The reconcile policy
splits it into two.

```text
            expiry                lookup by idempotency key
 reserved ────────────▶ outcome_unknown ────────────▶ confirmed_existing
                          │        │
                 naive:   │        └──── not found ──▶ unused (capacity returns)
                 treat as unused
```

The `outcome_unknown` state is the whole game. In other words, the reservation system now
knows something about the worker (it stopped) and nothing about the operation. Capacity
only returns through one of the two exits, both of which require
evidence from the external system rather than evidence from the clock.

## The retry that arrives too early

A careful reader spots the hole in the reconcile policy. It is the same reader who
spotted it in the comments section. The lookup answers a question about a moment in time:
does the key exist right now? The old attempt may still be in flight. It may commit
after the lookup returns "not found." Absence at lookup time is not absence at commit time.

The deterministic probes in the comment thread simulated this with a logical clock. The
upgrade in this post is a real one. The old attempt runs in a real thread with a real 2.4
second workload. The lease expires at 1.0 second on the monotonic clock. The janitor
genuinely reconciles at that moment, while the old thread is still sleeping. Five runs of
the naive reconciler:

```text
MODE=naive
  trial 1: expiry@1.003s released@1.003s retry@1.407s old_commit@2.405s(ok=True)
  trial 5: expiry@1.011s released@1.011s retry@1.412s old_commit@2.405s(ok=True)
SUMMARY trials=5 duplicate_writes_total=5 early_capacity_release=5/5
```

The janitor released capacity at 1.003 seconds. The retry committed at 1.407 seconds. The
old attempt, still alive this whole time, committed at 2.405 seconds. Two writes, one
ticket. The state machine never noticed, because both of its decisions were locally
correct at the moments it made them. The reconcile policy from the previous section does
not survive contact with a slow attempt.

![Timeline of the delayed commit race: the janitor releases capacity at 1.003s, the retry commits at 1.407s, the old attempt commits at 2.405s and two writes land](/images/reservations-fencing/race-timeline.png)

## Fences and witnesses

Two independent repairs exist. They fix different halves of the damage.

The first repair is destination fencing, a put-if-absent on the idempotency key. The retry
commits first at 1.4 seconds, because in this workload the fast attempt wins. When the old
attempt arrives at 2.4 seconds, the destination rejects it:

```text
MODE=fenced
  trial 1: released@1.006s retry@1.409s old_commit@2.407s(ok=False) fenced_rejected=1
SUMMARY trials=5 duplicate_writes_total=0 early_capacity_release=5/5
```

Zero duplicate writes across five runs, so the ticket system is safe. But look at what the
fence did not prevent. Capacity was still released early in all five runs. The retry still
ran. The old attempt still burned its full 2.4 seconds of work only to be told no.
As a result, the fence protects the destination, but not the capacity or the wasted effort.

In contrast, the second repair is a destination that witnesses attempt state. If the
external system exposes that attempt K is `in_flight`, the janitor does not have to guess
from a key lookup:

```text
MODE=authoritative
  trial 1: expiry@1.008s old_commit@2.405s(ok=True) released@2.405s retried=False
SUMMARY trials=5 duplicate_writes_total=0 early_capacity_release=0/5 retry_started=0/5
```

Seeing `in_flight` at expiry kept the reservation in `outcome_unknown`, so no retry started
and no capacity moved. The second reconciliation found a terminal outcome at 2.405 seconds
and released capacity exactly then, after the evidence existed. Zero duplicates, zero early
releases, zero wasted retries.

The two repairs compose. The pair is worth stating precisely. Fencing removes the
duplicate write at the destination. An authoritative attempt state removes the pointless
retry and the premature release. A system with both is safe at both ends. A system with
only one is safe at exactly one end.

## What surprised me

- The SDK already ships an in-process idempotency mechanism. I expected to find only a
  concurrency guard, and instead found token-based dedup with waiter semantics
  ([_concurrency.py:24](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)).
  It solves the duplicate-request problem inside one process, which is precisely the
  problem it cannot solve across processes.
- The fence rejected the original attempt, not the retry. In every run of the fenced mode
  the fast retry committed first, so the "old" writer was the one turned away. Which
  attempt survives is decided by speed, not by seniority. The intuition that
  "the stale one gets blocked" had it backwards.
- Crash recovery cost is paid by the healthy workers. In the contention experiment, a
  crashed holder kept one of two slots for the full lease. The worker that inherited the
  slot waited 1.002 seconds, almost exactly the 1.0 second lease, before it could start.
  The queue behind a crash waits out the lease even though nothing is running. The lease
  length is therefore itself a trade-off: shorter leases recover capacity faster, but
  they also expire slow attempts that were about to finish.

## When not to use this

- Do not build a reservation system for a single-process workload. The SDK's own
  invocation lock plus an idempotency token already covers one process. The experiment
  in part two of the first section is the proof.
- Do not treat these thread-and-clock experiments as evidence about real distributed
  systems. A thread lock is not a network partition. A monotonic clock is not clock
  skew. The state machines here are the transferable part, not the guarantees.
- Do not add fencing to a destination whose writers cannot agree on a key. A
  put-if-absent is only as stable as the idempotency key behind it.
  [Article 04](https://xiongpin.dev/posts/sessions-state-memory/) showed how easily a key
  living in conversation state gets forgotten mid-run.

## Try it yourself

Everything runs from the repository root with no AWS credentials except the one LLM probe:

```bash
cd usecases/05-reservations-fencing
python src/lease_crash_boundary.py --policy naive --crash after-effect --trials 5
python src/delayed_commit_race.py --mode naive --stress 5
python src/delayed_commit_race.py --mode fenced --stress 5
python src/delayed_commit_race.py --mode authoritative --stress 5
python src/slot_contention.py
python src/concurrent_limits.py   # needs Bedrock access, ~10 seconds
```

For example, swap `naive` for `reconcile` in the first command and watch `duplicates`
drop to zero, then watch `delayed_commit_race.py --mode naive` put it right back. The
scripts print every timing value from the real clock, so you can reproduce the race
windows to the millisecond.

## Takeaways

- A lease proves that a worker stopped reporting, and nothing else. Every safe transition
  out of an expired reservation needs evidence from the destination, not from the clock.
- "Not found" is a snapshot, not a promise. Any reconciler that treats a missing
  idempotency key as "never happened" will double-write the first time an old attempt
  commits late. My five-run stress test hit it five times.
- `outcome_unknown` is a load-bearing state. Splitting "expired" into "confirmed existing"
  and "unused" is what turns capacity return from a guess into a decision.
- Fences and witnesses are complementary. Put-if-absent protects the destination from
  duplicates. An authoritative attempt state protects the capacity from premature
  release and the fleet from wasted retries. Choose the one your destination can honor,
  and know which end you left open.

The reservation layer closes the capability arc, and the series now moves to orchestration:
what happens when several agents must decide who goes next and what you give up when
nobody is in charge. That next piece starts with the loop from
[article 01](https://xiongpin.dev/posts/how-the-strands-agent-loop-works/) and puts more
than one agent inside it.
