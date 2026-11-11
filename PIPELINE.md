# 文章流水线执行手册（自动任务的唯一真相源）

> 三个定时触发点（10:30 / 14:30 / 21:30 GMT+8）都只是**触发器**；真正的流程写在这里。
> 改流程改这个文件，不要去改定时任务的提示词。改完在文末「变更记录」写一行。

## 0. 为什么需要三个触发点

定时器只有在**电脑开机且 WorkBuddy 在运行**时才会触发；机器关机或深度休眠期间**不会补跑**，
到点没开机的任务就等于当天不存在。所以设三个时间点，**哪个点机器醒着就从哪个点开始**。

每次运行第一件事：读 `PIPELINE_STATE.md` 的 `last_run_date` / `today_started`。

- 今天已推进过 → 回一行「今日已推进到 <阶段>」，结束。**不重复开写、不重复发。**
- 今天还没推进 → 不管现在几点，立刻按下面顺序往下做，**不要等下一个整点**。

**幂等是硬要求**：三个触发点共享同一份状态文件，谁先醒谁干活，后来者只做检查。

## 1. 环境自检

1. 休眠唤醒后 Python venv / uv / Node / AWS 凭据可能未恢复，先验证再动笔。
2. 网络不通（dev.to、github.com 不可达）或实验环境起不来 → 等 15 分钟重试，最多 2 次。
3. 仍不行 → 在 `PIPELINE_STATE.md`「顺延记录」写一行（日期、缺什么、下次从哪继续），结束。
   **不写半成品，不降级成没跑过实验的稿子。**

## 2. 节奏判定

1. 读 `PLAN.md` 取下一篇（当前：UC01–UC05 已发布，下一篇 UC06《Orchestrating Agents: Nobody Decides Who Goes Next》）。
2. 从 `pinxiong.github.io/writing-lab/engagement/data/latest.json` 取**本系列**（`series == "strands-in-action"`）的最近发布日期；`series == "other"` 的独立文章不参与本系列的节奏判定。
3. 距最近发布不足 2 天且无在制品 → 回「未到写作窗口」，结束。
4. 有未完成篇目 → 继续它的下一个阶段。满 2 天且无在制品 → 开新篇。**每 2–3 天一篇，不日更。**

## 3. 写作

- 加载 `tech-article-writing` 与 `comment-reply-verification` 两个 skill。
- **开写前先读 `writing-lab/feedback/` 最近 2–3 篇记录的「下篇开写时必须记住的一条」**，写进本篇大纲开头。
- 阶段：详细大纲 → 实验与证据 → 英文正文 → **HTML 预览交付（第 5 节，走出正文立刻做）** → 三类评审 → 修订 → 渠道适配 → 发布。
- 每个数字必须来自真实运行，证据落盘该篇 `evidence/`。没跑出来的数字不许写。
- UC05 必须补真并发实验（线程/进程 + 真实 lease 时钟）；`outreach/uc03-comments/` 两组探针是确定性模拟，只用于解释状态机。
- **引用 SDK 或脚本源码时，正文里必须有逐字代码块，禁止只给链接 + 行号**（2026-11-09 用户明确要求）。理由：SDK 升级后同一个行号会指向完全不同的代码片段，链接不可靠。做法：代码块首行写 `# path:line -- version`，正文说明"逐字来自已安装版本"，链接退为二级指针；引用实验脚本时同理，省略处必须显式标注。三类评审都按此条判定。

## 4. 三类独立评审（各自单独 Agent 调用，互不参与对方工作）

| 评审 | 职责 | FAIL 判定 |
|---|---|---|
| 技术专家 | 每个技术断言的源码出处（file:line）与证据文件 | 无出处 |
| 目标读者 | 有 AWS 经验但没读过本篇的工程师 | 读不懂、跳步、标题与内容不符 |
| 独立复核 | 跑 `tech-article-writing` 的检查工具（破折号按用户政策忽略） | 图片、链接、代码块标注、Markdown 表格等硬规则违规 |

任一 FAIL → 修订后重审，全 PASS 才允许发布。**没通过不许发，也不许说"差不多可以发"。**

## 5. 交付预览稿（强制，不可跳过）

**正文一写完就要出 HTML 预览交给 Pin 看，不等评审、不等发布窗口。** 这是硬要求：文字再好，他没在浏览器里读过一遍就等于没交付。

