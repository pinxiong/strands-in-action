# BC comment reply · Artem Tokarev · UC08 (2026-11-16)

Comment id `3MBVsKFgl5QdXTvcZ4QmNEGXh6C`, posted 2026-11-16T10:15:52+00:00 on
https://builder.aws.com/content/3MBSAPbU1zpRZTXGz7LfqJ22Jst/orchestrating-agents-less-freedom-for-the-model-more-certainty-for-you

> Since `workflow` passes raw text without schema validation or replay support, how do you see it fitting alongside Strands' native `GraphBuilder` (or `structured_output`) in production? Is there a clean pattern to wrap `workflow` tasks with Pydantic validation and external state, or would you recommend skipping the vended `workflow` tool altogether in favor of custom Python orchestration?

Deliverable: `reply-artem-tokarev-bc.txt` (plain text, no backticks or fences, ready to paste on Builder Center). Do not auto-post.

Detailed edition assembled 2026-11-17 from the same already-verified material, with
probe code, raw stdout and verbatim UC08 evidence lines: paste-ready
`reply-artem-tokarev-detailed-bc.txt` and reading/archive copy
`reply-artem-tokarev-detailed.md`. Its first three paragraphs are byte-for-byte
the verified short reply; no new experiment or verification was run.

## Reply

Hi Artem, good question. Short answer: they are different layers. structured_output is Agent-level; workflow 0.8.11 just calls task_agent(task_prompt) and hands the next step a rendered string. workflow.py has no structured_output, BaseModel, pydantic or validator identifier, and the output_schema, returns, expects and validator keys I declared were stored but never read. GraphBuilder gives topology and state, but the 0.8.11 workflow does not wire it into task output validation.

A Pydantic wrapper is doable, but you own the parsing and the failure path: my probe had to extract the JSON from that rendered prompt first, and UC08 measured a tool exception still reported as 100% success. State is an in-process singleton, so a hand-edited file gets overwritten and a restart in a new process replays zero steps.

For production work needing contracts or replay, I would orchestrate in my own Python (or GraphBuilder plus my own validator and store), use structured_output on an Agent I control, and treat the vended workflow as a scheduling prototype. I have not run that wrapper end to end, so I will not call it clean yet. Probe and raw output: https://github.com/pinxiong/strands-in-action/tree/master/outreach/uc08-comments

## Fact sources

| Claim in reply | Source |
|---|---|
| `structured_output` is Agent-level, signature `(self, output_model, prompt=None)` | `evidence/probe-output.txt` A2, `strands.Agent.structured_output` |
| workflow 0.8.11 calls `task_agent(task_prompt)`; context appended as `Results from {dep_id}:\n` | `evidence/probe-output.txt` A2 (workflow.py:425, :444) |
| workflow.py has 0 hits for structured_output / GraphBuilder / BaseModel / pydantic / output_schema / validator | `evidence/probe-output.txt` A1 |
| multiagent package has 0 hits for structured_output / BaseModel / model_validate / pydantic / output_schema | `evidence/probe-output.txt` A3 |
| `output_schema`, `returns`, `expects`, `validator` persisted and never read | `usecases/08-workflow/evidence/wf-contract-schema.txt` lines 30-33 |
| downstream receives a rendered natural-language string | `usecases/08-workflow/evidence/wf-contract-passthrough.txt` lines 31-37 |
| `json.loads` on the whole rendered prompt fails; extracting the embedded object then Pydantic validating succeeds; wrong type gives `int_parsing` | `evidence/probe-output.txt` B1 / B2 / B3 |
| a tool exception was reported as 100% success | `usecases/08-workflow/evidence/wf-failure-swallowed.txt:25` (`🎉 Workflow 'wf-failure-swallowed' completed successfully! (2/2 tasks succeeded - 100.0%)`); also `article.md:32`, `article.md:426` |
| singleton store overwrites a hand-edited state file | `usecases/08-workflow/evidence/wf-replay-manual.txt` (`patched_status_seen_by_start={'calc': 'completed', 'write': 'pending'}` but `result_after_second` unchanged, `save_draft_calls_total=1`); worded in `article.md:430` |
| restart in a new process replays zero steps | `usecases/08-workflow/evidence/wf-restart-restart.txt` (`status_before={'a': 'completed', 'b': 'completed'}`, `order=[]`, `start did not return within 14s`); `article.md:542` |

