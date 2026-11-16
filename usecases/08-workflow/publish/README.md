# UC08 · Orchestrating Agents: Less Freedom for the Model, More Certainty for You

状态：**在制品** — 正文、9 组实验、HTML 预览、三类独立评审与发布物料已就绪，待 2026-11-16（周一）21:30–22:30 GMT+8 窗口上线。

| 渠道 | 线上地址 |
|---|---|
| 主站（canonical） | https://xiongpin.dev/posts/orchestrating-workflow/ （发布后生效） |
| AWS Builder Center | `<BC_URL>` — 发布后回填 |
| Dev.to | `<DEVTO_URL>` — 发布后回填 |
| Medium | <MEDIUM_URL> — 待手动 Import（物料已齐：Medium 手册 + Slack 文案 + 1400×788 16:9 封面） |

> Verified on 2026-11-16 against `strands-agents` 1.63.0,
> `strands-agents-tools` 0.8.11, Python 3.11 and Bedrock in `us-east-1`.
> The model is `amazon.nova-pro-v1:0`.
> Every number in the article came out of a run; raw output lives in `evidence/`.

A `workflow` is a list of tasks plus a `dependencies` array. A step runs when every
dependency is `completed`, and that check is a plain Python loop, not a model decision.
Independent steps really overlap in wall-clock time. But the certainty stops at scheduling:
upstream results are spliced into the next prompt as natural-language text, with no schema,
no validator and no idempotency key. A tool exception can be reported as 100 percent
success; a real model error parks the workflow in `running` forever; the documented
`Start or resume` cannot resume; a declared `timeout` is never read; and the only cost
accounting is a human-readable metrics string.

## What the experiments show

| Script | Question | Finding |
|---|---|---|
| `src/wf_trace.py --mode linear` | Is the declared order real? | `order=['research','calc','write']`, `overlaps=[]` |
| `src/wf_trace.py --mode parallel` | Do independent steps really run together? | Three overlapping pairs, same start timestamp, 6.66s instead of nine |
| `src/wf_contract.py --mode schema` | Does `create` validate an output schema? | No: `output_schema` / `returns` / `expects` / `validator` are persisted and never read |
| `src/wf_contract.py --mode passthrough` | What crosses the step boundary? | Rendered text, including `<thinking>` blocks and Markdown fences |
| `src/wf_failure.py --mode swallowed` | Is an injected failure a failed step? | No: `flaky` ends `completed`, `start` reports 2/2 succeeded - 100.0% |
| `src/wf_failure.py --mode real` | What does a real model error do? | `bad=error`, `down=pending` forever, state stays `running` (18s guard) |
| `src/wf_replay.py --mode manual` | Can editing the state JSON reset a step? | No: singleton memory copy overwrites the file, `save_draft` still called once |
| `src/wf_restart.py --phase create/start/restart` | Does `Start or resume` hold across processes? | No: a third process spins 14s with `order=[]` and 0 steps rerun |
| `src/wf_limits.py --mode timeout` | Is per-task `timeout` enforced? | No: `timeout=1` ran 7.06s and `completed`; `pause` / `resume` are not implemented |
| `src/wf_limits.py --mode ledger` | Where is the budget checkpoint? | Nowhere: 1182 + 1325 + 1437 = 3944 tokens in plain text, no `total_tokens`, no `budget` |

## Reproduce

```bash
git clone https://github.com/pinxiong/strands-in-action.git
cd strands-in-action/usecases/08-workflow
python3 -m venv .venv && . .venv/bin/activate
pip install strands-agents==1.63.0 strands-agents-tools==0.8.11 boto3
export AWS_DEFAULT_REGION=us-east-1
.venv/bin/python src/wf_trace.py --mode linear
```

The full nine-run command list and the three cross-process restart phases are at the end
of the article (`Try it yourself`). All runs need Bedrock access to `amazon.nova-pro-v1:0`
in `us-east-1`. Three runs deliberately never terminate (`wf_failure.py --mode real`,
`wf_replay.py --mode manual` on its second `start`, `wf_restart.py --phase restart`);
the scripts guard them with a wall-clock alarm and record the hang. Do not run those
without the guard.

## Scope

One process per run, two or three tasks, one model, short prompts that finish in seconds.
The fixture `data/brief-input.json` is byte-for-byte the UC06 and UC07 file; its `3640`
is a fictional input figure, not a measurement. This is a bench for inspecting a
mechanism, not a sample of production traffic. Not covered: concurrent writes, a crash
between the side effect and the state write, or a real store's deduplication semantics.