```bash
python3 tools/make_review_html.py usecases/<NN-slug>/article.md \
  --label "UC05 · Strands Agents series" --status "<not_started|draft|in_review|ready_to_publish>"
```

- 输出 `usecases/<NN-slug>/review/article-preview.html`：单文件自包含（图片 base64 内联）、可离线、可打印、手机可读。
- **每次改完正文要重新生成一次**，文件名不变（覆盖），这样 Pin 打开的就是最新版。
- 生成后**必须用 `present_files` 把 HTML 递给他**，不能只说"文件在 xxx 路径"。同一档里改了三次就递一次最新版，不要重复刷屏。
- 顺带自检：控制台出现 `WARNING missing images` 就必须修，说明有图没内联进去。
- 预览只服务评审，不进发布物料、不提交入库（体积大且非线上资产）。

## 6. 发布

- 时间依据 `PUBLISHING-POLICY.md`：主窗口 **21:30–22:30（GMT+8）**，周二/三/四优先，周六日不发。
- 不在窗口内 → 写顺延记录，等下一个符合条件的工作日窗口。不夜间赶发、不为赶窗口降质量门。
- 真相源 `pinxiong.github.io/content/posts/<slug>.md`，图片进 `static/images/<slug>/`，push 后确认线上 200。
  **push 前先 `git pull --rebase`**：21:30 同时还有日报与周复盘任务会推同一个仓库，并发推送会被拒；被拒就 rebase 后重试一次，不要 force push。
- Dev.to 与 BC 的 canonical 均指回主站；Dev.to 一段一行。
- **Medium 不发，但人工物料是发布的一部分，不是"以后再说"。** 这是 Pin 明确要求长期执行的规则（2026-11-10）：**每次自动发布文章都必须同时准备 Medium 物料，不许漏、不许"先发再补"**。
- **发布门禁（硬约束，不靠"记得"）**：在把 `stage` 改成 `published`、push 主站、发 Dev.to / BC **之前**必须执行：

  ```bash
  python3 /Users/pinxiong/Documents/Important/strands-in-action/check_publish_gate.py <slug>
  ```

  站点目录不在默认位置时加 `--site <path>`。脚本校验下面三件物料是否存在、内容是否齐全、封面是不是 16:9，**并对全系列做「可复跑入口」「代码块 0 缩进」「封面深蓝基准」体检**（当前 24 项，篇目增加时自动增加）。**这条命令就是发布前 check 的权威规则**：Pin 2026-11-11 要求把每次修复固化下来，以后任何质量规则都优先做成门禁检查项，不靠文档里的"记得"。**退出码非 0 → 禁止发布**，按 FAIL 项补齐后重跑；不许把缺项写成"已知偏差"放行，也不许跳过脚本直接发。任何一个触发点（10:30 / 14:30 / 21:30）走到发布步骤都受这条约束。Medium URL 位在发布前是 `<MEDIUM_URL>` 占位、手动 Import 后回填真实链接，两种状态门禁都应通过。
- **可复跑入口 = 第 4 件硬交付物**（Pin 2026-11-06 裁定，2026-11-11 复发）。写 `Try it yourself` 时首屏就要有 `git clone https://github.com/pinxiong/strands-in-action.git`，紧跟 `cd strands-in-action/usecases/<目录>` 与依赖安装；正文首屏另给完整仓库目录 URL。只写 `cd usecases/...` 或 `src/` 相对路径 = 缺件，读者跑不起来。门禁会扫描**所有** `usecases/*/article.md`、`usecases/*/publish/*.md` 和主站稿件，任何一篇退化都会拦下当次发布；`article.md` 改完要同步到三份渠道稿件。
- **代码块 0 缩进 = 第 5 件硬交付物**（Pin 2026-11-11 裁定）。每个 fenced code block 的第一行代码顶格，只保留相对层级；从 SDK 源码抠出的片段必须先 dedent，不能把类方法里的 8 / 16 / 20 个前导空格带进文章。首行 `# path:lines` 来源注释保持 0 位。门禁扫描全系列 `article.md`、全部 `publish/*.md` 与主站稿件，任何一块整体右移都会拦下发布；`final_check.py` 单篇扫描同样报「阻断」。改正文时四份稿件（article / devto / BC 稿 / 主站）必须一起改。
- **封面风格 = 第 6 件硬交付物**（Pin 2026-11-11 裁定）。UC01–UC04 的深蓝基准是唯一风格：`#0b2547 → #14407c` 渐变、蓝色胶囊系列编号、左侧白色大标题 + 一行 `#7db4ff` 高亮、右侧机制图（事实框 / 两个数字框 / 结论条）、底部等宽验证说明。UC05/UC06 曾改成白底 `#f8fafc` 细线排版且尺寸变成 1200×630 / 1000×420，与系列格格不入。**新篇禁止手搓配色**，一律运行：

  ```bash
  cd /Users/pinxiong/Documents/Important/strands-in-action
  .venv/bin/python tools/build_covers.py --slug <slug>      # 生成三套 SVG + PNG 并校验尺寸
  .venv/bin/python tools/build_covers.py --check            # 只校验不重写
  ```

  三档输出：`cover.svg/png` 1400×788（主站 og:image）、`cover-devto.svg/png` 1200×504、`cover-medium.svg/png` 1400×788（viewBox 必须是 `0 0 1400 788`）。生成器里每篇的标题、副标题、右侧机制图文字必须与 `evidence/`、正文和 front matter 的 `cover.alt` 三方一致。门禁检查深蓝 SVG 标记、无白底残留，以及两档 PNG 尺寸。
