"""UC05 comment probe: run the fence and the witness together.

Question (Benjamin Kincses, AWS Builder Center, 2026-11-10):
  "The fence and the witness were run separately. What breaks if you run both
   at once? If the fence rejects the late commit and the witness still holds the
   slot in outcome_unknown, does the retry wait for a terminal state that never
   arrives, or does the fence rejection count as terminal?"

The harness keeps the real-clock parameters of the original article script
(usecases/05-reservations-fencing/src/delayed_commit_race.py) so the numbers are
directly comparable to evidence/delayed-commit-race.txt. One variable changes
per case. No LLM is involved.

Cases:
  fenced_only       fence ON, witness OFF, naive reconciler (article MODE=fenced)
  witness_only      fence OFF, witness ON, effect_first (article MODE=authoritative)
  combined          fence ON, witness ON, no competing writer
  conflict/effect_first        combined + writer B bypasses the reservation
                               and writes key K before A commits; janitor uses
                               the article's order (effect lookup first)
  conflict/attempt_terminal    same, but {committed, fenced} are terminal states
  conflict/committed_whitelist same, but only "committed" is a terminal state
"""

import argparse
import threading
import time

LEASE_SECONDS = 1.0
ATTEMPT_LATENCY = 2.4
RETRY_LATENCY = 0.4
BYPASS_LATENCY = 0.5
JANITOR_POLL = 0.01
JANITOR_TIMEOUT = 3.2
TERMINAL_ATTEMPTS = {"committed", "fenced"}

CASES = {
    "fenced_only": dict(fenced=True, policy="naive", bypass=False, witness=False),
    "witness_only": dict(fenced=False, policy="effect_first", bypass=False, witness=True),
    "combined": dict(fenced=True, policy="effect_first", bypass=False, witness=True),
    "conflict/effect_first": dict(fenced=True, policy="effect_first", bypass=True, witness=True),
    "conflict/attempt_terminal": dict(fenced=True, policy="attempt_terminal", bypass=True, witness=True),
    "conflict/committed_whitelist": dict(fenced=True, policy="committed_whitelist", bypass=True, witness=True),
}


class Destination:
    """Copied from src/delayed_commit_race.py:33-62, same semantics."""

    def __init__(self, fenced: bool) -> None:
        self.fenced = fenced
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


def reconcile_once(dest: Destination, key: str, policy: str) -> str:
    """One janitor poll. Returns the settled state, or outcome_unknown to hold."""
    found = dest.has_effect(key)
    attempt = dest.attempt_state("A") if policy != "naive" else None

    if policy == "naive":
        return "confirmed_existing" if found else "unused"
    if policy == "effect_first":
        # src/delayed_commit_race.py:99-115, effect lookup has priority
        if found:
            return "confirmed_existing"
        if attempt == "in_flight":
            return "outcome_unknown"
        return "unused"
    if policy == "attempt_terminal":
        # "fenced" is explicitly accepted as a terminal attempt state
        if attempt in TERMINAL_ATTEMPTS:
            return "confirmed_existing" if found else "unused"
        return "outcome_unknown"
    if policy == "committed_whitelist":
        # a strict terminal set: only a successful commit counts
        if attempt == "committed":
            return "confirmed_existing" if found else "unused"
        return "outcome_unknown"
    raise ValueError(policy)


