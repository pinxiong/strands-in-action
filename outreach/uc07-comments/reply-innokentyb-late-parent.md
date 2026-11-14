Thanks Kent — I had not run that case, so I built it. Short answer: the late parent does change the decision on the second invocation, but the graph does not revise anything. It runs the join again and overwrites the first result. Your idempotency key does stop the duplicate write; with one fixed key per task it also silently keeps the decision made from a partial parent set.

Probe and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc07-comments

Setup: offline scripted models, strands-agents 1.63.0, Python 3.11, no LLM, a fixed synthetic 100 input + 20 output = 120 tokens per model call. The late cases use the article's `A -> B`, `A -> join`, `B -> join` graph. A returns text containing `no objection`, B returns text containing `VETO` after a 0.3 s scripted delay, and the join's decision is a plain string test on the text it is given. The join applies its decision through a tool standing in for the external effect. The `same_batch` case is the exception: A and B are both entry points, with no `A -> B` edge.

One correction to the framing. This is not at-least-once delivery in the transport sense: I did not find an ack, replay or redelivery mechanism in this SDK path. Readiness is re-evaluated once per completed batch, and `_is_node_ready_with_conditions` returns True on the first satisfied incoming edge from a node in that batch (graph.py:1021-1038). When both parents finish in the same batch, the join runs once:

```
  execution_order: ['A', 'B', 'join']
  join_invocations: 1
  parent_sets: ['A,B']
  decisions: ['veto']
  effect_attempts: 1
  effects_written: 1
  effect_ledger: [{'key': 'brief-42', 'decision': 'veto', 'parents': 'A,B'}]
```

In these two shapes the duplicate tracks parents arriving in different batches, and I found no cross-batch deduplication in the runtime (within one batch, candidate nodes are deduplicated into a set at graph.py:1013). That is why I put the key in the effect rather than in the graph. The `same_batch` contrast also changes the topology, so this is an observation from these two shapes, not a single-variable proof.

Now the late parent. With no key, the two invocations see different parent sets, reach opposite decisions, and both effects land:

```
  execution_order: ['A', 'join', 'B', 'join']
  join_invocations: 2
  parent_sets: ['A', 'A,B']
  decisions: ['approve', 'veto']
  effect_attempts: 2
  effects_written: 2
```

With one fixed key per task, as you suggest, the second write is suppressed — and that is the trap:

```
  effect_attempts: 2
  effects_written: 1
  effect_ledger: [{'key': 'brief-42', 'decision': 'approve', 'parents': 'A'}]
  suppressed: ['brief-42']
  final_join_result_text: DECISION veto
```

`effect_ledger` still holds approve while the graph's final join result is veto. The key protected the in-process ledger from a second write, but the decision left applied is the one made from a partial parent set. A key alone gives you one write in this probe (at-most-once on the write), not correctness. I did not test the crash/restart or real-store cases that end-to-end exactly-once would require.

On revision specifically: `state.results[node.node_id] = node_result` is a plain overwrite (graph.py:1177), and `GraphResult` has no revision or supersede field; its only ordered, per-invocation trace is `execution_order`. Both join entries in that list resolve to one NodeResult object. The three lines below are from `CASE late_fixed_key`; the same figures appear in the other three late-parent cases:

```
  join_result_refs_unique: 1
  completed_nodes: 3
  execution_count: 4
```

`completed_nodes` is 3 while `execution_count` is 4 because `GraphResult.completed_nodes` is `len(state.completed_nodes)` (graph.py:1344) over a set of node objects (graph.py:141), while `execution_count` increments on every execution, including the second join (graph.py:1239). The field itself is an int (graph.py:188). From `GraphResult` alone you cannot reconstruct which parents were present on invocation 1; the probe recovered it only because `apply_effect` recorded `parents` on each invocation (the `parent_sets` rows in the evidence). Recording that set inside each invocation, as you propose, is where it exists in this probe's records.

Two shapes that hold:

**1) If the first effect must not exist until every parent is in**, put the barrier condition on every incoming edge. Guarding only `B -> join` is not enough: the `A -> join` edge is the only satisfied incoming edge in that batch (the `B -> join` source is not in `completed_batch` yet), so the OR fires before B completes.

```
  join_invocations: 2
  parent_sets: ['A', 'A,B']
  decisions: ['approve', 'veto']
```

With both edges guarded by "A and B are in `state.completed_nodes`":

```
  execution_order: ['A', 'B', 'join']
  join_invocations: 1
  parent_sets: ['A,B']
  decisions: ['veto']
  effect_attempts: 1
  effects_written: 1
  effect_ledger: [{'key': 'brief-42', 'decision': 'veto', 'parents': 'A,B'}]
```

**2) If the first effect must land early**, version the key by parent set. `CASE late_versioned_key` wrote `brief-42:parents=A` (approve) then `brief-42:parents=A,B` (veto), so a caller could in principle replace the first decision — I did not implement that; the two entries simply coexist in the ledger (`effects_written: 2`). I did not find a revision mechanism in `GraphResult`, so that reconciliation would have to be caller-side code.

Scope: one 0.3 s delay, one join, one in-process ledger standing in for the external system, fixed synthetic token accounting, no Bedrock calls. I did not test concurrent writers, a crash between the effect and the key write, or a real store's dedup semantics.