- **封面重建 = 全渠道换图 + 线上核验**（Pin 2026-11-11 追问后补）。生成新封面不等于已发布文章换了图：每个渠道各存一份副本，必须逐个换、逐个验。

  | 渠道 | 换图动作 | 执行方 |
  |---|---|---|
  | 主站 | 覆盖 `static/images/<slug>/` 三套 PNG/SVG 并 push | 自动 |
  | Dev.to | `PUT /api/articles/{id}` 更新 `cover_image`，图片 URL 加 `?v=<版本>` 破代理缓存 | 自动 |
  | Builder Center | 平台资产库存的是上传时的副本：进编辑页重传 `cover-medium.png`，**并在同一浏览器会话点 Publish**；只上传不 publish，线上仍是旧 `cove.webp` | 自动（`aws-builder-center-publish` §0.0） |
  | Medium | 无 API：已发布故事在编辑页替换正文第一张图后 Save and publish；未 Import 的直接用新文件 | 人工，手册第 4 步写死操作步骤 |

  BC 封面落库是异步的：`step_cover` 报 FAIL 不要立刻判定失败，重开编辑器看 "Saved cover image" 的 asset URL，下载图像确认深蓝像素后再 publish（troubleshooting §10 / §11 / §15）。
  **每次封面重建后，对每篇已发布文章都要跑**（退出码非 0 必须修到 PASS）：

  ```bash
  cd /Users/pinxiong/Documents/Important/strands-in-action
  .venv/bin/python tools/verify_live_covers.py \
      --site  https://xiongpin.dev/posts/<slug>/ \
      --devto https://dev.to/aws-builders/<devto-slug> \
      --bc    https://builder.aws.com/content/<id>/<slug>
  ```

  脚本下载三个线上头图，检查尺寸（1400×788 / 1200×504）与深蓝渐变像素（BC 从 og:image 的 base64 里解出 hero）；Medium 明确输出 `MANUAL`，**不许默认当成 PASS**。
- 发布窗口当档必须产出以下三件：
  1. `pinxiong.github.io/writing-lab/distribution/<slug>-medium-manual.md` —— 按上一篇手册的结构（7 步）：Import 源 URL 与三渠道线上链接表；Title 核对；**4 个 subtitle 选项，每个标字符数（≤140）并写明推荐理由**；Byline 首行；封面路径与尺寸；5 个标签；正文核对清单（本篇实际图片数、代码块数、引用行、状态机 ASCII 块）；Advanced settings 的 canonical 勾选项与发布后回填动作。Medium URL 用 `<MEDIUM_URL>` 占位，发布后回填。
  2. `static/images/<slug>/cover-medium.png` —— **1400×788（16:9）**，源 SVG 同目录保留。出图时用 `cover-medium.svg` 的 viewBox 直接定为 `0 0 1400 788`，不要先做 1.90:1 再补边；用 `resvg-py` 渲染（其余工具在本机不可用，见 `tech-article-writing` §8）。渲染后读 PNG 头校验宽高，**尺寸不对就重做，不要写进台账当"已知偏差"**。
  3. `pinxiong.github.io/writing-lab/distribution/<slug>-slack.md` —— A 标准版 + B 短版（可再加 C 全渠道短版），链接块只放 **BC / Dev.to / Medium 三条**（Medium 为 `<MEDIUM_URL>`，发布后回填）与逐条数字出处（指向该篇 `evidence/`）。**按 Pin 2026-11-10 口径，Slack 文案里不放主站 Blog 链接**：主站只作各平台 canonical，读者从平台文内链接回流。门禁会检查文案块里没有 `xiongpin.dev/posts/`。
