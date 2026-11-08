"""Reservation expiry vs. external effect: a deterministic crash-boundary test.

Scenario (Mayank's comment): a worker reserves quota, completes the external
effect, and dies before recording confirmation. What should expiry do?

  naive       expiry == unused: the slot is returned, a retry re-executes
  reconcile   expiry == outcome unknown: the external idempotency key is checked
              before any capacity is returned or any retry is executed

Variants:
  --crash-after-effect    the crash lands between the effect and the confirmation
  --crash-before-effect   the crash lands before the effect ever happened

Pure Python, no model, no wall-clock dependence: the lease is a logical flag.
"""
import argparse


class ExternalSystem:
    """Stands in for the ticket service. Dedupes only if the caller checks."""

    def __init__(self) -> None:
        self.effects: list[tuple[str, str]] = []

    def execute(self, key: str, payload: str) -> None:
        self.effects.append((key, payload))

    def find(self, key: str) -> list[tuple[str, str]]:
        return [e for e in self.effects if e[0] == key]


def run(policy: str, crash: str) -> None:
    ext = ExternalSystem()
    total_slots = 1
    used = 0
    reservation_state = "reserved"

    # Worker 1 reserves, then crashes at the chosen point.
    used += 1
    if crash == "after-effect":
        ext.execute("K1", "ticket-123")
    # worker dies here: no confirmation is recorded
    worker_reporting = False

    print(f"POLICY={policy} CRASH={crash}")
    print(f"  lease observes: worker_stopped_reporting={not worker_reporting}, "
          f"operation_outcome=UNKNOWN")

    # Expiry fires.
    if policy == "naive":
        reservation_state = "unused"
        used -= 1  # capacity is returned unconditionally
    else:
        reservation_state = "outcome_unknown"  # capacity is NOT returned yet
        found = ext.find("K1")
        if found:
            reservation_state = "confirmed_existing"
        else:
            reservation_state = "unused"
            used -= 1
    print(f"  after expiry: reservation_state={reservation_state} used_slots={used}")

    # The retry worker picks up the same job.
    retried = False
    if policy == "naive":
        retried = True  # slot is free, so the job runs again
        ext.execute("K1", "ticket-123")
    else:
        if reservation_state == "unused":
            retried = True
            used += 1
            ext.execute("K1", "ticket-123")
        # confirmed_existing: nothing to redo, the effect is already there

    keys = {k for k, _ in ext.effects}
    print(f"  retried={retried}")
    print(f"  external_effects={len(ext.effects)} duplicate_writes={len(ext.effects) - len(keys)}")
    print(f"  capacity_returned_while_effect_exists="
          f"{bool(ext.find('K1')) and used == 0 and reservation_state == 'unused'}")
    print(f"  final_reservation_state={reservation_state}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["naive", "reconcile"], required=True)
    ap.add_argument("--crash", choices=["after-effect", "before-effect"], required=True)
    args = ap.parse_args()
    run(args.policy, args.crash)
