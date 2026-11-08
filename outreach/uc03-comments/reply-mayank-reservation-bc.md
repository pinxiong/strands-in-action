That is the right next failure-injection case, so I built it rather than leaving it as a diagram. Three runs, pure Python, no model: a single-slot quota, an external system that records effects, and a worker that crashes at a chosen point.

```
naive / crash after effect
  lease observes: worker_stopped_reporting=True, operation_outcome=UNKNOWN
  after expiry: reservation_state=unused used_slots=0
  retried=True
  external_effects=2 duplicate_writes=1
  capacity_returned_while_effect_exists=True

reconcile / crash after effect
  after expiry: reservation_state=confirmed_existing used_slots=1
  retried=False
  external_effects=1 duplicate_writes=0
  capacity_returned_while_effect_exists=False

reconcile / crash before effect
  after expiry: reservation_state=unused used_slots=0
  retried=True
  external_effects=1 duplicate_writes=0
  capacity_returned_while_effect_exists=False
```

The first row is exactly your scenario: expiry reads the crash as "unused", capacity comes back, the retry writes the same effect twice, and the store now believes it has free capacity while the effect already exists. The lease knew the worker stopped reporting and nothing else.

The second row is your proposal working: expiry moves the reservation to `outcome_unknown` instead of `unused`, and capacity is only returned after the external idempotency key has been checked. The key is found, so the reservation becomes `confirmed_existing`, nothing is retried, and there is one effect.

The third row is the case I would add to keep the design honest: if the crash happened before the effect, the same reconciliation finds no key, the reservation becomes `unused`, capacity comes back, and the retry executes exactly once. Without this branch, an outcome-unknown state is just a slow leak of quota instead of a duplicate write.

So the rule I would write down is: `outcome_unknown` is a real state with its own lifetime, not a label on the way to `unused`. Expiry may move a reservation into it; only reconciliation with the external system may move it out, to `confirmed_existing` or to `unused`. And the transition to `unused` is the only one allowed to return capacity.

Script and evidence log: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc03-comments (`reservation_crash.py`, `evidence/reservation-crash.txt`). The two policies share everything except what expiry does, and the crash point is a flag, so both halves of the boundary are reproducible.
