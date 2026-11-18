# UC09 · Orchestrating Agents: Your Agent Leaves the Process

状态：**在制品 / 待发布** — 正文与 9 组真实证据已落盘，主站稿 `draft: true`；Medium 手册、Slack 文案、三套深蓝封面齐备。Medium 物料待手动 Import。

| 渠道 | 线上地址 |
|---|---|
| 主站（canonical） | https://xiongpin.dev/posts/orchestrating-a2a/ — 稿件 `content/posts/orchestrating-a2a.md`，发布时置 `draft: false` |
| AWS Builder Center | https://builder.aws.com/content/<BC_ID>/orchestrating-agents-your-agent-leaves-the-process — 占位，发布后回填 |
| Dev.to | https://dev.to/aws-builders/orchestrating-agents-your-agent-leaves-the-process-<SUFFIX> — 占位，发布后回填 |
| Medium | <MEDIUM_URL> — 待手动 Import（物料已齐：Medium 手册 + Slack 文案 + 1400×788 16:9 封面） |

> Verified on 2026-11-18 against `strands-agents` 1.63.0, `a2a-sdk` 0.3.26,
> `fastapi` 0.163.2, Python 3.11 and Bedrock in `us-east-1`.
> The model is `amazon.nova-pro-v1:0`.
> Every number in the article came out of a run; raw output lives in `evidence/`.

An `A2AServer` wraps the writer in one OS process and an `A2AAgent` calls it
from another. The card offers `text` as the only output mode. The executor builds
one artifact with `str(result)`, so a receipt id arrives as prose. A remote tool
that raises still produces `completed` and `end_turn`; an agent-level exception
produces `a2a_task_state = failed` while `stop_reason` stays `end_turn`. The
caller's `accumulated_usage` is zero for a run the server metered at 2369
tokens. A client timeout can leave the remote receipt already written.

## What the experiments show

| Script | Question | Finding |
|---|---|---|
| `src/probe_card.py` | What can the caller learn before spending tokens? | card `protocolVersion 0.3.0`, `JSONRPC`, 2 skills, `defaultOutputModes: ["text"]` |
| `src/probe_trace.py --mode happy` | What does a successful call return? | `end_turn`, `a2a_task_state=completed`, prose text, caller usage 0/0/0, one receipt in the server pid |
| `src/probe_trace.py --mode tool_raise` | Does a remote tool error change the state? | no: `completed` + `end_turn`, error rendered as a sentence, 0 receipts |
| `src/probe_trace.py --mode stream` | What does the event stream carry? | 58 events, 55 `working` status updates, 1 artifact, 1 `completed` |
| `src/probe_failure.py --mode agent_raise` | What does a real agent failure produce? | `a2a_task_state=failed`, but `stop_reason=end_turn`, text `Agent execution failed` |
| `src/probe_failure.py --mode timeout` | Can the write happen without the reply? | yes: `A2AClientTimeoutError` at 2s, receipt already on disk with the server pid |
| `src/probe_failure.py --mode readback` | Does a retry duplicate the write? | no: 2 calls with one key, `receipt_count=1` |
| `src/probe_cost.py` | Where does the token ledger go? | local 2313, remote 2369, caller 0; `executor.py` has 0 hits for usage/token/metric |
| `src/probe_swarm.py` | Do in-process orchestrators take a remote node? | Swarm rejects with `AttributeError`; GraphBuilder accepts construction only |

## Files

- 正文：`article.md`（唯一真相源，四份稿件由它派生）
- 脚本：`src/common.py`, `src/remote_server.py`, `src/probe_*.py`
- 证据：`evidence/a2a-*.txt` 与 `evidence/a2a-*.json`，9 组各一份
- 渠道稿：`publish/devto.md`（一段一行）、`publish/orchestrating-a2a.md`（BC，裸 URL 无尖括号）、`content/posts/orchestrating-a2a.md`（主站）
- 封面：`static/images/orchestrating-a2a/` 三套 SVG + PNG（1400×788 / 1200×504 / 1400×788）
- 物料：`writing-lab/distribution/orchestrating-a2a-medium-manual.md`、`orchestrating-a2a-slack.md`

## Run order

`Try it yourself` 首屏给了完整仓库地址。九条命令一次一条执行，每条自己起停服务端进程，
共享 `/tmp/uc09-a2a` 落盘目录，启动时会清空，因此不要并行跑。UC09 与 UC06–UC08 共用
`data/brief-input.json`，逐字节相同。
