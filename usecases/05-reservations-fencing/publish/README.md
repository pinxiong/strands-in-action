# UC05 · When "Not Found" Doesn't Mean "Never Happened"

> Verified on 2026-11-09 against `strands-agents` 1.63.0, Python 3.11 and Bedrock in
> `us-east-1`. The model in the agent probe is `amazon.nova-pro-v1:0`.
> Every number in the article came out of a run; raw output lives in `evidence/`.

A quota shared by many workers cannot rely on per-invocation limits, and a lease expiry
cannot tell you whether the side effect happened. This case builds the smallest system that
double-writes, then repairs it twice: at the destination (put-if-absent) and at the
reservation (authoritative attempt state).

## What the experiments show

| Script | Question | Finding |
|---|---|---|
| `src/concurrent_limits.py` | What does the SDK give two concurrent workers? | One `Agent` instance serializes invocations (`ConcurrencyException`); the same `idempotency_token` gets the inflight result (948 tokens each, one invocation); two instances each run to `limit_turns` with their own 453-token budget |
| `src/lease_crash_boundary.py` | Is returning capacity on lease expiry safe? | Crash after the effect: `duplicates=1` and capacity returned while the effect exists, 5/5 runs. Reconcile policy: zero duplicates, `confirmed_existing` |
| `src/delayed_commit_race.py` | What if the old attempt commits after reconciliation? | naive: 5/5 duplicate writes, capacity released at 1.003s, old commit at 2.405s. fenced: 0 duplicates but the old attempt is rejected after burning 2.4s. authoritative: 0 duplicates, 0 early releases, no retry |
| `src/slot_contention.py` | What does a crashed holder cost the queue? | 12 workers, 2 slots, 1.0s lease: the crashed slot returns only through expiry, the inheriting worker waits 1.002s |

## Reproduce

From the repository root, use the shared environment (`uv venv --python 3.11`, then
`VIRTUAL_ENV=.venv uv pip install strands-agents==1.63.0`).

```bash
cd usecases/05-reservations-fencing
python src/lease_crash_boundary.py --policy naive --crash after-effect --trials 5
python src/lease_crash_boundary.py --policy reconcile --crash after-effect --trials 5
python src/delayed_commit_race.py --mode naive --stress 5
python src/delayed_commit_race.py --mode fenced --stress 5
python src/delayed_commit_race.py --mode authoritative --stress 5
python src/slot_contention.py
python src/concurrent_limits.py   # needs Bedrock access
```

The scripts are pure Python except `concurrent_limits.py`, print real monotonic-clock
timings, and take about 60 seconds in total. Leases are 1.0s, the slow attempt is 2.4s, and
the retry latency is 0.4s; change the constants at the top of each script and the race
windows change with them.

## Scope

Threads on one machine with real clocks, and an external system simulated by a lock-guarded
object. This is a state-machine study, not a distributed-systems proof. The article says so
in its opening and closing sections.
