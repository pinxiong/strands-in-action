Thanks Igor — this is a fair challenge to a line I wrote, and running it changed my answer. The article says "If you need a barrier, you have to build it yourself with a condition that inspects `state.completed_nodes`." That sentence is too narrow. I ran nine offline cases on strands-agents 1.63.0 (Python 3.11, scripted models, no LLM) and found three patterns where your own code neither inspects nor writes `state.completed_nodes`. Probe: https://github.com/pinxiong/strands-in-action/blob/master/outreach/uc07-comments/probe_barrier_join.py · raw output: https://github.com/pinxiong/strands-in-action/blob/master/outreach/uc07-comments/evidence/barrier-join.txt

Setup is the article's fan-in: `A -> B`, `A -> join`, `B -> join`. A says "no objection", B says "VETO". The join decides from the text it is given and calls a tool standing in for an external effect. B has a fixed 0.15 s scripted delay so that when a join shares a batch with B, the completion order stays stable; the batches themselves come from the `A -> B` edge. The `CASE failed_parent` variant uses a 0.5 s delay and a 0.1 s node timeout instead.

The baseline, and the trap. `CASE no_barrier` and `CASE barrier_one_edge` produced the same five lines:

```
  status: Status.COMPLETED
  execution_order: ['A', 'join', 'B', 'join']
  join_invocations: 2
  parent_sets: ['A', 'A,B']
  decisions: ['approve', 'veto']
```

Guarding only `B -> join` does not help. Readiness is an OR over incoming edges from the completed batch (`graph.py:1021-1038`), and in `CASE barrier_one_edge` the `A -> join` edge still carries an always-true condition, so it satisfies the OR.

What I would recommend, in order — this is a design judgement, not something these runs prove:

**1. Prefer topology over predicates.** If the join can have a single incoming edge, drop `A -> join` and keep `A -> B -> join`. There is nothing left for the OR to fire on: your code adds no condition and does not read or write `state.completed_nodes`. `CASE single_incoming_edge`:

```
  execution_order: ['A', 'B', 'join']
  join_invocations: 1
  parent_sets: ['B']
  decisions: ['veto']
  effects_written: 1
  effect_ledger: [{'decision': 'veto', 'parents': 'B'}]
  final_join_result_text: DECISION veto
  condition_calls: 0
```

The cost shows up in `parent_sets: ['B']`. The SDK's `_build_node_input` (`graph.py:1286-1293`) folds in results from the join's direct incoming-edge parents only; with `A -> join` removed, A's text no longer reaches the join. You have to pass it through explicitly. That is a different trade-off from a state hack, but it is not free.

**2. If you must keep the fan-in, put the same read-only predicate on every incoming edge.** Two sources work without writing anything into graph state; I would start with the first one and reach for the second when you already keep caller-owned context:

**Option A — `state.results`.** The runtime fills this dict at `graph.py:1177`, and also at `graph.py:1216` for failed nodes. The predicate is `PARENTS.issubset(set(state.results))` with `PARENTS = {"A", "B"}`. `CASE barrier_results` (the same eight lines also appear in `CASE barrier_completed_nodes` and, as the first eight lines, in `CASE barrier_invocation_state`):

```
  execution_order: ['A', 'B', 'join']
  join_invocations: 1
  parent_sets: ['A,B']
  decisions: ['veto']
  effects_written: 1
  effect_ledger: [{'decision': 'veto', 'parents': 'A,B'}]
  final_join_result_text: DECISION veto
  condition_calls: 4
```

**Option B — `invocation_state`.** This is a caller-owned dict: an `AfterNodeCallEvent` hook records finished node ids into it, and the predicate reads only that dict, never `graph.state`. In `CASE barrier_invocation_state` the first eight lines match `CASE barrier_results`. The `barrier_done` line below is a set stored inside that dict; it lists `join` because the hook fires for every finished node including the join itself (`graph.py:1230`), while the predicate only checks that A and B are present, so the extra id is harmless. The run:

```
  execution_order: ['A', 'B', 'join']
  join_invocations: 1
  parent_sets: ['A,B']
  decisions: ['veto']
  effects_written: 1
  effect_ledger: [{'decision': 'veto', 'parents': 'A,B'}]
  final_join_result_text: DECISION veto
  condition_calls: 4
  barrier_done: ['A', 'B', 'join']
```

Both gave one join, both parents and the veto decision. `CASE barrier_completed_nodes` (the article's version) also gave one join, so it works; it is just not the only option. `CASE barrier_results_same_batch`, with A and B as two entry points, also gave one join, so the barrier holds when parents finish in one batch.

**3. Two rules for the predicate.** Put it on every incoming edge — the `CASE barrier_one_edge` result above shows why. Keep it free of side effects: the runtime calls `should_traverse` again while building the node input (`graph.py:1286-1293`), so a wrapped counter recorded 4 predicate evaluations in `CASE barrier_results` even though the join ran once. A predicate that increments its own counter would be counting the wrong thing. With `CASE single_incoming_edge` no predicate is needed at all: `should_traverse` still runs, but with no condition it returns `True` without calling any predicate (`graph.py:219-220`), so `condition_calls` is 0.

The part I would flag before shipping this: in these runs a strict barrier traded "runs at least once" for "runs zero or one times". `CASE missing_parent` adds a third parent that never runs:

```
  status: Status.COMPLETED
  execution_order: ['A', 'B']
  join_invocations: 0
  parent_sets: []
  decisions: []
  effects_written: 0
  effect_ledger: []
  final_join_result_text: none (join never ran)
```

`COMPLETED`, yet the join never ran. `CASE failed_parent` times B out with the SDK node timeout:

```
  status: Exception: Node 'B' execution timed out after 0.1s
  execution_order: ['A']
  join_invocations: 0
  parent_sets: []
  decisions: []
  effects_written: 0
  effect_ledger: []
  final_join_result_text: none (join never ran)
  condition_calls: 1
  barrier_done: []
  completed_nodes: 1
  execution_count: 1
  results_keys: ['A', 'B']
```

In `CASE failed_parent` the SDK raised, so no `GraphResult` was returned; `results_keys` still lists A and B, which shows a key in `state.results` does not mean that parent succeeded. That case is why a barrier needs an explicit timeout and failure policy. `CASE missing_parent` is the quieter one: the run returned `Status.COMPLETED` with zero joins, so `GraphResult.status == COMPLETED` is not evidence that the join ran; check for the join's entry in `results`.

Scope: nine offline cases, one fan-in family with a few topology variants, scripted models with fixed synthetic token accounting (100 input + 20 output = 120 per call), one in-process list standing in for the external effect, no Bedrock calls. I did not test concurrent writers, a crash window, a real store's dedup semantics, barriers across processes, or other SDK versions.

If you have a shape where the single-edge option is not available, I would be glad to run it — that is the case where the choice between `state.results` and `invocation_state` actually gets interesting.
