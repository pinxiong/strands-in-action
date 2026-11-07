First-use report for the exercise in #19. Everything below came off the public endpoint on 2026-11-06; the tool inventory was re-checked on 2026-11-07 and is unchanged.

```
Cliente / Client + version: curl 8.7.1, JSON-RPC 2.0 over streamable HTTP, no MCP UI.
  The model reading responses and writing the comparison was Claude in an agent loop.
Sistema operacional / OS: macOS 26.6.2
Modo / Mode: remote HTTP, https://mcp.moretes.com/mcp
Versão do servidor / Server version: 0.4.1 (serverInfo from initialize)
Etapa seguida / Step attempted: steps 1-4. requirements_check on the order-API brief,
  gaps confirmed, architect_panel with solution/security/finops, two alternatives via
  architecture_pattern, then capacity for the 500 rps figure.
Ferramentas chamadas / Tools actually called: tools/list, requirements_check,
  architect_panel, architecture_pattern (serverless-api, container-api),
  service_compare (compute), capacity_plan (once rejected by schema validation)
```

**Esperado / Expected**

- the gaps stay gaps
- assumptions distinguishable from supplied requirements
- no invented numbers

**Observado / Observed**

1. `requirements_check` did exactly that. `requirements: []`, `constraints: []`, `validated: false`, seven items under `decisionsToClarify`. The brief said 500 rps and no budget, SLO, RTO or RPO, and the server repeated that back as questions instead of filling it in.

2. Both patterns returned no sizing, cost or latency numbers: services, `fit`, tradeoffs, two open questions each. `service_compare` returned three options plus `decisionRequired` instead of a pick.

3. `capacity_plan` is where the separation breaks, and it breaks on the input side, before the model writes a line of prose. `durationMs` and `payloadKB` are required, the brief contains neither, and the server correctly refuses the call:

```json
{"result":{"content":[{"type":"text","text":"Invalid tool input: durationMs: Invalid input: expected number, received undefined; payloadKB: Invalid input: expected number, received undefined"}],"isError":true},"jsonrpc":"2.0","id":8}
```

The exercise still asks for a capacity discussion, so continuing means supplying the two numbers. I supplied 250 and 4. They were mine, not the team's. The server then returns one flat object:

```json
{"result":{"content":[{"type":"text","text":"{\"kind\":\"calculation\",\"assumptions\":{\"requestsPerSecond\":500,\"durationMs\":250,\"payloadKB\":4,\"headroom\":1.3},\"averageConcurrency\":125,\"plannedConcurrency\":163,\"dailyRequests\":43200000,\"dailyPayloadGB\":172.8,\"limitations\":[\"Assumes sustained rate all day; separate burst and average inputs\",\"Validate quotas, tail latency, downstream capacity, storage overhead and retries\"]}"}],"structuredContent":{"kind":"calculation","assumptions":{"requestsPerSecond":500,"durationMs":250,"payloadKB":4,"headroom":1.3},"averageConcurrency":125,"plannedConcurrency":163,"dailyRequests":43200000,"dailyPayloadGB":172.8,"limitations":["Assumes sustained rate all day; separate burst and average inputs","Validate quotas, tail latency, downstream capacity, storage overhead and retries"]}},"jsonrpc":"2.0","id":9}
```

`requestsPerSecond: 500` came from the caller. `durationMs: 250` and `payloadKB: 4` came from the model. `headroom: 1.3` is a value I passed because the schema made it required. All four land in one field called `assumptions`; `plannedConcurrency: 163` follows from `requestsPerSecond`, `durationMs` and `headroom`, while `payloadKB` feeds the payload figure. Nothing in the response records which of the four was mine.

So, the question in the issue as I experienced it: could I separate server output from my own conclusions? Yes, because I knew what I had typed. Could a reader of my answer? No.

**Tool schemas**

`capacity_plan` input, from `tools/list`:

```json
{
  "type": "object",
  "properties": {
    "requestsPerSecond": {"type": "number", "minimum": 0, "maximum": 1000000000},
    "durationMs": {"type": "number", "minimum": 0, "maximum": 86400000},
    "payloadKB": {"type": "number", "minimum": 0, "maximum": 1000000000},
    "headroom": {"type": "number", "default": 1.3, "minimum": 1, "maximum": 10}
  },
  "required": ["requestsPerSecond", "durationMs", "payloadKB", "headroom"],
  "additionalProperties": false
}
```

