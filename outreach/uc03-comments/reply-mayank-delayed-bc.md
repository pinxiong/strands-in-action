Built the delayed-completion case, and it breaks the reconciler from the last run without changing anything else. The old attempt commits after reconciliation has already looked and found nothing.

```
MODE=naive
  t2 lookup_effect(K) -> not_found
  after t2: reservation_state=unused used_slots=0 retried=True
  external_effects=2 duplicate_writes=1
  capacity_released_before_old_commit=True

MODE=fenced
  t2 lookup_effect(K) -> not_found
  after t2: reservation_state=unused used_slots=0 retried=True
  external_effects=1 duplicate_writes=0
  fenced_rejected_commits=1
  capacity_released_before_old_commit=True

MODE=authoritative
  t2 lookup_effect(K) -> not_found
  t2 attempt_state(K) -> in_flight
  after t2: reservation_state=outcome_unknown used_slots=1 retried=False
  t3+ reconciliation: terminal outcome found, capacity released now
  external_effects=1 duplicate_writes=0
  capacity_released_before_old_commit=False
  final_reservation_state=confirmed_existing
```

So your condition is the load-bearing one. In the naive row the reconciler did everything the previous design asked: it checked the external key before returning capacity. The check was simply answered too early, and "not found" at t2 said nothing about t3.

The fenced row is the part I found most useful, because it separates the two protections. The reservation still expires, capacity is still returned early, a retry still starts — and the duplicate is stopped at the destination by put-if-absent on the idempotency key, with one commit rejected. Nothing in the lease did that. It also shows the cost of relying on the fence alone: the retry still ran, so the work was wasted even though the effect was not duplicated.

The authoritative row avoids that waste. The destination reports the attempt as in_flight, so the reservation stays in outcome_unknown and no capacity moves; the second reconciliation, once a terminal outcome exists, closes it as confirmed_existing and only then releases.

The rule I would write down now: a lookup that returns "not found" establishes "no committed effect is visible to this read", nothing more. Releasing capacity requires one of the two things you named — an authoritative terminal outcome, or a fence enforced by the destination. An expired lease supplies neither, and a read that lags the write has the same shape as a worker that never stopped.

Script and evidence log: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc03-comments (`reservation_delayed_commit.py`, `evidence/reservation-delayed-commit.txt`). The three modes share the same base timeline; fenced adds destination-enforced put-if-absent, while authoritative adds attempt-state visibility to reconciliation.