- 发布后 30 分钟内不改正文（避免 Dev.to 重抓打乱首小时数据）。
- 门禁通过后把 `PIPELINE_STATE.md` 的 `publish_gate` 三个字段置为 `true`，再记 D+0 台账：标题、三渠道链接、发布时刻（GMT+8 与 UTC）、字数、代码块数、实验组数；**Medium 行不得只写"未发"，要写"物料已就绪，待手动 Import"，并列出手册与封面文件名**，同时记一行门禁结果（命令 + 14/14 PASS）。手动 Import 完成后把该行换成真实 URL，并同步回填 Medium 手册顶部表格、Slack 文案（A 版与任何含 Medium 链接的短版）、`usecases/<n>/publish/README.md` 共四处。
- 新篇一开始就按 `<slug>` 建这三件物料的占位，别等发布窗口当档临时赶；封面 `cover-medium.svg` 的 viewBox 直接做成 `0 0 1400 788`。

## 7. 反馈回灌

按 `writing-lab/feedback/README.md`，**发布不是终点**：

| 时点 | 动作 |
|---|---|
| D+2 | 读两渠道全部评论原文 → `feedback/YYYY-MM-DD-<uc>.md`（用 `TEMPLATE.md`）；小样本（<48h 或 views<50）只写观察项 |
| D+7 | 与前三篇同渠道对比，判断是文章问题还是时点/选题问题，追加进同一份记录 |

评论原文位置：Dev.to `data/comments/<article-id>.json`；Builder Center `data/comments/bc-<uc>-<id>.json`（`scan.py` 已接公开接口）。按 `tech-article-writing` §11 分四类判读、分渠道统计，**致谢不进归因**；评论区零追问时，把正文自己写下的 `does not cover` 登记进 `topic-backlog.md`，别让闭环空转。

每条结论必须落到一个出口：**A** 改 `tech-article-writing` + 记 `feedback/ledger.md` 四要素｜**B** 改 `PLAN.md`（读者提的是系列缺口就走插队，附顺延清单，版本 +1）｜**C** 改 `PUBLISHING-POLICY.md`｜**D** 明确不改并写理由。

**没有出口的反馈等于没读。不允许只更新报表、不更新规则。**

## 8. 汇报

只在有实质进展时汇报：开写、评审结论、发布链接、顺延原因、规则修订。无进展回一行。
需要 Pin 拍板的情形只有三种：系列方向变更、质量门连续两轮不过、需要付费资源或新凭据。

