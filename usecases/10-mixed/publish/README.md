# UC10 · Orchestrating Agents: Three Orchestrators, One Process

状态：**三渠道全部上线（主站 2026-11-21 10:51 GMT+8、Dev.to 10:55 GMT+8、Builder Center 21:5x GMT+8 补发）**。正文、9 组真实 Bedrock 实验、19 个逐字 SDK 源码块、三套深蓝封面与两件发布物料已落盘；三类独立评审全 PASS、门禁 17/17 + 全套检查全绿。BC 平台正文硬上限 40000 字符，原稿 44855 字符被表单校验拦下；按 Pin 口径只压缩冗余散文（不动任何源码块、数字、evidence、结论），BC 稿压到 39807 字符 / 正文 39354 字符后补发成功，线上正式 URL 200 + 标题正确 + og:image 目标封面三判据齐全。

> 按 Pin 2026-11-18 永久政策：**对外分发只发 Dev.to + Builder Center 两个渠道**，不再写 Medium 版本、不做 Import、不回填 `<MEDIUM_URL>`。主站是单一真相源与 canonical 目标，照常 push，不算对外分发版本。

| 渠道 | 线上地址 |
|---|---|
| 主站（canonical） | https://xiongpin.dev/posts/orchestrating-mixed/ — `draft: false`，线上 200，og:image 深蓝 `cover.png` 1400×788 |
| AWS Builder Center | https://builder.aws.com/content/3MOmWdircFuu4zPSVM8o66B7nkr/orchestrating-agents-three-orchestrators-one-process — 2026-11-21 21:5x GMT+8 补发上线，线上 200，og:image 深蓝 `cove.webp` 1400×788 |
| Dev.to | https://dev.to/aws-builders/orchestrating-agents-three-orchestrators-one-process-4agc — id `5085508`，2026-11-21 10:55 GMT+8 上线，组织 AWS Community Builders，canonical 指回主站 |

> Verified on 2026-11-20 against `strands-agents` 1.63.0,
> `strands-agents-tools` 0.8.11, Python 3.11 and Bedrock in `us-east-1`.
> The model is `amazon.nova-pro-v1:0`.
> Every number in the article came out of a run; raw output lives in `evidence/`.

A Graph, the vended Workflow tool and a Swarm run in one process on the same
brief fixture. They compose at the API level and do not compose at the data
level. A Graph hands a downstream node `str(NodeResult)` text; its condition
predicate can still read all seven structured fields. A Swarm keeps a real
`SharedContext` dictionary and the Workflow tool keeps `task_results` on disk,
but neither reaches the outer Graph as a structured field. A nested tool
failure leaves the outer Graph `completed`; only an agent-level exception makes
it fail and prune the branch. Mixing buys one capability, a Graph that schedules
a Swarm as a node, and costs 74.5% and 192.8% more tokens on this linear task.

## What the experiments show

| 组 | 脚本 | 问题 | 发现 |
|---|---|---|---|
| E1 | `src/e1_graph_baseline.py` | 纯 Graph 控制组 | `researcher / calculator / writer`，4829 tokens，6 次模型调用，10.179s |
| E2 | `src/e2_workflow_baseline.py` | 纯 Workflow 返回值形态 | 一个 `100.0%` 文本句；磁盘上每 task 有 status，返回值里没有，4767 tokens |
| E3 | `src/e3_swarm_baseline.py` | 纯 Swarm 接力与共享上下文 | 串行 handoff，`SharedContext` 有 `raw_counts` / `total`，8234 tokens |
| E4 | `src/e4_mixed_graph_swarm.py` | Swarm 能否直接作 Graph node | 能（`MultiAgentBase`），8428 tokens（含内层 4778），`SharedContext` 不进 `state.results` |
| E5 | `src/e5_mixed_graph_workflow.py` | Workflow 能否直接作 Graph node | 不能，须 `@tool` 包装；两套账本 9272 + 4867 = 14139，13 次调用 |
| E6 | `src/e6_context_bridge.py` | 字段级数据通道 | sentinel `SWARM-7Q2` 写入后两处都不可见；四类 crossing 只有 text 穿过 |
| E7 | `src/e7_failure_inner_swarm.py` | 内层失败在外层怎么标记 | 吞掉的 tool failure → 外层 `completed` 且 sink 照跑；agent-level exception → `failed` + 剪枝 |
| E8 | `src/e8_failure_workflow_condition.py` | predicate 能否判别内层失败 | 不能；`100.0%` 成功句里没有 error marker，predicate 求值 3 次未见 |
| E9 | `src/e9_cost_capability.py` | 成本与能力对照 | 聚合 E1–E5 真实运行 + 无模型调用的构造期 probe；混搭只加成本不加数据能力 |

## Files

- 正文：`article.md`（唯一真相源，四份稿件由它派生）
- 脚本：`src/common.py`、`src/e1_*.py` … `src/e9_*.py`、`src/gen_source_blocks.py`、`src/probe_api.py`
- 证据：`evidence/e{1..9}-*.txt` 与同名 `.json` 共 9 组，另 `evidence/source-blocks.md`（19 个逐字块）
- 渠道稿：`publish/devto.md`（一段一行）、`publish/orchestrating-mixed.md`（BC，裸 URL 无尖括号）、`content/posts/orchestrating-mixed.md`（主站）
- 封面：`static/images/orchestrating-mixed/` 三套 SVG + PNG（1400×788 / 1200×504 / 1400×788）
- 物料：`writing-lab/distribution/orchestrating-mixed-slack.md`（只列 BC / Dev.to 两条）

## Run order

`Try it yourself` 首屏给了完整仓库地址。九条命令一次一条执行；`src/common.py` 在
import 时为每个进程分配独立的 `STRANDS_WORKFLOW_DIR`，并在启动时清空共享工具
ledger，因此不要并行跑。E9 读 E1–E5 写下的证据文件，必须最后跑。
UC10 与 UC06–UC09 共用 `data/brief-input.json`，逐字节相同。
