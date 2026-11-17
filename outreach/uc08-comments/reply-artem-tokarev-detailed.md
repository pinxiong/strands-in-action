# BC comment reply · detailed edition · Artem Tokarev · UC08

Comment id `3MBVsKFgl5QdXTvcZ4QmNEGXh6C`, posted 2026-11-16T10:15:52+00:00 on
<https://builder.aws.com/content/3MBSAPbU1zpRZTXGz7LfqJ22Jst/orchestrating-agents-less-freedom-for-the-model-more-certainty-for-you>.

> Since `workflow` passes raw text without schema validation or replay support, how do you see it fitting alongside Strands' native `GraphBuilder` (or `structured_output`) in production? Is there a clean pattern to wrap `workflow` tasks with Pydantic validation and external state, or would you recommend skipping the vended `workflow` tool altogether in favor of custom Python orchestration?

This is the **detailed** companion to `reply-artem-tokarev-bc.txt` (185 words, three
paragraphs). It was assembled on 2026-11-17 from material that had already been
independently verified on 2026-11-16; **no new experiment or verification was run**.
The first three paragraphs are byte-for-byte the verified short reply. Everything
after them is either verbatim probe source, verbatim stdout, or verbatim UC08
evidence lines, plus connective prose that introduces no new technical claim.

Paste-ready plain-text version: `reply-artem-tokarev-detailed-bc.txt` (no backticks,
no fences, no bold, no Markdown links). Do not auto-post.

## Reply

Hi Artem, good question. Short answer: they are different layers. structured_output is Agent-level; workflow 0.8.11 just calls task_agent(task_prompt) and hands the next step a rendered string. workflow.py has no structured_output, BaseModel, pydantic or validator identifier, and the output_schema, returns, expects and validator keys I declared were stored but never read. GraphBuilder gives topology and state, but the 0.8.11 workflow does not wire it into task output validation.

A Pydantic wrapper is doable, but you own the parsing and the failure path: my probe had to extract the JSON from that rendered prompt first, and UC08 measured a tool exception still reported as 100% success. State is an in-process singleton, so a hand-edited file gets overwritten and a restart in a new process replays zero steps.

For production work needing contracts or replay, I would orchestrate in my own Python (or GraphBuilder plus my own validator and store), use structured_output on an Agent I control, and treat the vended workflow as a scheduling prototype. I have not run that wrapper end to end, so I will not call it clean yet. Probe and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc08-comments

Here is the detail behind that short answer. Each block below is either verbatim probe code (dedented only for display), verbatim stdout, or verbatim UC08 evidence lines. Reproducing the probe needs no LLM call.

### Part 1 - Environment and the source-level check

Probe source, `probe_graphbuilder_pydantic.py` lines 46-67 (dedented 4 spaces for display):

```python
print("=== A1 workflow.py integration symbols ===")
lines = WF.read_text().splitlines()
for kw in ["structured_output", "GraphBuilder", "BaseModel", "pydantic",
           "output_schema", "validator"]:
    hits = [i + 1 for i, line in enumerate(lines) if kw in line]
    print(f"{kw}: {len(hits)} hits {hits[:5]}")

print("=== A2 step boundary is rendered text ===")
for i, line in enumerate(lines, 1):
    if "context.append(f\"Results from" in line or "task_agent(task_prompt)" in line:
        print(f"{i}: {line.strip()}")
print("Agent.structured_output", inspect.signature(Agent.structured_output))

print("=== A3 multiagent schema symbols ===")
for kw in ["structured_output", "BaseModel", "model_validate", "pydantic",
           "output_schema"]:
    hits = []
    for f in sorted(MULTI.rglob("*.py")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if kw in line:
                hits.append(f"{f.name}:{i}")
    print(f"{kw}: {len(hits)} hits {hits[:5]}")
```

`evidence/probe-output.txt` lines 1-4 and 6-22, verbatim (line 5 is the local venv path, omitted):

```text
=== ENV ===
strands-agents 1.63.0
strands-agents-tools 0.8.11
pydantic 2.14.2
=== A1 workflow.py integration symbols ===
structured_output: 0 hits []
GraphBuilder: 0 hits []
BaseModel: 0 hits []
pydantic: 0 hits []
output_schema: 0 hits []
validator: 0 hits []
=== A2 step boundary is rendered text ===
425: context.append(f"Results from {dep_id}:\n" + "\n".join(dep_content))
444: result = task_agent(task_prompt)
Agent.structured_output (self, output_model: type[~T], prompt: str | list[strands.types.content.ContentBlock] | list[strands.types.interrupt.InterruptResponseContent] | list[strands.types.content.Message] | None = None) -> ~T
=== A3 multiagent schema symbols ===
structured_output: 0 hits []
BaseModel: 0 hits []
model_validate: 0 hits []
pydantic: 0 hits []
output_schema: 0 hits []
```

