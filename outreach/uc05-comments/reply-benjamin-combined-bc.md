Good catch, and you are pointing at the sentence I deliberately left open: the article says the two repairs were run separately, never together. I ran them together to answer this. One setup note first. The article's authoritative branch reconciles once at expiry, then joins the old thread and checks has_effect again (src/delayed_commit_race.py:99-115, :128, :134-137). It has no polling janitor, so it cannot answer a liveness question on its own. I added a 10 ms polling janitor with a 3.2 s cap, keeping the same real-clock values (lease 1.0 s, old attempt 2.4 s, retry 0.4 s), five runs per case on Python 3.11.15.

The first thing that changes is the premise about the retry. With both repairs on and no competing writer, the witness sees A as in_flight at expiry, so the reservation stays in outcome_unknown until A commits and capacity is held until then. Across all four combined cases retry_started was 0/5. Nothing on the retry side is waiting for a terminal state. Where waiting does happen, it is the janitor holding capacity, not a retry waiting on a result. The fence can only reject A if another writer put the same key first, and a writer that bypasses the reservation is outside the policy in the article.

With both on and no competing writer, the fence stays idle:

SUMMARY case=combined trials=5 duplicate_writes_total=0 early_capacity_release=0/5 retry_started=0/5 fence_rejections=0 capacity_released=5/5 queued_job_started=5/5 timed_out=0/5

Capacity returned between 2.406 s and 2.416 s, around the 2.402 s to 2.407 s commit, with no early release. That is the same shape as witness-only, including zero duplicate writes.

To produce your exact case I added a writer B that commits K at about 0.5 s without holding the reservation. A arrives at about 2.4 s and is refused. Three janitor policies, one variable at a time:

SUMMARY case=conflict/effect_first trials=5 duplicate_writes_total=0 early_capacity_release=5/5 retry_started=0/5 fence_rejections=5 capacity_released=5/5 queued_job_started=5/5 timed_out=0/5
SUMMARY case=conflict/attempt_terminal trials=5 duplicate_writes_total=0 early_capacity_release=0/5 retry_started=0/5 fence_rejections=5 capacity_released=5/5 queued_job_started=5/5 timed_out=0/5
SUMMARY case=conflict/committed_whitelist trials=5 duplicate_writes_total=0 early_capacity_release=0/5 retry_started=0/5 fence_rejections=5 capacity_released=0/5 queued_job_started=0/5 timed_out=5/5

The article's own order is effect_first. At expiry K already exists, so it settles confirmed_existing on the first janitor poll and returns capacity at about 1.003 s, while A is still in flight and is rejected at about 2.405 s. Zero duplicates, but the slow attempt's work is wasted and capacity moves before A's outcome is known. In that order your question never comes up, because the effect lookup decides before the attempt state is used.

It becomes real when the janitor waits on A's recorded state. commit() in the article's script writes self.attempts[attempt_id] = "fenced" on rejection (src/delayed_commit_race.py:48-51), and the probe copies that Destination class with the same semantics (probe_fence_witness.py:61-69), so the destination does record an explicit final state. With fenced in the terminal set, the reservation closes at about 2.41 s with no early release. With a terminal set containing only committed, the reservation stays in outcome_unknown until the 3.2 s cap: capacity_released=0/5, queued_job_started=0/5, timed_out=5/5. A queued job never starts. That is the terminal-state-never-arrives failure you describe, on the janitor and capacity side rather than the retry side; in this probe it is a capacity leak, not a stuck retry.

So the direct answer: in the code as published, a fence rejection is not treated as a terminal state, and the reconciler never needs it to be, because the has_effect lookup has priority and K exists whenever a put-if-absent rejection occurs. In any implementation that does wait on attempt state, fenced has to be in the terminal set (or the effect lookup has to stay the first exit), otherwise outcome_unknown has no way out. I did not run the case where the destination never reports anything at all, so I cannot say how long such a wait should be bounded.

Scope: threads on one machine with a monotonic clock, five runs per case at one fixed timing. I did not test network partitions, clock skew, multiple keys, or a bypass writer at other timings.

Probe and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc05-comments (probe_fence_witness.py, evidence/fence-witness-combined.txt). Happy to run a different terminal-state rule if you have one in mind.
