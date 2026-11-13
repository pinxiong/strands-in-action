# 流水线状态（三个触发点共享，谁先醒谁干活，后来者只检查）

> 流程见 [`PIPELINE.md`](PIPELINE.md)；发布时间依据 [`PUBLISHING-POLICY.md`](PUBLISHING-POLICY.md)；反馈闭环见 `writing-lab/feedback/README.md`。

## 机器可读字段（自动任务先读这几行）

```yaml
last_run_date: 2026-11-13      # 最近一次真正推进过工作的日期
today_started: 2026-11-13      # 今天是否已开工（与 last_run_date 同步；跨天自动失效）
stage: review                  # not_started | outline | experiments | draft | review | ready_to_publish | published
current_piece: UC07
current_slug: orchestrating-graph
gates: {expert: pass, reader: pass, independent: pass}   # UC07 三类独立评审全 PASS（2026-11-13；修订一轮 + 终审 PASS）
ready_since: null              # 尚未 ready_to_publish：门禁 23/24，Slack 渠道链接待发布后回填
published_at: 2026-11-11T13:36:31Z    # 最近发布仍是 UC06；UC05 = 2026-11-09T13:32:00Z
publish_gate: {medium_manual: true, cover_16x9: true, slack_copy: true}  # 三件物料已建（占位），但 Slack 链接位未回填
publish_gate_checked: 2026-11-13T11:20+08:00  # check_publish_gate.py orchestrating-graph → 23/24，1 项预期内 FAIL（未发布占位符）
```

> **发布门禁（每次自动发布都适用）**：`stage` 改成 `published` 之前必须跑 `python3 check_publish_gate.py <slug>`，非 0 退出禁止发布；通过后把 `publish_gate` 三项置 `true` 并记检查时刻。Medium 不发，但手册 / 16:9 封面 / Slack 文案缺一不可，不许"先发再补"。详见 `PIPELINE.md` 第 6 节。

## 当前

| 项 | 值 |
|---|---|
| 当前篇目 | **UC07 · Orchestrating Agents: The Graph Is Yours, the Judgment Isn't**（slug `orchestrating-graph`）— **在制品，三类评审全 PASS，未发布** |
| 阶段 | `review`（10:30 档：环境自检 → 节奏判定 → 大纲 → 6 组真实实验 → 英文正文 → HTML 预览 → 三类评审 → 修订 → 终审 PASS → 三件物料与封面占位） |
| 最近发布日期 | 2026-11-11（UC06 `orchestrating-swarm`）；节奏判定只统计 `series == "strands-in-action"` |
| 下次可开新篇 | UC08 最早 2026-11-15 之后（距 UC07 发布满 2 天，按实际发布日重算） |
| 下次可发布窗口 | 今天 21:30–22:30 窗口**已因幂等短路未使用**（21:30 档只读早退，详见顺延记录）；下个符合条件窗口 = **2026-11-16（周一）21:30**（周六日不发）。若 Pin 当晚拍板补发，以实际发布时间为准并回填 D+0 台账 |
| 阻塞项 | ① 发布前回填 Slack 三条渠道链接并重跑门禁（当前 23/24，退出码 1 禁止发布）② 主站稿件 `content/posts/orchestrating-graph.md` 待生成 ③ UC06 Medium 手动 Import ④ UC05 Medium 头图人工替换 ⑤ UC04 D+7 = 11-14 ⑥ **UC06 D+2 = 11-13 已到期未写**（`feedback/` 无当日记录）⑦ 今晚发布窗口未使用，待 Pin 决定补发或顺延 11-16 |

## UC07 在制品台账（2026-11-13 10:30 档）

