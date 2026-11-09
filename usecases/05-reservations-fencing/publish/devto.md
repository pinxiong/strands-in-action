---
title: "When \"Not Found\" Doesn't Mean \"Never Happened\""
published: true
description: "A lease expiry proves only that a worker stopped reporting. In five real-clock runs, a naive reconciler wrote the same ticket twice, and a late commit survived the lookup."
tags: ai, agents, strands, aws
canonical_url: "https://xiongpin.dev/posts/reservations-fencing/"
cover_image: "https://xiongpin.dev/images/reservations-fencing/cover-devto.png"
---

> Verified on 2026-11-09 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in `us-east-1`. Every number below came out of a run, and the scripts live in `usecases/05-reservations-fencing/src/` with raw output in `evidence/`. The model in the agent experiments is `amazon.nova-pro-v1:0`.

A reader of [article 03](https://xiongpin.dev/posts/execution-limits/) left three questions under the piece, and each one tightened on the last. A limit counts what happens inside one call, so what stops two concurrent attempts from each spending a full remaining quota? When a request was submitted but the response was lost, how do you know that "not found" means "never happened"? And when the crash lands before or after the side effect, is returning the capacity safe in both cases?

Those questions share one blind spot. Limits, leases and lookups all answer questions about a moment in time, which is why the answers stop being true the moment after they are given. This post builds the smallest system that fails, fails it on purpose and then makes it safe twice, once at the reservation and once at the destination.

One scope note before anything else. The experiments here are threads on one machine with real clock leases, and the "external system" is an object guarded by a thread lock. This is a simulation of a distributed system, not a distributed system, and I will not claim otherwise. What the simulation gives you is exact, repeatable timing evidence for the state machines involved, which is the part most explanations wave their hands at.

## What the SDK already gives you

Two threads invoked the same `Agent` instance with different prompts. One call won. The other raised:

```text
ConcurrencyException: Agent is already processing a request.
Concurrent invocations are not supported.
```

That is the documented default. The constructor argument `concurrent_invocation_mode` defaults to `THROW`. `UNSAFE_REENTRANT` is the explicit opt-out for code that accepts the risk ([agent.py:268](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/agent.py), [types/agent.py:205](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/types/agent.py)).

The second probe was more interesting. The call signature accepts an `idempotency_token`, a caller-chosen name for one logical request, so a retry carries the same name as the original instead of looking like a second request ([agent.py:928](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/agent.py)). When a second thread called the same instance with the same prompt and the same token, the duplicate did not crash and did not run the model twice. It waited for the inflight invocation and received its cached result. Both threads reported identical usage, 948 total tokens each, because only one invocation ever ran ([_concurrency.py:183](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)).

So the SDK already distinguishes "concurrent invocations" from "the same request twice." It handles the second one correctly. The third probe found the boundary. Two separate instances, one thread each, each invocation carrying `limits={"turns": 1}`, both ran to `stop_reason="limit_turns"` with identical usage of 453 total tokens each. No budget was shared between them. None could be, because limits travel with the request, not with the fleet: the signature documents them as "Limits for the whole request this call starts" ([agent.py:955](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/agent.py)). The two usage figures differ for an unrelated reason. The token-dedup probe ran to `end_turn` over two turns. The limits probe stopped after one turn.

In short, the SDK serializes an instance, dedupes a repeated token in-process and budgets each call separately. That guard, the token registry and the lock all live in one per-instance controller, which is why a second process cannot reuse them without inventing a protocol of its own ([_concurrency.py:86](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)). A quota that several workers must share is still yours to build, which is where leases come in and where the trouble starts.

## What a lease can and cannot tell you

The minimal system has one capacity slot, a unit of the shared quota that article 03 bounded per call, one worker that reserves it and one external system, a ticket service, that records side effects. The worker reserves the slot, performs the effect and confirms. The reservation carries a lease, a deadline after which the slot may be taken back, and a janitor loop watches that deadline on the real clock. A lease is therefore a one-sided promise, because it protects the fleet from a silent worker and it can also take a slot away from a worker that is still healthy.

The naive policy treats expiry as proof of innocence: the slot is free, so the operation never happened, so a retry worker re-executes the job. I crashed the worker after the effect had landed but before the confirmation and ran the race five times.

```text
POLICY=naive CRASH=after-effect
  trial 1: expiry@1.0s effect@0.205s retry@1.204s effects=2 duplicates=1
  trial 2: expiry@1.002s effect@0.202s retry@1.206s effects=2 duplicates=1
  trial 5: expiry@1.009s effect@0.201s retry@1.214s effects=2 duplicates=1
SUMMARY trials=5 duplicate_writes_total=5 capacity_returned_while_effect_exists=5/5
```

Every run wrote the ticket twice. Every run handed the capacity back while a completed effect was sitting in the external system. Scale to many workers and that freed slot goes to an unrelated job, so the fleet quietly spends two units of quota on one. The lease told the truth, just not the truth the policy needed. "The worker stopped reporting" is a fact about the worker. "The operation did not happen" is a fact about the external system, which a lease cannot see.

The reconcile policy separates the two facts. On expiry it holds the reservation in an `outcome_unknown` state and asks the external system whether the idempotency key exists before touching capacity. When the crash lands after the effect, the lookup finds the ticket, so the reservation settles as `confirmed_existing` and no retry runs. When the crash lands before the effect, the lookup finds nothing, so the reservation settles as `unused` and the capacity returns. The retry that follows is correct, because there was nothing to duplicate. Both crash points, one policy, no damage; all ten runs sit in `evidence/lease-crash-boundary.txt`.

Neither policy fixes the cost that a crash charges to everyone else, and the contention experiment, this time with two slots instead of one, makes that cost visible. Twelve worker threads contended for two leased slots with a one second lease. Worker 0 crashed while holding one of them. That slot came back only through expiry, and the worker that inherited it waited 1.002 seconds, almost exactly the lease length, before it could start. The queue behind a crash pays for the crash even though nothing is running on the held slot.

## Two states, not one

The fix above looks like a policy flag, but it is a state machine change. The naive policy has no intermediate state: expiry sends `reserved` straight to `unused`. The reconcile policy inserts `outcome_unknown` between them and requires evidence to leave it.

```text
naive:      reserved ──expiry──▶ unused

reconcile:  reserved ──expiry──▶ outcome_unknown ──key found──▶ confirmed_existing
                                        ├──key absent─────────▶ unused
                                        └──attempt in flight──▶ outcome_unknown (hold)
```

The `outcome_unknown` state is the whole game. In other words, the reservation system now knows something about the worker (it stopped) and nothing about the operation. Capacity only returns through one of the two exits, both of which require evidence from the external system rather than evidence from the clock.

## The retry that arrives too early

A careful reader spots the hole in the reconcile policy. It is the same reader who spotted it in the comments section. The lookup answers a question about a moment in time: does the key exist right now? The old attempt is still in flight when the lookup runs, and its commit can land after the answer. Absence at lookup time is not absence at commit time.

The deterministic probes in the comment thread simulated this with a logical clock. The upgrade in this post is a real one. The old attempt runs in a real thread with a real 2.4 second workload. The lease expires at 1.0 second on the monotonic clock. The janitor loop genuinely reconciles at that moment, while the old thread is still sleeping (the first harness prints `POLICY=naive`, the second prints `MODE=naive`, and both are the same policy in two shapes). Five runs of the naive reconciler:

```text
MODE=naive
  trial 1: expiry@1.003s released@1.003s old_commit@2.405s(ok=True) retry@1.407s effects=2 duplicates=1
  trial 2: expiry@1.001s released@1.001s old_commit@2.404s(ok=True) retry@1.405s effects=2 duplicates=1
SUMMARY trials=5 duplicate_writes_total=5 early_capacity_release=5/5
```

The janitor loop released capacity at 1.003 seconds. The retry committed at 1.407 seconds. The old attempt, still alive this whole time, committed at 2.405 seconds. Two writes, one ticket. The state machine never noticed, because both of its decisions were locally correct at the moments it made them. The reconcile policy from the previous section does not survive contact with a slow attempt.

The retry here is a stand-in for any other worker that picks up the same job after the release, and a released job has nothing that stops a second pickup. If your workers share one permanent identity instead of per-attempt ids, the same ambiguity returns through a different door: a crashed attempt and a slow attempt are indistinguishable under one id. Cancelling the id on death is a separate mechanism, and this experiment does not cover it.

![Timeline of the delayed commit race: the janitor releases capacity at 1.003s, the retry commits at 1.407s, the old attempt commits at 2.405s and two writes land](https://xiongpin.dev/images/reservations-fencing/race-timeline.png)

## Fences and witnesses

Two disjoint repairs exist. They fix different halves of the damage.

The first repair is a uniqueness check at the destination, a put-if-absent on the idempotency key. I will call it a fence, with one honest caveat: it is not a fencing token, because it does not order attempts. It refuses whichever write arrives second, and it cannot stop an old write that arrives first.

```text
MODE=fenced
  trial 1: expiry@1.006s released@1.006s old_commit@2.407s(ok=False) retry@1.409s effects=1 duplicates=0
SUMMARY trials=5 duplicate_writes_total=0 early_capacity_release=5/5
```

In these runs the fast retry committed first at 1.409 seconds, so the old attempt was the one turned away at 2.407 seconds after burning its full workload. Had the old attempt arrived first, the retry would have been the refused one instead. Either order ends with one write. The fence does not care which attempt loses. Zero duplicate writes across five runs, so the ticket system is safe. But look at what the fence did not prevent. Capacity was still released early in all five runs. The retry still ran. The losing attempt spent its whole workload only to be told no. As a result, the fence protects the destination, but not the capacity or the wasted effort.

In contrast, the second repair is a destination that witnesses attempt state. If the external system exposes that attempt K is `in_flight`, the janitor loop does not have to guess from a key lookup:

```text
MODE=authoritative
  trial 1: expiry@1.008s old_commit@2.405s(ok=True) released@2.405s retried=False effects=1 duplicates=0
SUMMARY trials=5 duplicate_writes_total=0 early_capacity_release=0/5 retry_started=0/5
```

That state only exists if the worker registers its intent before doing the work. The script does exactly that, because the attempt is marked in flight before the sleep starts. Without an intent write, the destination can only answer existence, and the fence is the only repair it supports. A destination that can answer existence and nothing else forces a choice between an early release behind a fence and a lease long enough to cover the slowest attempt you expect. Seeing `in_flight` at expiry kept the reservation in `outcome_unknown`. No retry started. No capacity moved. The second reconciliation found a terminal outcome at 2.405 seconds and released capacity exactly then, after the evidence existed. Zero duplicates, zero early releases, zero wasted retries.

The two repairs were run separately, never together, so I will not claim a measured result for the combination. What the separate runs do show is a clean division of labor: fencing removes the duplicate write at the destination, and an authoritative attempt state removes the early release and the wasted retry. The costs are not symmetric either. The fence costs nothing per attempt but leaves the wasted work in place, while the attempt state requires an extra write before every effect and a destination that stores it.

## What surprised me

- The SDK already ships an in-process idempotency mechanism. I expected to find only a concurrency guard, and instead found token-based dedup with waiter semantics ([_concurrency.py:25](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/agent/_concurrency.py)). It solves the duplicate-request problem inside one process, which is precisely the problem it cannot solve across processes.
- The fence rejected the original attempt, not the retry. In every run of the fenced mode the fast retry committed first, so the "old" writer was the one turned away. Which attempt survives is decided by speed, not by seniority. The intuition that "the stale one gets blocked" had it backwards.
- Crash recovery cost is paid by the healthy workers. The contention experiment showed the inheriting worker waiting out the full lease. The lease length is therefore itself a trade-off: shorter leases recover capacity faster, but they also expire slow attempts that were about to finish.

## When not to use this

- Do not build a reservation system for a single-process workload. The SDK's own invocation lock plus an idempotency token already covers one process. The second probe above is the proof.
- Do not treat these thread-and-clock experiments as evidence about real distributed systems. A thread lock is not a network partition. A monotonic clock is not clock skew. The state machines here are the transferable part, not the guarantees.
- Do not add fencing to a destination whose writers cannot agree on a key. A put-if-absent is only as stable as the idempotency key behind it. [Article 04](https://xiongpin.dev/posts/sessions-state-memory/) showed how easily a key living in conversation state gets forgotten mid-run.

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

For example, swap `naive` for `reconcile` in the first command and watch `duplicates` drop to zero, then watch `delayed_commit_race.py --mode naive` put it right back. The scripts print every timing value from the real clock, so you can reproduce the race windows to the millisecond.

## Takeaways

- A lease proves that a worker stopped reporting, and nothing else. In these state machines, every safe transition out of an expired reservation needs evidence from the destination, not from the clock.
- "Not found" is a snapshot, not a promise. Any reconciler that treats a missing idempotency key as "never happened" will double-write the first time an old attempt commits late. My five-run stress test hit it five times.
- `outcome_unknown` is a load-bearing state. Splitting "expired" into "confirmed existing" and "unused" is what turns capacity return from a guess into a decision.
- The recipe composes conditionally. Keep the reservation unresolved until the destination reports a terminal state. If the destination can only answer existence, a put-if-absent fence plus the idempotency key still stops the duplicate write, and the damage shrinks to an early release and a wasted retry. I verified each half separately, not the combination.

The reservation layer closes the capability arc, and the series now moves to orchestration: what happens when several agents must decide who goes next and what you give up when nobody is in charge. That next piece starts with the loop from [article 01](https://xiongpin.dev/posts/how-the-strands-agent-loop-works/) and puts more than one agent inside it.