---

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-08 | 建立本文件；开写 09:00 → 10:30；改为三点触发 + 幂等补跑；发布窗口收到 21:30–22:30 并绑定 PUBLISHING-POLICY；加入反馈回灌（D+2 / D+7） |
| 2026-11-09 | 新增第 5 节「交付预览稿（强制）」：正文写完必出 HTML 预览并 `present_files` 递给 Pin，改一次重生成一次；原 5/6/7 节顺延为 6/7/8 |
| 2026-11-09 | 第 3 节新增硬规则：源码引用必须内联逐字代码块（含 `path:line -- version` 表头），禁止只给链接 + 行号；链接退为二级指针 |
| 2026-11-10 | 第 7 节指明两渠道评论原文的新路径（BC 不再是 JS-only）；按 §11 分四类判读、致谢不进归因；零追问时把正文 `does not cover` 登记进 topic-backlog。依据 UC05 反馈记录 |
| 2026-11-10 | 第 6 节把「Medium 只出人工物料」补成**三件可验收交付物**（medium-manual.md / 16:9 cover-medium.png / slack.md）与 D+0 台账核对项。起因：UC05 只写了「Medium 未发（今晚不动）」，手册与 Slack 文案都没产出，封面做成 1.90:1 且把尺寸偏差记进台账就算完。依据 Pin 2026-11-10 追问 |
| 2026-11-10 | 第 6 节新增**发布门禁**：`check_publish_gate.py <slug>` 校验 14 项，非 0 退出禁止发布、禁止置 `published`；`PIPELINE_STATE.md` 增加 `publish_gate` 三个布尔字段。起因：Pin 明确「后面每次自动发布文章一定要准备 Medium 物料，不要忘记了」——文档里写一句仍可能忘记，改成可执行的拦截面 |
| 2026-11-10 | UC05 Medium 手动 Import 完成，URL 回填手册 / Slack / D+0 台账 / publish README 四处；门禁对 Medium URL 位改为「占位或已回填真实链接均通过」，否则回填后重跑会误报 2 项 FAIL。第 6 节补上回填四处的规定 |
| 2026-11-10 | Pin 口径：**Slack 文案不放主站 Blog 链接**。UC05 的 A/C 两版删掉 Blog 行；第 6 节第 3 条改为链接块只列 BC / Dev.to / Medium；门禁的「Slack 含主站链接」改为「三条渠道链接齐全且文案块内无 `xiongpin.dev/posts/`」，避免以后为了过门禁又把 Blog 链接加回来。UC03/UC04 已发文案不动 |
| 2026-11-10 | 第 2 节节奏判定的「最近发布」限定为 `series == "strands-in-action"`。起因：当天 21:00 发布的 dev.to 独立文章（`series == "other"`）写进 `latest.json` 后，按字面取「最近发布」会把 UC06 从 11-11 误顺延到 11-13；本系列节奏只看本系列文章。同节第 1 步的下篇指针同步为 UC06，`PLAN.md` 的 UC05 状态与详纲标题同步为已发布 |
| 2026-11-11 | 第 6 节新增「可复跑入口 = 第 4 件硬交付物」，`check_publish_gate.py` 增加全系列 clone 块体检（现在 18 项）。起因：Pin 第二次指出文章 `Try it yourself` 只写 `cd usecases/...`、正文只写 `src/` 相对路径，读者拿不到完整仓库地址。根因是 11-06 定的规则只写在 skill / README 散文里，11-07 与 11-10 改版时被覆盖，且 `final_check` 与门禁都不查。已修 UC05 四份稿件 + UC06 正文，并把规则写进 skill 顶部「永久政策」块、发布前清单、README Conventions 与用户级 MEMORY.md；机器门禁为权威判据 |
| 2026-11-11 | 第 6 节新增「代码块 0 缩进 = 第 5 件硬交付物」，门禁从 18 项扩到 21 项；`final_check.py` 新增代码块整体缩进扫描（阻断级）。起因：UC06 已发布后 Pin 指出 5 个 Python 块带着 SDK 源码的嵌套缩进（8/16/12/20 空格）、来源注释却在 0 位，读者看到整块右移、`if` 与 `else` 层级错乱。此前 skill / final_check / 门禁都没有任何一条覆盖代码块缩进。已修 UC06 四份稿件 + HTML 预览，并把规则写进 skill 顶部「永久政策」块、发布前清单、README Conventions 与用户级 MEMORY.md；机器门禁为权威判据 |
| 2026-11-11 | 第 6 节新增「封面风格 = 第 6 件硬交付物」，门禁从 21 项扩到 24 项（全系列封面 SVG 深蓝基准 + `cover.png` / `cover-devto.png` 尺寸）；新增 `tools/build_covers.py` 作为封面唯一模板，UC05 / UC06 三套封面全部重做为 UC01–UC04 的深蓝风格。起因：Pin 指出从 UC05 开始封面换成白底 `#f8fafc` 细线排版、尺寸也变成 1200×630 / 1000×420，与之前几篇格格不入。同时按 Pin 要求把「代码块 0 缩进」明确固化为**发布前 check 三条命令之一**（skill §8），并声明今后任何质量规则一律优先做成门禁检查项，不靠文档里"记得" |
| 2026-11-11 | 第 6 节新增「封面重建 = 全渠道换图 + 线上核验」，新增 `tools/verify_live_covers.py`（下载主站 / Dev.to / BC 三个线上头图，校验尺寸与深蓝像素，Medium 只报 `MANUAL`）。起因：Pin 指出 UC05 / UC06 的新封面生成并放到仓库后就停手，BC 两篇线上仍挂平台资产库里的旧白底 `cove.webp`。当晚用 `aws-builder-center-publish` 对两篇重传封面并在同一会话 Publish，线上 hero 分别换成 `3LxyHNUWw…/cove.webp` 与 `3Ly14Jmd…/cove.webp`，两篇跑核验脚本均三渠道 PASS；Medium UC05 已发布故事仍需人工替换正文第一张图（手册第 4 步），UC06 尚未 Import，直接用新图即可 |