`capacity_plan` output: `kind`, `assumptions`, `averageConcurrency`, `plannedConcurrency`, `dailyRequests`, `dailyPayloadGB`, `limitations`. No `validated`, no `sources`, no per-field provenance.

`requirements_check` output, same server: `kind`, `validated`, `limitation`, `sources`, `workload`, `requirements`, `constraints`, `decisionsToClarify`, `nextTools`. Two tools, two different models of what "I did not make this up" looks like.

**Inventory, 48 tools in `tools/list`**

- 28 declare `validated`, `limitation` and `sources`
- 20 do not declare `validated`. Six of those return no output schema at all; the other 14 return one without it, and that group is the eight calculators (`capacity_plan`, `cost_model`, `slo_budget`, `latency_budget`, `queue_sizing`, `retry_policy`, `storage_growth`, `finops_unit_economics`) plus six others (`architecture_diagram`, `service_equivalents`, `postmortem`, `runbook`, `integration_catalog`, `integration_config`). None of the eight calculators carries all three fields together.

Inside that 14 the shapes disagree. Five calculators use `limitations` plural and carry no `sources`. `cost_model` has neither field. `slo_budget` has `limitation` singular and no `sources`. `retry_policy` has `sources` and no limitation. `postmortem`, `runbook`, `integration_catalog` and `integration_config` carry none of the three.

To check it without trusting me:

```bash
curl -sX POST https://mcp.moretes.com/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' > tools.json
python3 - <<'PY'
import json
tools = json.load(open("tools.json"))["result"]["tools"]
props = lambda t: set(((t.get("outputSchema") or {}).get("properties") or {}).keys())
noval = [t for t in tools if "validated" not in props(t)]
print(len(tools))
print(sum(1 for t in tools if {"validated", "limitation", "sources"} <= props(t)))
print(len(noval), sum(1 for t in noval if not t.get("outputSchema")),
      sum(1 for t in noval if t.get("outputSchema")))
PY
# 48 tools / 28 with all three / 20 without validated / 6 no schema / 14 schema but no validated
```

My saved copy of that response is 68217 bytes and today's call returns the same size, so the inventory has not moved between the run and this report.

**Sugestão / Suggested improvement**

1. Make `durationMs` and `payloadKB` optional, return `insufficientInputs: ["durationMs", "payloadKB"]` with the arithmetic that does not depend on them. `requirements_check` already answers "still open" with empty arrays and a question list; `capacity_plan` answering "cannot be sized yet" would make the two tools agree.

2. If they must stay required, accept `assumedFields: ["durationMs", "payloadKB"]` and echo a `provenance` block, so a client can render 250 ms as a footprint rather than a fact.

3. The rejection path carries no `structuredContent`, while the success path does. So a client asking the user for exactly the missing fields must parse English prose, on the one path where the server already knows which fields are missing. `{"missing": ["durationMs", "payloadKB"]}` next to the message would turn the guard into a question instead of a dead end.

**Raw responses**

All seven, plus `tools/list`, unedited: https://github.com/pinxiong/strands-in-action/tree/master/outreach/moretes-mcp-probe

- `01-requirements-check.json` — gaps come back as questions
- `02-architect-panel.json` — panel with solution, security, finops
- `03-pattern-serverless.json`, `04-pattern-container.json` — no sizing or cost numbers in either
- `05-service-compare.json` — three options, `decisionRequired`
- `06-capacity-missing.json` — the schema rejection
- `07-capacity-invented.json` — the flat `assumptions` object
- `tools-list.json` — the 48-tool inventory used above

Smaller note, as data rather than complaint: the `limitation` string is identical across the five tools I called, and `sources` is the Well-Architected landing page for each. That reads as a disclaimer rather than claim-level provenance. "DynamoDB access patterns must be designed first" arrives with no source attached.

What already works and is worth protecting: `knownFacts` echoed verbatim, `decisionsToClarify` as a list, no cost figure in a run where no price was supplied, and `synthesis` ending on "Unknown stays unknown; do not fill gaps with assumptions". The rule is right. The one place it broke in this run has no way to record who broke it.