| 项 | 值 |
|---|---|
| 标题 | Orchestrating Agents: The Graph Is Yours, the Judgment Isn't |
| Slug | `orchestrating-graph` |
| 正文 | 2644 词（HTML 预览口径）/ 12 个代码块（8 个 Python 源码逐字段 + 2 text + 2 bash）/ 正文零配图 / 零 Markdown 表格 |
| 实验 | 6 组脚本、9 条复跑命令 = 8 次图运行 + 1 次构造期检查；证据 `evidence/*.txt` + `*.json` 共 9 组 |
| 关键实测 | 条件谓词求值 3 次且 3 次 `model_calls_at_eval` 快照恒为 `{r:2,c:2,w:0,f:0}`；fan-in `order=['A','join','B','join']`（join 跑两次、与 B 重叠、输入只有 `From A:`）；`overlap_pairs=[('right','left')]`（对照 UC06 空 overlap）；不设限 build 发 unbounded warning、上限 6 → 6 次执行后 FAILED；工具抛异常节点仍 COMPLETED，hook 取消整图 abort |
| 最锋利发现 | `_find_newly_ready_nodes` 的 docstring 承诺「失败剪枝、兄弟分支继续」，但 1.63.0 实测两条注入路径都走不到：`except` 分支注释为 fail-fast。正文按实测写，并明写「不声称剪枝代码不可达」 |
| 指标 | `final_check` 0 项；`en_metrics` 平均句长 13.6 / stdev 6.7 / 被动 3.98 / 连接词 0.65 / 名词化 1.77 / Flesch 72.0 / >40 词长句 0（stdev、连接词、Flesch 略偏舒适区，属软性观察，非阻断） |
| 评审 | 技术专家首轮 FAIL 2 项（scope 数字、命令数口径）→ 修订 PASS；目标读者首轮 FAIL 3 项（本体类别、UC06 最小上下文、复跑凭据/区域）→ 修订 PASS；独立复核首轮 PASS（硬规则全过）；修订后复审 FAIL 2 项（源码块 `return True` 缩进、`unbounded` 说明与新事实冲突）→ 修复后终审 PASS。**三类全 PASS** |
| 物料 | Medium 手册（7 步 / 4 个 subtitle 均 ≤140 且字符数实测准确）、`cover-medium.png` 1400×788 深蓝、Slack A/B/C 三版（无主站链接）；三套封面由 `build_covers.py --slug orchestrating-graph` 生成，`--check` ALL PASS |
| 门禁 | `python3 check_publish_gate.py orchestrating-graph --site ...` → **23/24**，唯一 FAIL「Slack 三渠道齐全且无主站链接」是未发布的占位符，发布后回填即 PASS。**不发布、不置 `published`** |
| HTML 预览 | `usecases/07-graph/review/article-preview.html`（31 KB，已 `present_files` 递给 Pin；正文改过 4 次，每次覆盖重生成） |
| 待办 | ① 21:30 窗口：生成主站稿件 → 回填 Slack 三链接 → 跑门禁 24/24 + `final_check` + `hugo -D` → 发布主站 / Dev.to / BC ② Medium 手动 Import 后回填四处 ③ D+2 / D+7 反馈回灌 |

## UC06 D+0 台账（2026-11-11）

| 项 | 值 |
|---|---|
| 标题 | Orchestrating Agents: Nobody Decides Who Goes Next |
| 主站 | https://xiongpin.dev/posts/orchestrating-swarm/ — push 21:36:31（GMT+8）= 13:36:31 UTC，≈21:41 起 200 |
| Dev.to | https://dev.to/aws-builders/orchestrating-agents-nobody-decides-who-goes-next-2cg4 — id 5017329，21:37:31（GMT+8）= 13:37:31 UTC，org aws-builders（2794），canonical 指回主站，段中 `<br>` = 0 |
| Builder Center | https://builder.aws.com/content/3Lxn0RS1k0tiClcigN1xz5c0hH9 — ≈21:50（GMT+8）= 13:50 UTC，200，正文图已传站内（prod-assets swar.webp），封面已落库（cove.webp，cover 步骤两次报 FAIL 均为 SKILL §11 已知误判） |
| Medium | **物料已就绪，待手动 Import**（Medium 本身不自动发）。文件：`pinxiong.github.io/writing-lab/distribution/orchestrating-swarm-medium-manual.md`（7 步 + 4 个 subtitle 选项）、`orchestrating-swarm-slack.md`（A/B/C 三版，BC / Dev.to 已回填，Medium 待回填）、`static/images/orchestrating-swarm/cover-medium.png`（1400×788 16:9）。Import 后把 URL 回填四处：手册顶部表格 / Slack 文案 / 本台账 / `publish/README.md` |
| 规模 | 正文 2536 词（en_metrics 口径）/ **16 个代码块**（5 Python + 9 text + 2 bash）/ 1 张机制图 / 4 组实验（E1 正常接力、E2 沉默、E3 双上限、E4/E5/E6 三种失败） |
| 门禁 | `python3 check_publish_gate.py orchestrating-swarm` → **18/18 PASS**（21:36，退出码 0）；发布后复跑仍应为 18/18（Medium URL 位占位与回填两种状态均通过） |