def run_once(case: str, trial: int) -> dict:
    cfg = CASES[case]
    dest = Destination(fenced=cfg["fenced"])
    key = "K"
    capacity_event = threading.Event()
    t0 = time.monotonic()

    dest.start("A")
    old: dict[str, float | bool | None] = {"at": None, "ok": None}

    def old_attempt() -> None:
        time.sleep(ATTEMPT_LATENCY)
        old["ok"] = dest.commit("A", key)
        old["at"] = time.monotonic() - t0

    wa = threading.Thread(target=old_attempt)
    wa.start()

    bypass_at: list[float] = []
    wb = None
    if cfg["bypass"]:
        def bypass_writer() -> None:
            time.sleep(BYPASS_LATENCY)
            dest.start("B")
            dest.commit("B", key)
            bypass_at.append(time.monotonic() - t0)

        wb = threading.Thread(target=bypass_writer)
        wb.start()

    # a queued job that can only start once capacity is handed back
    queued_at: list[float] = []
    wq = None

    def queued_job() -> None:
        if capacity_event.wait(JANITOR_TIMEOUT + 0.5):
            queued_at.append(time.monotonic() - t0)

    wq = threading.Thread(target=queued_job)
    wq.start()

    lease_deadline = t0 + LEASE_SECONDS
    while time.monotonic() < lease_deadline:
        time.sleep(JANITOR_POLL)
    expiry = time.monotonic() - t0

    # janitor loop: keep reconciling until a terminal state or the timeout
    state = "outcome_unknown"
    released_at = None
    polls = 0
    timed_out = False
    while True:
        polls += 1
        state = reconcile_once(dest, key, cfg["policy"])
        if state in ("confirmed_existing", "unused"):
            released_at = time.monotonic() - t0
            capacity_event.set()
            break
        if time.monotonic() - t0 >= JANITOR_TIMEOUT:
            state = "outcome_unknown"
            timed_out = True
            break
        time.sleep(JANITOR_POLL)

    retried = False
    retry_commit_at = None
    if state == "unused":
        retried = True
        dest.start("R")

        def retry_attempt() -> None:
            time.sleep(RETRY_LATENCY)
            dest.commit("R", key)

        wr = threading.Thread(target=retry_attempt)
        wr.start()
        wr.join()
        retry_commit_at = time.monotonic() - t0

    wa.join()
    if wb:
        wb.join()
    wq.join()

    old_done = old["at"]
    effects = len(dest.effects)
    return {
        "trial": trial,
        "case": case,
        "expiry_s": round(expiry, 3),
        "released_s": round(released_at, 3) if released_at is not None else None,
        "old_commit_s": round(old_done, 3),
        "old_commit_ok": old["ok"],
        "a_final_state": dest.attempt_state("A"),
        "bypass_s": round(bypass_at[0], 3) if bypass_at else None,
        "retry_s": round(retry_commit_at, 3) if retry_commit_at is not None else None,
        "queued_s": round(queued_at[0], 3) if queued_at else None,
        "effects": effects,
        "duplicates": effects - len(set(dest.effects)),
        "fenced_rejected": dest.rejected,
        "polls": polls,
        "timed_out": timed_out,
        "released_before_old_commit": released_at is not None and released_at < old_done,
        "final_state": state,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=list(CASES), required=True)
    ap.add_argument("--stress", type=int, default=5)
    args = ap.parse_args()

    print(f"CASE={args.case} FENCED={CASES[args.case]['fenced']} "
          f"WITNESS={CASES[args.case]['witness']} POLICY={CASES[args.case]['policy']} "
          f"BYPASS={CASES[args.case]['bypass']} LEASE_S={LEASE_SECONDS} "
          f"ATTEMPT_LATENCY={ATTEMPT_LATENCY} RETRY_LATENCY={RETRY_LATENCY} "
          f"JANITOR_TIMEOUT={JANITOR_TIMEOUT} STRESS={args.stress}")
    results = [run_once(args.case, i + 1) for i in range(args.stress)]
    for r in results:
        print(f"  trial {r['trial']}: expiry@{r['expiry_s']}s released@{r['released_s']}s "
              f"old_commit@{r['old_commit_s']}s(ok={r['old_commit_ok']}, "
              f"state={r['a_final_state']}) bypass@{r['bypass_s']}s "
              f"retry@{r['retry_s']}s queued@{r['queued_s']}s "
              f"effects={r['effects']} duplicates={r['duplicates']} "
              f"fenced_rejected={r['fenced_rejected']} polls={r['polls']} "
              f"released_before_old_commit={r['released_before_old_commit']} "
              f"timed_out={r['timed_out']} final_state={r['final_state']}")
    print(f"SUMMARY case={args.case} trials={len(results)} "
          f"duplicate_writes_total={sum(r['duplicates'] for r in results)} "
          f"early_capacity_release={sum(1 for r in results if r['released_before_old_commit'])}/{len(results)} "
          f"retry_started={sum(1 for r in results if r['retry_s'] is not None)}/{len(results)} "
          f"fence_rejections={sum(r['fenced_rejected'] for r in results)} "
          f"capacity_released={sum(1 for r in results if r['released_s'] is not None)}/{len(results)} "
          f"queued_job_started={sum(1 for r in results if r['queued_s'] is not None)}/{len(results)} "
          f"timed_out={sum(1 for r in results if r['timed_out'])}/{len(results)}")


if __name__ == "__main__":
    main()
