First-use report for the exercise in #19, run against the remote endpoint at `mcp.moretes.com`, server version 0.4.1.

Short version: the separation you ask about holds on the server side and leaks on the input side. It breaks before the model writes a single sentence of prose, at the point where the client has to fill a required argument.

```
Cliente / Client + version: curl 8.7.1 with a Python 3.11 wrapper sending JSON-RPC 2.0
  over streamable HTTP. No MCP client UI. The model reading the results and writing
  the comparison was Claude, in an agent loop.
Sistema operacional / OS: macOS 26.6.2
Modo / Mode: remote HTTP, https://mcp.moretes.com/mcp
Versão do servidor / Server version: 0.4.1 (from serverInfo)
Etapa seguida / Step attempted: steps 1 to 4 of the issue. requirements_check on the
  order API brief, gaps confirmed, architect_panel with solution, security and finops,
  two alternatives through architecture_pattern, then capacity for the 500 rps figure.
Ferramentas chamadas / Tools actually called: tools/list, requirements_check,
  architect_panel, architecture_pattern (serverless-api, container-api),
  service_compare (compute), capacity_plan twice, once rejected by schema validation.
```

**Esperado / Expected**

- the gaps stay gaps
- assumptions distinguishable from supplied requirements
- no invented numbers

**Observado / Observed**

1. `requirements_check` did exactly that. `requirements: []`, `constraints: []`, `validated: false`, and seven items under `decisionsToClarify`. Nothing was invented to fill the space. The brief said 500 rps and no budget, SLO, RTO or RPO, and the response repeated that back as questions.

2. Both patterns came back with no numbers at all. Services, `fit`, tradeoffs, two open questions each. No cost, no sizing, no latency figure. `service_compare` returned three options and `decisionRequired` instead of picking one.

3. `capacity_plan` is where it goes wrong. `durationMs` and `payloadKB` are required, the brief contains neither, and the schema rejects the call with both fields named and `isError: true`. That is correct behavior. But the exercise asks for a capacity discussion, so the client has to continue, and continuing means supplying the two missing numbers. I supplied 250 ms and 4 KB. They were invented by me, not by the team.

The response then returns them as one flat object:

```json
{
  "kind": "calculation",
  "assumptions": {"requestsPerSecond": 500, "durationMs": 250, "payloadKB": 4, "headroom": 1.3},
  "averageConcurrency": 125,
  "plannedConcurrency": 163,
  "dailyRequests": 43200000,
  "dailyPayloadGB": 172.8
}
```

`requestsPerSecond: 500` came from the caller. `durationMs: 250` and `payloadKB: 4` came from the model. The payload labels all four the same way, and everything after them is downstream of two invented numbers that now read as inputs.

So, answering the question in the issue as I actually experienced it: I could tell server output from my own conclusions, because I knew what I had typed. A reader of my answer could not. The sentence I would have written, "at 500 rps with a 250 ms p95 and 4 KB payloads you need 163 concurrent slots", reads as three facts. One is yours, two are mine.

**Trecho mínimo / Minimal synthetic example**

The two calls above, nothing else. The first one is the guard working. The second is the guard being paid to step aside.

**Sugestão / Suggested improvement**

1. Make `durationMs` and `payloadKB` optional and return `insufficientInputs: ["durationMs", "payloadKB"]` with the partial arithmetic that does not depend on them. `requirements_check` already behaves this way with an empty `requirements` array, so the two tools disagree with each other on the same server. Answering "this cannot be sized yet" is more useful than forcing a guess.

2. If the inputs must stay required, let the caller mark provenance per field, for example `assumedFields: ["durationMs", "payloadKB"]`, and echo a `provenance` block back. A client can then render 250 ms as a footprint instead of a fact, and a UI can put both numbers in the same visual class they belong to.

3. `decisionRequired` is a sentence, "Collect workload evidence and current pricing before selecting". A boolean plus an `openQuestions` count would let a client gate on it mechanically instead of parsing prose. Right now the field with the strongest instruction in the whole server is the one a script cannot read.

Two smaller notes, offered as data rather than complaint.

Of the 48 tools in `tools/list`, 28 return `validated`, `limitation` and `sources`. Fourteen return a schema with different names, and the calculator family is in that group: `capacity_plan`, `cost_model`, `latency_budget`, `retry_policy`, `slo_budget`, `storage_growth`, `queue_sizing`, `finops_unit_economics` and others. Six have no output schema at all. The tools whose numbers get quoted as fact are the ones without `validated` and `sources`.

The `limitation` string is identical across the five tools I called, and `sources` is the Well-Architected landing page for all of them. That is a disclaimer, not claim-level provenance. "DynamoDB access patterns must be designed first" arrives with no source attached to it.

What already works, and is worth protecting: `knownFacts` echoed verbatim, so supplied text stays traceable. `decisionsToClarify` as a list rather than a paragraph. No cost figure anywhere in a run where no price was supplied. `synthesis` ending on "Unknown stays unknown; do not fill gaps with assumptions", which is the right rule. The gap is that rule lives in a string, and the only tool that could break it has no way to enforce it.

I can attach the raw JSON responses, or rerun the same script against a later version if that helps.