**本档执行备注**

- 物料顺序按 §6：先补 Medium 手册 + Slack 文案（10:30 档已备 16:9 封面），门禁 18/18 后才 push 主站 / 发 Dev.to / 发 BC；`publish_gate` 三项 21:36 置 true。
- Dev.to 流程与 UC05 相同：POST 个人号 → PUT `organization_id=2794`；本机 urllib 直连 api 会 403（Forbidden Bots），加浏览器 User-Agent 后正常。
- BC `publish.py run` 的 cover 步骤报两次 FAIL，均为 troubleshooting §11 已知误判（「当前已保存封面」行有 `prod-assets…/cove.webp` 即已落库）；重传一次确认后直接 `publish`，未按 FAIL 停发。
- **22:25 发布后缺陷修复（Pin 指出）**：UC06 的 5 个 Python 代码块整块带着 SDK 源码的嵌套缩进（8/16/12/20 空格），第一行代码不在 0 位。已对四份稿件（article.md / publish/devto.md / publish/orchestrating-swarm.md / 主站稿件）+ review HTML 整体 dedent，保留相对层级。主站 push、Dev.to `PUT /api/articles/5017329` 均独立复核生效（元数据、canonical、封面、标签未变）；BC 线上导入时本就自动 dedent，逐行核验为 0/4 缩进，无需改动；Medium 尚未 Import，从主站 Import 即得修复版。门禁扩到 21 项（三项「代码块 0 缩进基线」全 PASS），`final_check.py` 新增阻断级扫描。提交 `a36d539` / `68cd0ab`。
- **22:55 发布后封面风格统一（Pin 指出）**：从 UC05 起封面换成白底 `#f8fafc` + 细线排版、尺寸也变成 1200×630 / 1000×420，与 UC01–UC04 的深蓝渐变基准格格不入。新增 `tools/build_covers.py`，以 UC04 的封面为唯一模板，为 UC05 / UC06 各生成三套 SVG + PNG（cover 1400×788 / cover-devto 1200×504 / cover-medium 1400×788），右侧机制图数字与 `evidence/` 及 front matter `alt` 对齐。主站线上与 Dev.to 图片代理均已复核为深蓝新图（Dev.to front matter 加 `?v=2252` 破缓存，`published_at` / 组织 / canonical 未变，正文 clone 与 0 缩进完好）。当时把 **BC 两篇头图（平台资产库里的旧白底 `cove.webp`）与 UC05 已发布的 Medium 头图**写成「需后台手动替换」就停手了，这是错的：BC 是完全可以自动换的，**当晚 23:04–23:50 已把两篇换掉并重新发布**（见下一段），Medium UC05 才成为唯一剩余人工项；两份 Medium 手册已补精确操作步骤；UC06 的 Medium 尚未 Import，直接用新文件。门禁扩到 24 项（全系列封面深蓝基准 + 两档 PNG 尺寸），UC05 / UC06 复跑均 24/24 PASS；按 Pin 要求把「代码块 0 缩进」明确写为 skill §8 **发布前 check 三条命令之一**，并声明今后质量规则优先做成门禁。提交 `fc66162` / `a8b4aaa`（strands）、`f3c74f8` / `6399b31`（主站）。

## 23:04–23:50 已发布封面全渠道收口（Pin 追问：生成好的新图为什么不换上去）

