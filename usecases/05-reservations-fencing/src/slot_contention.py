"""C3: what a crashed holder costs the other workers, on the real clock.

8 worker threads contend for 2 leased slots. Each healthy worker holds its
slot for HOLD_SECONDS and releases it. One worker (the 5th) crashes while
holding a slot: it never releases. The crashed slot only comes back through
lease expiry, so workers queuing behind it wait the full lease duration.

Measured outputs: which worker got which slot, at what offset, and how long
the workers that inherited the crashed slot waited.
"""
import threading
import time

SLOTS = 2
WORKERS = 12
LEASE_SECONDS = 1.0
HOLD_SECONDS = 0.3
CRASH_WORKER = 0  # grabs a slot immediately, then crashes while holding it


class LeasedSlots:
    def __init__(self, count: int, lease_seconds: float) -> None:
        self.free = list(range(count))
        self.deadlines: dict[int, float] = {}
        self.lease_seconds = lease_seconds
        self.lock = threading.Lock()

    def acquire(self) -> tuple[int, str]:
        """Return (slot, how): 'free' or 'expired' once a lease lapses."""
        while True:
            with self.lock:
                now = time.monotonic()
                if self.free:
                    slot = self.free.pop(0)
                    self.deadlines[slot] = now + self.lease_seconds
                    return slot, "free"
                expired = [s for s, d in self.deadlines.items()
                           if d is not None and now >= d]
                if expired:
                    slot = expired[0]
                    self.deadlines[slot] = now + self.lease_seconds
                    return slot, "expired"
            time.sleep(0.005)

    def release(self, slot: int) -> None:
        with self.lock:
            self.deadlines.pop(slot, None)
            self.free.append(slot)


def main() -> None:
    slots = LeasedSlots(SLOTS, LEASE_SECONDS)
    got: list[dict] = []
    got_lock = threading.Lock()

    def worker(i: int) -> None:
        t0 = time.monotonic()
        slot, how = slots.acquire()
        waited = time.monotonic() - t0
        if i == CRASH_WORKER:
            # crash: hold the slot, never release, thread ends
            with got_lock:
                got.append({"worker": i, "slot": slot, "how": how,
                            "waited_s": round(waited, 3), "released": False})
            return
        time.sleep(HOLD_SECONDS)
        slots.release(slot)
        with got_lock:
            got.append({"worker": i, "slot": slot, "how": how,
                        "waited_s": round(waited, 3), "released": True})

    t_start = time.monotonic()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = time.monotonic() - t_start

    print(f"SLOTS={SLOTS} WORKERS={WORKERS} LEASE_S={LEASE_SECONDS} "
          f"HOLD_S={HOLD_SECONDS} CRASH_WORKER={CRASH_WORKER}")
    crash = next(g for g in got if g["worker"] == CRASH_WORKER)
    for g in sorted(got, key=lambda g: g["worker"]):
        print(f"  worker {g['worker']}: slot={g['slot']} acquired_via={g['how']} "
              f"waited={g['waited_s']}s released={g['released']}")

    expired_inherits = [g for g in got if g["how"] == "expired"]
    print(f"SUMMARY total_s={round(total, 3)} "
          f"crash_held_slot={crash['slot']} crash_waited={crash['waited_s']}s "
          f"slot_recycled_via_expiry={len(expired_inherits)} "
          f"first_expiry_inheriter_waited={min((g['waited_s'] for g in expired_inherits), default=None)}s "
          f"lease_was={LEASE_SECONDS}s")


if __name__ == "__main__":
    main()
