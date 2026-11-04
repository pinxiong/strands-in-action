---
name: write-strands-article
description: 在 strands-in-action 仓库里写（或修改）用例与配套英文文章时使用。这是一个项目级入口，负责把通用产线的规则拉进来：写前加载 tech-writing-methodology（内容方法论）与 hands-on-series-pipeline（产线规则），技术参数走 profiles/strands.md，配图走 agentcore-figures，收尾走 medium-manual-publish / distribution-copy / aws-builder-center-publish。触发词：写 strands 的 UC0X、给 strands 加一篇、把这个用例写成文章、按产线跑 strands、发 strands 这篇文章。不适用：只改 Python 代码不写文章、纯排版调整、其他不相关的仓库。
read_when:
  - 用户要在 strands-in-action 里写新用例或新文章
  - 用户说「按产线跑」「走那套流程」「写一篇 strands 的 UC0X」
  - 要发布 strands 的文章到任一渠道
---

# strands-in-action 文章入口

本仓库写文章走到产线上时，第一步是**按顺序加载三份文档**。它们都在用户级，
用绝对路径读，不依赖 skill 是否被自动发现：

```text
/Users/pinxiong/.workbuddy/skills/tech-writing-methodology/SKILL.md          内容层（先读）
/Users/pinxiong/.workbuddy/skills/hands-on-series-pipeline/SKILL.md          产线层
/Users/pinxiong/.workbuddy/skills/hands-on-series-pipeline/profiles/strands.md  技术参数
```

判断不了某条规则该放哪层，就不要改它 —— 通用规则只能改通用层，改这里会让两个系列分叉。

## 本仓库的硬参数（与 AgentCore 系列不同的地方）

- 主题是 **Strands Agents SDK，一个开源库**，不是托管平台。文章第一句就要把这个
  本体类别说清：读者要能立刻说出「这是 SDK，我自己在自己的进程里跑」。
- 版本基线唯一来源：`docs/00-facts-baseline.md`。写版本号、默认值、模型 ID 一律从那里取，
  不靠记忆。README 顶部的 "Verified against" 那行随手同步。
- 跑在哪：本地、笔记本都行，不强依赖 AWS。但**只要用到 Bedrock 模型就要显式给区域**，
  本机默认区域是 `ap-southeast-1`，容易踩错。
- AgentCore 系列锁 `us-east-1` 是它自己的约束（Registry 只有 5 个区域），
  **本系列不要照抄这个约束**；用例该用什么区域就用什么，但要写出来。
- 用例目录：`usecases/NN-<slug>/`，里面有 `src/`、`evidence/`、`README.md`、`article.md`。
  每个用例能独立跑，不 import 别的用例。

## 每篇文章的九段顺序（字面一致，不许改）

`## The use case` → `## What AgentCore does here` → `## Requirements` → `## The code`
→ `## How it works` → `## Deploy it` → `## What it produced` → `## Troubleshooting`
→ `## Takeaways`

第二段的标题在 strands 系列里仍然是这七个字，因为 series 对外是一个产品线；
如果这一篇压根不涉及 AgentCore，就如实写不涉及，不要空着。

## 产线七步（通用层的简版，细节在那份里）

1. 写 3-5 条**可证伪断言**，写不出来说明选题没成型。
2. 建用例到 `usecases/NN-<slug>/`， Independence：不依赖其他用例。
3. **真机跑**。每个命令跑完立刻把原始输出存进 `evidence/`，文件名用产出它的命令命名。
4. 出图。SVG 源 + **2880px 宽** 的 PNG；命令后面跟图，**不再贴输出代码块**。
5. 写 `article.md`，九段顺序，1900 词以内为宜（本系列不是 UC07，没有 2500 的例外）。
6. **换一个 agent 验证**，写的人不验自己。
7. PASS 后才发布。

## 发布顺序

```bash
env -u PYTHONPATH /usr/local/bin/python3 \
  ~/Documents/Important/bedrock-agentcore-in-action/shared/scripts/publish_article.py \
  --slug <slug> --devto-create --medium-export
```

再 `--devto-update --devto-publish --skip-hugo` 把 Dev.to 草稿转正式。
Medium 手动凭证，Builder Center 走 `aws-builder-center-publish` skill。

## 常见翻车点

- 数字不是跑出来的：写之前先跑，跑不通宁可删这一节，不许估。
- 图和证据不是同一次运行：重跑之后 id 全变，图、正文、evidence 要同步更新。
- 用了 `aws` CLI 建的资源（不在 CDK 栈里）：**创建命令和删除命令都要写进文章**，
  否则读者复现不出，而且会在账号里留资源。
- 文章里出现 `plaintext` 围栏：禁用，最少标 `bash`。
- GitHub 链接写成 `/tree/main/`：这个仓库默认分支是 **master**，写成 main 是 404。