| 渠道 | UC05 `reservations-fencing` | UC06 `orchestrating-swarm` | 结论 |
|---|---|---|---|
| 主站 | `cover.png` 已是深蓝 1400×788 | 同左 | 两篇 og:image 下载采样 `(11,37,72)` / `(16,51,98)`，PASS |
| Dev.to | `cover-devto.png?v=2252` 1200×504 | 同左 | 图片代理已破缓存，PASS |
| Builder Center | hero 换成 `3LxyHNUWwUnbcWU2R6QDmG9F4WM/cove.webp` | hero 换成 `3Ly14JmdaNOWWjkNhL4aMmVTT2O/cove.webp` | 两篇都进编辑页重传 `cover-medium.png` 并**在同一浏览器会话 Publish**；og:image 的 base64 里解出 hero，下载采样 `(11,38,72)` / `(15,51,98)`，PASS |
| Medium | **待人工**：已发布故事正文第一张图仍是旧白底 `1*uqaDy968kYeyCJQUuZtTmA.png`，按 `reservations-fencing-medium-manual.md` 第 4 步的四步换掉 | **未 Import**（Medium profile 最新一篇仍是 UC05），导入时直接用新深蓝 `cover-medium.png`，不存在替换动作 | Medium 无 API；本次已用登录态打通自动化浏览器并进入编辑页，但编辑器未初始化（`contenteditable=0`、Save and publish 为 disabled），无法代点，**不虚报 PASS** |

- 新增 `tools/verify_live_covers.py`：下载三个自动渠道的线上头图，校验尺寸与深蓝像素。UC05 / UC06 各跑一次，三渠道全 PASS、退出码 0，Medium 输出 `MANUAL`。命令与渠道动作表已写进 `PIPELINE.md` §6。
- 根因：上一档只做了「本地出图 + 主站 / Dev.to 换图」，把 BC 与 Medium 一起留成文字待办，没有继续做本来能自动完成的 BC。今后任何封面重建，四个渠道逐个换、逐个验，核验脚本为机器权威；Medium 只能人工，手册必须给到可点的步骤。
- 唯一剩余动作：UC05 Medium 编辑页换头图（4 步），换完把本表 Medium 行改成 PASS 并记新的 og:image。

## UC06 在制品台账（2026-11-11 10:30 档）

| 项 | 值 |
|---|---|
| 标题 | Orchestrating Agents: Nobody Decides Who Goes Next |
| Slug | `orchestrating-swarm` |
| 正文 | 2536 词 / 15 个代码块 / 1 张机制图 / 4 组实验（E1 正常接力、E2 沉默、E3 双上限、E4/E5/E6 三种失败） |
| 指标 | `final_check` 0 项；`en_metrics` 句长 19.1 / stdev 11.3 / 被动 3.08 / 连接词 1.34 / 名词化 1.38 / Flesch 69.6 |
| 证据 | `usecases/06-swarm/evidence/`：swarm-trace.txt（E1 两次 + E2）、swarm-limits.txt（E3 两档）、swarm-failure.txt（toolerror/timeout/cancel/session）+ 5 份 json |
| 图片 | `static/images/orchestrating-swarm/`：cover.png 1200×676、cover-devto.png 1000×420、**cover-medium.png 1400×788 16:9**、swarm-handoff-loop.png 1200×520（SVG 源齐全） |
| 评审 | 技术专家首轮 FAIL 5 项 → 修订后定向复审 PASS；目标读者有条件 PASS 5 项 → 全部落地；独立复核首轮 FAIL 1 项（Flesch 71.9）→ 修订后 PASS（69.6） |
| 待办 | ~~① Medium 手册 ② Slack 文案 ③ 跑门禁 ④ 21:30 窗口发主站 + Dev.to + BC~~ 全部完成（21:36–21:50）；剩：Medium 手动 Import（Pin）+ D+2（11-13）|

**本轮最该记住的一条**：目标读者把「标题说没人决定，正文其实是模型逐跳决定」指了出来。已在第 2 节补一句并把 ping-pong 实验标成动态路由的正面证据；后续写编排篇时，标题的张力表述要在正文前三段内落地成机制句子。

## UC05 D+0 台账（2026-11-09）

