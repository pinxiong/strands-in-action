"""Delayed completion: the old attempt commits AFTER reconciliation finds nothing.

Logical clock, no wall time, no model. One slot, one idempotency key K.

  t0  worker 1 reserves the slot and starts attempt A (slow, still running)
  t1  the lease expires
  t2  reconciliation looks up K -> not found (A has not committed)
  t3  attempt A commits
  t4  a retry, if one was started, commits

Modes:
  naive         'not found' == unused: capacity is returned at t2 and a retry starts
  fenced        same early release, but the destination enforces put-if-absent on K
  authoritative the destination also reports attempt state, so reconciliation sees
                A as in_flight and keeps the reservation in outcome_unknown

The point being tested: absence at lookup time is not absence at commit time.
"""
import argparse


class Destination:
    def __init__(self, fenced: bool) -> None:
        self.fenced = fenced
        self.effects: list[str] = []
        self.attempts: dict[str, str] = {}
        self.rejected = 0

    def start(self, key: str) -> None:
        self.attempts[key] = "in_flight"

    def commit(self, attempt_id: str, idem_key: str = "K") -> bool:
        # the fence is on the idempotency key, not on the attempt id
        if self.fenced and idem_key in self.effects:
            self.rejected += 1
            self.attempts[attempt_id] = "fenced"
            return False
        self.effects.append(idem_key)
        self.attempts[attempt_id] = "committed"
        return True

    def lookup_effect(self, key: str) -> bool:
        return key in self.effects

    def attempt_state(self, key: str) -> str:
        return self.attempts.get(key, "unknown")


def run(mode: str) -> None:
    dest = Destination(fenced=(mode == "fenced"))
    used = 0
    state = "reserved"
    retried = False
    released_at_t2 = False

    dest.start("K")          # t0: attempt A is running
    used = 1
    # t1: lease expires (no confirmation recorded)
    # t2: reconciliation looks for the effect
    found = dest.lookup_effect("K")
    print(f"MODE={mode}")
    print(f"  t2 lookup_effect(K) -> {'found' if found else 'not_found'}")

    if mode == "authoritative":
        attempt = dest.attempt_state("K")
        print(f"  t2 attempt_state(K) -> {attempt}")
        if attempt == "in_flight":
            state = "outcome_unknown"  # capacity stays held
        else:
            state = "confirmed_existing"
    else:
        if not found:
            state = "unused"
            used = 0
            released_at_t2 = True
            retried = True               # retry starts while A is still running
            dest.start("K-retry")
    print(f"  after t2: reservation_state={state} used_slots={used} retried={retried}")

    dest.commit("K")         # t3: the OLD attempt completes
    if retried:
        dest.commit("K-retry")  # t4: the retry completes

    if mode == "authoritative" and dest.lookup_effect("K"):
        # second reconciliation, now that there IS a terminal outcome
        state = "confirmed_existing"
        used = 0
        print("  t3+ reconciliation: terminal outcome found, capacity released now")

    print(f"  external_effects={len(dest.effects)} duplicate_writes={len(dest.effects) - len(set(dest.effects))}")
    print(f"  fenced_rejected_commits={dest.rejected}")
    print(f"  capacity_released_before_old_commit={released_at_t2}")
    print(f"  final_reservation_state={state}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["naive", "fenced", "authoritative"], required=True)
    run(ap.parse_args().mode)
