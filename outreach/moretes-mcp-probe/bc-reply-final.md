Fernando, done. The raw responses and both tool schemas are now on issue #19, unedited, in my comment of 2026-11-07: https://github.com/fernando-moretes/moretes-aws-architect-mcp/issues/19. The seven JSON-RPC responses plus the full `tools/list` are also in a public folder, so you can diff them against your own runs: https://github.com/pinxiong/strands-in-action/tree/master/outreach/moretes-mcp-probe

The short version of what they show: your boundary holds on the output side and breaks on the input side, before the model writes a single line of prose.

The run, against `moretes-aws-architect` 0.4.1 over streamable HTTP on 2026-11-06.

`requirements_check` on your brief verbatim did the right thing. `requirements: []`, `constraints: []`, `validated: false`, and seven items under `decisionsToClarify`. The brief said 500 rps and no budget, SLO, RTO or RPO, and the server handed those back as questions rather than filling them in. Both `architecture_pattern` calls returned services, fit, tradeoffs and open questions, and not one number. `service_compare` returned three options plus `decisionRequired` instead of picking one.

Then `capacity_plan`, and this is where it breaks.

```text
Invalid tool input: durationMs: Invalid input: expected number, received undefined;
payloadKB: Invalid input: expected number, received undefined
isError: true
```

Correct behavior, and the schema is doing exactly what you designed it to do. But the exercise still asks for a capacity discussion, and the brief contains neither latency nor payload size, so the only way to continue is for the client to supply the two numbers. I supplied 250 ms and 4 KB. They were mine, not the team's.

```text
"assumptions": {"requestsPerSecond": 500, "durationMs": 250, "payloadKB": 4, "headroom": 1.3},
"averageConcurrency": 125,
"plannedConcurrency": 163,
"dailyRequests": 43200000,
"dailyPayloadGB": 172.8
```

500 came from the caller. 250 and 4 came from the model. 1.3 I passed because the schema made it required. All four land in one field called `assumptions`, and `plannedConcurrency: 163` sits downstream of all four. The sentence a reader would take away, "at 500 rps with 250 ms and 4 KB payloads you need 163 concurrent slots", reads as three facts. One is yours, two are mine, and the payload cannot say which is which.

So your question, as I experienced it. Could I tell server output from my own conclusions? Yes, because I knew what I had typed. Could a reader of my answer tell? No. Your server never invented a number. I did, and the response had no field that could record it.

One thing the schema inventory adds. Of the 48 tools in `tools/list`, 28 declare `validated`, `limitation` and `sources`. Twenty do not declare `validated` at all: six have no output schema, and the other fourteen return a schema without it. Those fourteen are the eight calculators plus `architecture_diagram`, `service_equivalents`, `postmortem`, `runbook`, `integration_catalog` and `integration_config`. Inside the fourteen the shapes even disagree with each other: five calculators use `limitations` plural with no `sources`, `cost_model` has neither field, `slo_budget` has `limitation` singular, and `retry_policy` has `sources` but no limitation. The issue comment includes a five-line script that reproduces those counts, so none of this rests on my word.

The uncomfortable part is which tools land in which group. The advisory tools, whose output a reader already treats as opinion, carry the provenance fields. The calculators, whose output gets quoted as numbers, do not.

Three suggestions, in the order I would take them.

1. Make `durationMs` and `payloadKB` optional and return `insufficientInputs` when they are absent, with the arithmetic that does not depend on them. `requirements_check` already answers "still open" with empty arrays and a question list. `capacity_plan` answering "cannot be sized yet" would make the two tools agree.
2. If they must stay required, accept `assumedFields: ["durationMs", "payloadKB"]` and echo a `provenance` block, so a client can render 250 ms as a footprint rather than a fact.
3. The rejection path carries no `structuredContent`, while the success path does. A client that wants to ask the user for exactly the missing fields has to parse English prose, on the one path where the server already knows which fields are missing. A `missing` array next to the message would turn the guard into a question instead of a dead end.

What already works and is worth protecting: `knownFacts` echoed verbatim, `decisionsToClarify` as a list, no cost figure anywhere in a run where no price was supplied, and `synthesis` ending on "Unknown stays unknown; do not fill gaps with assumptions". The rule is right. The only tool that can break it currently has no way to record who broke it.

Thank you for running the exercise in public. It is a much harder question than "does the tool work", and it is the one that decides whether the rest is worth anything.