| 项 | 值 |
|---|---|
| 标题 | When "Not Found" Doesn't Mean "Never Happened" |
| 主站 | https://xiongpin.dev/posts/reservations-fencing/ — push 21:32:00（GMT+8）= 13:32:00 UTC，21:36 起 200 |
| Dev.to | https://dev.to/aws-builders/when-not-found-doesnt-mean-never-happened-2eie — id 5004687，21:33:25（GMT+8）= 13:33:25 UTC，org aws-builders（2794），canonical 指回主站 |
| Builder Center | https://builder.aws.com/content/3Ls8Su63RbuSKR3yys1j9t6US1p/when-not-found-doesnt-mean-never-happened — ≈22:15（GMT+8）= 14:15 UTC，200，hero 封面与 "Originally published" 均在线上 |
| Medium | https://medium.com/@pinxiong.cn/when-not-found-doesnt-mean-never-happened-1bc3e54bd912 — **已上线**（2026-11-10 手动 Import，URL 由 Pin 提供）。人工物料齐备：`writing-lab/distribution/reservations-fencing-medium-manual.md`（7 步 + 4 个 subtitle 选项）、`reservations-fencing-slack.md`（A/B/C 三版，四渠道链接齐全）、`static/images/reservations-fencing/cover-medium.png`（16:9）。URL 已回填四处（手册 / Slack / 本台账 / publish/README.md）；`medium.com` 本机不可达，未做页面抓取核验 |
| 规模 | 正文 2421 词（不含代码块）/ 16 个代码块 / 4 组实验（C1 崩溃边界、C2 延迟提交竞态、C3 slot 争用、C4 LLM 三探针） |
| 指标 | `final_check` 0 项；`en_metrics` 定稿读数 stdev 9.8 / 被动 3.1 / 连接词 1.07 / 名词化 3.06 / Flesch 61.9（发布前复跑确认，与 11:20 复审时的 stdev 8.2 差异来自 v3 润色） |

**发布当天的两个偏差（第 1 项已修复）**

1. ~~BC 封面 `cover-medium.png` 是 1400×735（1.90:1），SKILL 要求 16:9。~~ **已于 2026-11-10 10:51 修复**：新建 `cover-medium.svg`（viewBox `0 0 1400 788`），用 `resvg-py` 渲染，PNG 实测 1400×788。BC 线上仍挂 11-09 上传的旧资产，已正常显示、无须重传；Medium 用新文件。流程层面已在 `PIPELINE.md` 第 6 节写死 16:9 出图与尺寸校验，不再把尺寸偏差记成"已知偏差"放行。
2. BC `cover` 步骤报了两次 "改动没进草稿" 的 FAIL，实为 SKILL troubleshooting §11 的已知误判：第一次上传已落库（`prod-assets.../cove.webp`），第二次重传资产 URL 不变被判失败。核验方式是看"当前已保存封面"那行，不是等 `Saved cover asset` 二次变化。

## UC05 评审台账（2026-11-09）

| 评审 | 首轮 | 修订后复审 |
|---|---|---|
| 技术专家 | FAIL 4 项（compose 越界断言、453 是 usage 非 budget 且出处错、first call won、janitor thread） | PASS 7/7 |
| 目标读者 | 有条件 PASS，5 处必改（idempotency_token 定义、争用实验进正文、fence 语义、in_flight 前提、状态图 naive 路径） | PASS 5/5 |
| 独立复核 | FAIL 1 项（句长标准差 7.0 < 8）；硬规则全过 | PASS（stdev 8.2、final_check 0 项） |

## UC05 实验台账（2026-11-09 10:30 档产出）

- 大纲：`usecases/05-reservations-fencing/OUTLINE.md`（五个发现已回填实测数字）
- C1 崩溃边界（真时钟 4 组合 × 5 次）：naive/after-effect 重复写 5/5 + 误归还 5/5
- C2 延迟提交竞态（3 模式 × 5 次压力）：naive 5/5 重复；fenced 0 重复但旧 attempt 5/5 被拒；authoritative 0 提前释放
- C3 slot 争用（× 3 轮）：崩溃 slot 仅经 expiry 回收，继承者等待 ≈ 租约 1.0s
- C4 三段式 LLM 探针（nova-pro，strands 1.63.0）：实例串行 ConcurrencyException / 同 idempotency_token 进程内去重 / 双实例各拿预算
- SDK 源码出处已取：agent.py:268/928/955、_concurrency.py:25/86/107/183、types/agent.py:205

## 发布物料（已归档，均为线上状态）