## Verification

- Round 1, two independent read-only agents with no shared context: `verifier-a` (facts / source / line-level, 11 required checks) → `RESULT: PASS`; `verifier-b` (pasteability / wording / scope / length, 12 required checks) → `RESULT: PASS`. verifier-a re-grepped `workflow.py` and `strands/multiagent/` itself instead of trusting the probe output file, and verified all `file:line` citations.
- Adopted from round 1: wording tightened for Pin's "简洁明了一点" request; "symbol" → "identifier"; the GraphBuilder design assertion replaced by the verifier-proposed source-anchored sentence "the 0.8.11 workflow does not wire it into task output validation"; probe reproducibility note added (3 byte-identical runs, sha256 `96c34a99…`).
- Round 2, a **new** independent final verifier doing a full re-check of the revised text (not just the delta): `RESULT: PASS`, 12/12 items, 0 mandatory fixes. It re-grepped `workflow.py` itself (GraphBuilder / structured_output / pydantic / BaseModel / validator / output_schema / model_validate / returns / expects all 0 hits), checked `graph.py:491-503`, `:760-770`, `:289-309` to confirm those are topology checks rather than output-schema validation, and verified byte-for-byte identity between the paste-ready text and the archived Reply section.
- Final: 185 words, 10 sentences, 3 paragraphs, 1233 chars, no Markdown syntax in the paste-ready version. Pushed as `8f01213` (and the verification note as a follow-up commit); the `tree/master/outreach/uc08-comments` link and all four blob links return 200.

## Scope limits

- This probe did **not** run a new Bedrock workflow. Part B parses the exact downstream prompt recorded by UC08 (`wf-contract-passthrough.txt`), so the parsing result is reproducible without a model call.
- The reply explicitly says the Pydantic wrapper was not run end to end inside `workflow`. It does not claim a production-ready integration, a benchmark, or that `GraphBuilder` cannot be combined with `workflow`.
- "the 0.8.11 workflow does not wire it into task output validation" is anchored to the A1 0-hits result and to `workflow.py` containing no `GraphBuilder` reference, rather than to a claim that `GraphBuilder` never validates anything. `graph.py` does contain `_validate_graph` / `_validate_node_executor` (lines 289, 491, 760), but those validate graph topology and node executors, not a task's output against a schema; the `model_` hits there are `executor._model_state`, not Pydantic models. This replacement was proposed by the independent verifier and adopted.
- "no ... identifier" replaces the earlier "no ... symbol" so the 0-hits claim is about source identifiers, not about runtime behaviour. Note `workflow.py` docstrings do contain the English word "validation" (lines 12, 25, 936, 941), but those describe dependency resolution and tool filtering, not output-schema validation; the probe's 0-hits result is specifically for `structured_output`, `GraphBuilder`, `BaseModel`, `pydantic`, `output_schema`, `validator`.
- The reply keeps "replays zero steps" without adding "and busy-loops"; `wf-restart-restart.txt:1,7,11,16` supports both, so the shorter phrasing is not an overstatement.
- Reply length was tightened to meet Pin's "简洁明了一点" request. Every factual assertion from the first draft was kept; only redundant words were removed.

Run:

```bash
cd strands-in-action
.venv/bin/python outreach/uc08-comments/probe_graphbuilder_pydantic.py
```

Reproducibility: three consecutive runs produced byte-identical stdout, matching
`evidence/probe-output.txt` (sha256 `96c34a99d8efdf97f4e8baca38c8a01e43640d8283b3aad2ff852e430139e052`).
No LLM call is needed to reproduce this probe.
