"""C1: crash boundary with a real lease clock and real threads.

Upgrades the deterministic probe outreach/uc03-comments/reservation_crash.py:
- the lease is a real monotonic-clock deadline, observed by a janitor thread
- the worker runs in a real thread and genuinely stops reporting (crash)
- timing values below are measured, not asserted

Scenario: a worker reserves the only slot, optionally performs the external
effect, then dies before recording confirmation. The janitor thread waits for
the lease to expire on the real clock and applies one of two policies.

  naive      expiry == unused: capacity returns, a retry worker re-executes
  reconcile  expiry == outcome unknown: look the idempotency key up at the
             destination first; only 'no effect' may return capacity

Crash points:
  after-effect    the crash lands between the effect and the confirmation
  before-effect   the crash lands before the effect ever happened

Pure Python, no model. The destination's mutual exclusion is a thread lock;
that is a simulation of a real external system, and the article says so.
"""
import argparse
import threading
import time

LEASE_SECONDS = 1.0
EFFECT_LATENCY = 0.2
RETRY_LATENCY = 0.2
JANITOR_POLL = 0.01


class Destination:
    """Stands in for the ticket service. Dedupes only if the caller checks."""

    def __init__(self) -> None:
        self.effects: list[str] = []
        self.lock = threading.Lock()

    def execute(self, key: str) -> None:
        with self.lock:
            self.effects.append(key)

    def has_effect(self, key: str) -> bool:
        with self.lock:
            return key in self.effects


class LeasedSlot:
    """One capacity slot, reserved with a real monotonic-clock deadline."""

    def __init__(self) -> None:
        self.deadline: float | None = None
        self.lock = threading.Lock()

    def reserve(self, lease_seconds: float) -> None:
        with self.lock:
            self.deadline = time.monotonic() + lease_seconds

    def expired(self) -> bool:
        with self.lock:
            return self.deadline is not None and time.monotonic() >= self.deadline

    def release(self) -> None:
        with self.lock:
            self.deadline = None


def run_once(policy: str, crash_point: str, trial: int) -> dict:
    dest = Destination()
    slot = LeasedSlot()
    key = "K1"

    t0 = time.monotonic()
    slot.reserve(LEASE_SECONDS)

    effect_done_at: list[float] = []

    def worker(crash_point: str) -> None:
        # the worker thread really runs, really sleeps, really stops
        if crash_point == "after-effect":
            time.sleep(EFFECT_LATENCY)
            dest.execute(key)
            effect_done_at.append(time.monotonic())
        # crash: the thread ends here, no confirmation is ever recorded

    w = threading.Thread(target=worker, args=(crash_point,))
    w.start()

    # janitor: wait for expiry on the real clock
    while not slot.expired():
        time.sleep(JANITOR_POLL)
    expiry_observed_at = time.monotonic() - t0

    state = "outcome_unknown"
    retried = False
    retry_done_at: float | None = None

    if policy == "naive":
        state = "unused"
        slot.release()
        retried = True

        def retry_worker() -> None:
            time.sleep(RETRY_LATENCY)
            dest.execute(key)

        r = threading.Thread(target=retry_worker)
        r.start()
        r.join()
        retry_done_at = time.monotonic() - t0
    else:
        if dest.has_effect(key):
            state = "confirmed_existing"
        else:
            state = "unused"
            slot.release()
            retried = True

            def retry_worker() -> None:
                time.sleep(RETRY_LATENCY)
                dest.execute(key)

            r = threading.Thread(target=retry_worker)
            r.start()
            r.join()
            retry_done_at = time.monotonic() - t0

    w.join()

    effects = len(dest.effects)
    duplicates = effects - len(set(dest.effects))
    capacity_returned_while_effect_exists = (
        policy == "naive" and crash_point == "after-effect"
        and dest.has_effect(key) and state == "unused"
    )
    return {
        "trial": trial,
        "policy": policy,
        "crash_point": crash_point,
        "expiry_observed_at_s": round(expiry_observed_at, 3),
        "effect_done_at_s": round(effect_done_at[0] - t0, 3) if effect_done_at else None,
        "retry_done_at_s": round(retry_done_at, 3) if retry_done_at else None,
        "external_effects": effects,
        "duplicate_writes": duplicates,
        "retried": retried,
        "final_state": state,
        "capacity_returned_while_effect_exists": capacity_returned_while_effect_exists,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["naive", "reconcile"], required=True)
    ap.add_argument("--crash", choices=["after-effect", "before-effect"], required=True)
    ap.add_argument("--trials", type=int, default=5)
    args = ap.parse_args()

    print(f"POLICY={args.policy} CRASH={args.crash} "
          f"LEASE_S={LEASE_SECONDS} TRIALS={args.trials}")
    print(f"python real-clock crash boundary; lease={LEASE_SECONDS}s, "
          f"effect_latency={EFFECT_LATENCY}s, retry_latency={RETRY_LATENCY}s")
    results = [run_once(args.policy, args.crash, i + 1) for i in range(args.trials)]
    for r in results:
        print(f"  trial {r['trial']}: expiry@{r['expiry_observed_at_s']}s "
              f"effect@{r['effect_done_at_s']}s retry@{r['retry_done_at_s']}s "
              f"effects={r['external_effects']} duplicates={r['duplicate_writes']} "
              f"retried={r['retried']} state={r['final_state']} "
              f"capacity_returned_while_effect_exists={r['capacity_returned_while_effect_exists']}")

    dup_total = sum(r["duplicate_writes"] for r in results)
    cap_total = sum(1 for r in results if r["capacity_returned_while_effect_exists"])
    print(f"SUMMARY trials={len(results)} duplicate_writes_total={dup_total} "
          f"capacity_returned_while_effect_exists={cap_total}/{len(results)} "
          f"mean_expiry_observed={round(sum(r['expiry_observed_at_s'] for r in results) / len(results), 3)}s")


if __name__ == "__main__":
    main()
