"""C2: delayed commit race, real clock, real overlapping threads.

The core upgrade over the deterministic probes: the OLD attempt is still
running in a real thread when the janitor observes lease expiry. What the
janitor believes at expiry time and what the destination looks like at
commit time are separated by real, measured seconds.

  t0   worker 1 reserves the only slot, starts attempt A (slow: still running)
  t1   the lease expires on the real clock; the janitor reconciles
  t2   reconciliation outcome decides whether capacity returns and a retry starts
  t3   attempt A finally commits at the destination
  t4   the retry, if one started, commits

Modes:
  naive         'not found' at t2 == unused: capacity returns, retry starts
  fenced        same early release, but the destination enforces put-if-absent
                on the idempotency key
  authoritative the destination also reports attempt state; seeing in_flight
                at t2 keeps the reservation in outcome_unknown (capacity held)

--stress N repeats the whole race N times to show it is reproducible.
"""
import argparse
import threading
import time

LEASE_SECONDS = 1.0
ATTEMPT_LATENCY = 2.4   # the old attempt outlives the lease
RETRY_LATENCY = 0.4
JANITOR_POLL = 0.01


class Destination:
    def __init__(self, fenced: bool, track_attempts: bool) -> None:
        self.fenced = fenced
        self.track_attempts = track_attempts
        self.effects: list[str] = []
        self.attempts: dict[str, str] = {}
        self.rejected = 0
        self.lock = threading.Lock()

    def start(self, attempt_id: str) -> None:
        with self.lock:
            self.attempts[attempt_id] = "in_flight"

    def commit(self, attempt_id: str, key: str) -> bool:
        with self.lock:
            if self.fenced and key in self.effects:
                self.rejected += 1
                self.attempts[attempt_id] = "fenced"
                return False
            self.effects.append(key)
            self.attempts[attempt_id] = "committed"
            return True

    def has_effect(self, key: str) -> bool:
        with self.lock:
            return key in self.effects

    def attempt_state(self, attempt_id: str) -> str:
        with self.lock:
            return self.attempts.get(attempt_id, "unknown")


def run_once(mode: str, trial: int) -> dict:
    fenced = mode == "fenced"
    authoritative = mode == "authoritative"
    dest = Destination(fenced=fenced, track_attempts=authoritative)
    key = "K"

    t0 = time.monotonic()
    # t0: worker 1 reserves the only slot and starts the slow attempt A
    lease_deadline = t0 + LEASE_SECONDS
    dest.start("A")

    old_commit_at: list[float] = []
    old_commit_ok: list[bool] = []

    def old_attempt() -> None:
        time.sleep(ATTEMPT_LATENCY)
        ok = dest.commit("A", key)
        old_commit_ok.append(ok)
        old_commit_at.append(time.monotonic())

    w = threading.Thread(target=old_attempt)
    w.start()

    # janitor: wait for expiry on the real clock
    while time.monotonic() < lease_deadline:
        time.sleep(JANITOR_POLL)
    expiry_observed_at = time.monotonic() - t0

    state = "outcome_unknown"
    retried = False
    released_at = None
    capacity_released_before_old_commit = False
    retry_commit_at: float | None = None

    found = dest.has_effect(key)
    attempt = dest.attempt_state("A") if authoritative else None

    if authoritative:
        if found:
            state = "confirmed_existing"
        elif attempt == "in_flight":
            state = "outcome_unknown"  # capacity stays held
        else:
            state = "unused"
    else:
        if not found:
            state = "unused"

    if state == "unused":
        # naive and fenced both release here; only authoritative holds
        released_at = time.monotonic() - t0
        retried = True
        dest.start("R")

        def retry_attempt() -> None:
            time.sleep(RETRY_LATENCY)
            dest.commit("R", key)

        r = threading.Thread(target=retry_attempt)
        r.start()
        r.join()
        retry_commit_at = time.monotonic() - t0

    w.join()
    old_done = old_commit_at[0] - t0
    # capacity was handed back while the old attempt was still in flight
    if released_at is not None and released_at < old_done:
        capacity_released_before_old_commit = True

    # authoritative mode: reconcile again now that there is a terminal outcome
    if authoritative and dest.has_effect(key):
        state = "confirmed_existing"
        released_at = time.monotonic() - t0

    effects = len(dest.effects)
    duplicates = effects - len(set(dest.effects))
    return {
        "trial": trial,
        "mode": mode,
        "expiry_observed_at_s": round(expiry_observed_at, 3),
        "released_at_s": round(released_at, 3) if released_at is not None else None,
        "old_commit_at_s": round(old_done, 3),
        "old_commit_accepted": old_commit_ok[0],
        "retry_commit_at_s": round(retry_commit_at, 3) if retry_commit_at else None,
        "external_effects": effects,
        "duplicate_writes": duplicates,
        "fenced_rejected_commits": dest.rejected,
        "retried": retried,
        "capacity_released_before_old_commit": capacity_released_before_old_commit,
        "final_state": state,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["naive", "fenced", "authoritative"], required=True)
    ap.add_argument("--stress", type=int, default=5)
    args = ap.parse_args()

    print(f"MODE={args.mode} LEASE_S={LEASE_SECONDS} ATTEMPT_LATENCY={ATTEMPT_LATENCY} "
          f"RETRY_LATENCY={RETRY_LATENCY} STRESS={args.stress}")
    results = [run_once(args.mode, i + 1) for i in range(args.stress)]
    for r in results:
        print(f"  trial {r['trial']}: expiry@{r['expiry_observed_at_s']}s "
              f"released@{r['released_at_s']}s old_commit@{r['old_commit_at_s']}s"
              f"(ok={r['old_commit_accepted']}) "
              f"retry@{r['retry_commit_at_s']}s effects={r['external_effects']} "
              f"duplicates={r['duplicate_writes']} fenced_rejected={r['fenced_rejected_commits']} "
              f"retried={r['retried']} released_before_old_commit={r['capacity_released_before_old_commit']} "
              f"state={r['final_state']}")

    dup_total = sum(r["duplicate_writes"] for r in results)
    early_release = sum(1 for r in results if r["capacity_released_before_old_commit"])
    print(f"SUMMARY mode={args.mode} trials={len(results)} duplicate_writes_total={dup_total} "
          f"early_capacity_release={early_release}/{len(results)} "
          f"retry_started={sum(1 for r in results if r['retried'])}/{len(results)} "
          f"mean_old_commit={round(sum(r['old_commit_at_s'] for r in results) / len(results), 3)}s "
          f"mean_expiry={round(sum(r['expiry_observed_at_s'] for r in results) / len(results), 3)}s")


if __name__ == "__main__":
    main()