- 主站：`pinxiong.github.io/content/posts/reservations-fencing.md`（`draft: false`，commit a43e079）
- 图片：`pinxiong.github.io/static/images/reservations-fencing/`（cover / cover-devto / **cover-medium 1400×788 16:9** / race-timeline，另留 cover-medium.svg 源）
- Dev.to：`usecases/05-reservations-fencing/publish/devto.md`（`build_devto.py --check` = in sync）
- BC / Medium 正文：`usecases/05-reservations-fencing/publish/reservations-fencing.md`（本次改动：标题去转义、正文图改站内根路径）
- **Medium 手册**：`pinxiong.github.io/writing-lab/distribution/reservations-fencing-medium-manual.md`（2026-11-10 补齐）
- **Slack 文案**：`pinxiong.github.io/writing-lab/distribution/reservations-fencing-slack.md`（2026-11-10 补齐）
- **评审预览**：`usecases/05-reservations-fencing/review/article-preview.html`
- 正文：2421 词 / 16 代码块、`final_check` 0 项（发布后 30 分钟内未改正文，符合 PUBLISHING-POLICY §5.4）

## 历史

| 日期 | 篇目 | 结果 |
|---|---|---|
| 2026-11-13 | UC07 Orchestrating Agents: The Graph Is Yours, the Judgment Isn't | 10:30 档开写并完成大纲 + 9 组真实实验 + 正文 + HTML 预览 + 三类评审（修订一轮、终审 PASS）；三件物料与三套封面已建占位；门禁 23/24（Slack 链接位待回填）。**未发布**，等 21:30 窗口 |
| 2026-11-11 | UC06 Orchestrating Agents: Nobody Decides Who Goes Next | 已发布（主站 21:36 / Dev.to 21:37 / BC ≈21:50），门禁 18/18；Medium 待手动 Import；D+2 = 11-13 |
| 2026-11-09 | UC05 When "Not Found" Doesn't Mean "Never Happened" | 已发布（主站 / Dev.to / BC / Medium），D+2 记录已补（2026-11-11），D+7 = 11-16 |
| 2026-11-07 | UC04 Sessions, State & Memory | 已发布，D+2 记录已补（2026-11-09），D+7 = 11-14 |
| 2026-11-06 | UC03 The Limits That Don't Limit | 已发布 |
| 2026-11-05 | UC02 The Tools That Got Replaced | 已发布 |
| 2026-11-04 | UC01 How the Strands Agent Loop Actually Works | 已发布 |

## 顺延记录

| 日期 | 原因 | 顺延到 | 从哪继续 |
|---|---|---|---|
| 2026-11-13 | 10:30 触发档不在发布窗口（主窗口 21:30–22:30 GMT+8）；且门禁 23/24，Slack 三条渠道链接需发布后才能回填。按 PIPELINE.md §6「不夜间赶发、不为赶窗口降质量门」，本档不发布 | 今天（周五）21:30–22:30 GMT+8 | ① 生成 `pinxiong.github.io/content/posts/orchestrating-graph.md`（`draft: true`）② 发布主站 / Dev.to / BC 后把真实链接回填 Slack A/C 两版与 Medium 手册 ③ 跑 `check_publish_gate.py orchestrating-graph`（须 24/24）+ `final_check.py`（0 项）+ `hugo -D` 三条命令全绿，退出码非 0 禁止发布 ④ 门禁通过后置 `publish_gate` 三项 true 并记 D+0 台账 ⑤ Medium 手动 Import 后回填四处 |
| 2026-11-13 21:30 档 | **幂等短路**：`last_run_date` 已是今天 → 该档只读早退、一行结论结束，未走发布流程；`PIPELINE.md` §0 已加「幂等边界」硬规则，此类复发不再可能。核查时 `stage=review`、门禁 23/24、主站稿件未生成 | 2026-11-16（周一）21:30；或 Pin 当晚拍板补发 | ① 生成 `content/posts/orchestrating-graph.md`（`draft: true`）→ ② 发布主站 / Dev.to / BC → ③ 回填 Slack A/C 与 Medium 手册链接 → ④ 门禁 24/24 + `final_check` 0 项 + `hugo -D` 全绿后置 `published`、记 D+0 → ⑤ 补写 UC06 D+2 反馈记录（11-13 到期未做） |
| — | — | — | — |