A1 and A3 are identifier checks on the installed 0.8.11 sources, not runtime behaviour. `workflow.py` docstrings do contain the English word "validation" (lines 12, 25, 936, 941), but those describe dependency resolution and tool filtering, not output-schema validation. A2 is the step boundary: the two printed source lines plus the `Agent.structured_output` signature, which lives on `Agent` rather than on the workflow task path.

### Part 2 - What the next step actually receives

Probe source, lines 28-29 and 69-75 (dedented; the input is UC08's recorded prompt, not an invented string):

```python
ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "usecases/08-workflow/evidence/wf-contract-passthrough.txt"
txt = EVID.read_text()
m = re.search(r"^downstream_prompt_full=(.*?)(?=^note=)", txt, re.S | re.M)
assert m, "downstream_prompt_full block not found in UC08 evidence"
prompt = m.group(1).rstrip("\n")
print("prompt_bytes:", len(prompt.encode()))
print("prompt_repr:", repr(prompt))
```

`evidence/probe-output.txt` lines 23-25, verbatim:

```text
=== B recorded downstream prompt ===
prompt_bytes: 243
prompt_repr: 'Previous task results:\nResults from calc:\n{"total": 3640, "cost_usd": 0.002912}\n\nCurrent Task:\nUsing the previous results, call save_draft with the total and cost. Then reply with the exact upstream text you were given, enclosed in <raw> tags.'
```

`usecases/08-workflow/evidence/wf-contract-passthrough.txt` lines 31-37, verbatim:

```text
downstream_prompt_full=Previous task results:
Results from calc:
{"total": 3640, "cost_usd": 0.002912}

Current Task:
Using the previous results, call save_draft with the total and cost. Then reply with the exact upstream text you were given, enclosed in <raw> tags.
note=downstream receives a rendered natural-language string built by execute_task, not a typed field
```

### Part 3 - Declared contract keys are stored, never read

`usecases/08-workflow/evidence/wf-contract-schema.txt` lines 30-33, verbatim:

```text
declared_extra_fields=['output_schema', 'returns', 'expects', 'validator']
create_response={'status': 'success', 'content': [{'text': "✅ Created modern workflow 'wf-contract-schema' with 2 tasks"}]}
persisted_task_keys={'research': ['dependencies', 'description', 'expects', 'output_schema', 'priority', 'returns', 'task_id', 'timeout', 'tools', 'validator'], 'calc': ['dependencies', 'description', 'output_schema', 'priority', 'task_id', 'timeout', 'tools']}
note=create_workflow only checks task_id, description and that a dependency id exists; extra keys are copied verbatim and never read
```

Four keys were declared. `research` persisted all four; `calc` persisted only `output_schema`. The short reply says "keys I declared", not "every task".

### Part 4 - What a Pydantic wrapper actually has to do

Probe source, lines 34-36 and 77-97 (dedented):

```python
class CalcResult(BaseModel):
    total: int
    cost_usd: float

print("=== B1 json.loads on the whole rendered prompt ===")
try:
    json.loads(prompt)
    print("PARSE: ok")
except json.JSONDecodeError as e:
    print("PARSE: JSONDecodeError:", e.msg, "at pos", e.pos)

print("=== B2 extract embedded JSON object then Pydantic validate ===")
m2 = re.search(r'\{[^{}]*"total"[^{}]*\}', prompt)
assert m2, "no embedded JSON object in recorded prompt"
print("extracted:", repr(m2.group(0)))
validated = CalcResult.model_validate(json.loads(m2.group(0)))
print("validated:", validated.model_dump())

print("=== B3 wrong type is rejected by Pydantic ===")
try:
    CalcResult.model_validate({"total": "not-a-number", "cost_usd": 0.002912})
    print("BAD: accepted")
except ValidationError as e:
    err = e.errors()[0]
    print("BAD: ValidationError:", err["type"], "loc=", err["loc"])
```

`evidence/probe-output.txt` lines 26-36, verbatim:

```text
=== B1 json.loads on the whole rendered prompt ===
PARSE: JSONDecodeError: Expecting value at pos 0
=== B2 extract embedded JSON object then Pydantic validate ===
extracted: '{"total": 3640, "cost_usd": 0.002912}'
validated: {'total': 3640, 'cost_usd': 0.002912}
=== B3 wrong type is rejected by Pydantic ===
BAD: ValidationError: int_parsing loc= ('total',)
=== BOUNDED CONCLUSION ===
workflow.py has no structured_output/BaseModel/pydantic/output_schema/validator symbol
the step boundary is a rendered string; a Pydantic wrapper must parse it itself
this probe did not run a new Bedrock workflow; input is the UC08 recorded prompt
```

So the wrapper owns three things the vended tool does not give it: pulling the object out of a natural-language prompt, defining the failure path when parsing fails, and deciding where the validated value is stored. B3 only shows that Pydantic rejects a wrong type; it is not an end-to-end integration test.

### Part 5 - Failure visibility, state and restart

`wf-failure-swallowed.txt` lines 25-26, verbatim:

```text
run={'created': {'status': 'success', 'content': [{'text': "✅ Created modern workflow 'wf-failure-swallowed' with 2 tasks"}]}, 'start_returned': {'status': 'success', 'content': [{'text': "🎉 Workflow 'wf-failure-swallowed' completed successfully! (2/2 tasks succeeded - 100.0%)"}]}, 'elapsed_s': 20.32, 'busy_loop': False, 'seconds_budget': 30}
injected=explode() raises RuntimeError
```

`wf-replay-manual.txt` lines 47 and 49, verbatim:

```text
patched_status_seen_by_start={'calc': 'completed', 'write': 'pending'}
note=restart skips completed steps and cannot reach total_tasks, so start_workflow busy-loops; the replayed step never reran (save_draft stays at 1 call). Only a fresh delete + create would repeat the side effect, and there is no idempotency key to deduplicate it
```

`wf-restart-restart.txt` lines 1 and 12-16, verbatim:

```text
❌ Error in workflow execution: start did not return within 14s
status_before={'a': 'completed', 'b': 'completed'}
workflow_status_after=running
status_after={'a': 'completed', 'b': 'completed'}
ledger_tools=[]
order=[]
```

### Part 6 - Where GraphBuilder sits

The claim in the short reply is narrow: the 0.8.11 workflow does not wire GraphBuilder into task output validation, which the A1 0-hits result supports. This is not a claim that GraphBuilder never validates anything. `graph.py` does contain `_validate_graph` / `_validate_node_executor` (lines 289, 491, 760), but those validate graph topology and node executors, not a task's output against a schema; the `model_` hits there are `executor._model_state`, not Pydantic models. I have not tested a GraphBuilder plus workflow combination, so I am not making a claim about one.

### Part 7 - Scope limits

This probe did not run a new Bedrock workflow. Part B parses the exact downstream prompt recorded by UC08, so the parsing result is reproducible without a model call. I have not run the Pydantic wrapper end to end inside `workflow`, so I will not call it a clean pattern yet. I have not benchmarked this, validated it in production, or measured a custom-Python replacement against the vended tool.

### Part 8 - Reproduce

After installing strands-agents 1.63.0, strands-agents-tools 0.8.11 and pydantic 2.14.2 in a venv:

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action
.venv/bin/python outreach/uc08-comments/probe_graphbuilder_pydantic.py
```

Three consecutive runs produced byte-identical stdout, matching `evidence/probe-output.txt` (sha256 `96c34a99d8efdf97f4e8baca38c8a01e43640d8283b3aad2ff852e430139e052`). No LLM call is needed to reproduce this probe.

Files:

- https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc08-comments
- https://github.com/pinxiong/strands-in-action/blob/master/outreach/uc08-comments/probe_graphbuilder_pydantic.py
- https://github.com/pinxiong/strands-in-action/blob/master/outreach/uc08-comments/evidence/probe-output.txt
- https://github.com/pinxiong/strands-in-action/tree/master/usecases/08-workflow/evidence

## Verification status (inherited, not repeated)

| Round | Agent | Scope | Result |
|---|---|---|---|
| 1 | `verifier-a` | facts / source / line-level, 11 required checks | `RESULT: PASS` |
| 1 | `verifier-b` | pasteability / wording / scope / length, 12 required checks | `RESULT: PASS` |
| 2 | `uc08-comment-final-verifier` | new independent agent, full re-check of the revised text, 12 items | `RESULT: PASS`, 12/12, 0 mandatory fixes |

A separate machine check re-verified all 12 `file:line` fact citations (`12/12`).
All evidence quoted above was part of those verification passes. The detailed
edition adds no new assertion, so it was not sent back for a fourth round.

## Notes for Pin

- The paste-ready file is plain text: no backticks, no fences, no bold, no Markdown link syntax. `BEGIN` / `END` markers replace fences so Builder Center does not reformat the code and output blocks.
- Probe source excerpts are dedented 4 spaces for display; the wording is unchanged. The complete file is in the repo.
- `probe-output.txt` line 5 contains a local venv absolute path and is omitted from the quoted stdout; no other line was changed.
- The recorded downstream prompt contains `<raw>` tags. They are verbatim evidence, not markup; if a comment field strips them, the linked file still carries the original.
- Pushed as commit(s) on 2026-11-17 alongside `reply-artem-tokarev-bc.txt` and `reply-artem-tokarev.md`. Do not auto-post; paste manually.
