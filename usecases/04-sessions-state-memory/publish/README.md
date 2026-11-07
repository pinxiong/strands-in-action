# UC04 发布物料清单

状态：**已发布**（2026-11-07）

| 渠道 | 线上地址 |
|---|---|
| 主站 | https://xiongpin.dev/posts/sessions-state-memory/ |
| AWS Builder Center | https://builder.aws.com/content/3Ll4sEZ0YTvNRvbvH4UWe5hUdtz/it-remembers-across-restarts-and-forgets-mid-conversation |
| Dev.to | https://dev.to/aws-builders/it-remembers-across-restarts-and-forgets-mid-conversation-1ehh |
| Medium | https://medium.com/@pinxiong.cn/it-remembers-across-restarts-and-forgets-mid-conversation-1a27f5d6b782 |

## 文件

| 渠道 | 文件 | 说明 |
|---|---|---|
| 主站 xiongpin.dev | `pinxiong.github.io/content/posts/sessions-state-memory.md` | Hugo 稿件，front matter 已带 cover 与 description |
| 主站图片 | `pinxiong.github.io/static/images/sessions-state-memory/` | 6 张正文图（2880 宽）+ cover.png 1400×788 + cover-devto.png 1200×504 |
| AWS Builder Center | `publish/sessions-state-memory.md` | tags `["ai","agents"]`、canonical、正文顶部母版链接行 |
| BC 图片 | `publish/images/sessions-state-memory/` | 正文图 2000 宽降采样 + cover-medium.png 1400×788 |
| Dev.to | `publish/devto.md` | `published: false`，图片走 xiongpin.dev 绝对 URL |
| Medium | `writing-lab/distribution/sessions-state-memory-medium-manual.md` | 唯一 Medium 物料（subtitle 四条候选，全部 ≤140 字符） |
| Slack | `writing-lab/distribution/sessions-state-memory-slack.md` | 标准版 + 短版，链接占位待回填 |
| 封面源文件 | `publish-assets/cover.svg` / `cover-devto.svg` | 改字重出即可，渲染后用 `sips` 裁到目标尺寸 |

## 发布顺序

1. **Pages**：把 `content/posts/sessions-state-memory.md` 与 `static/images/sessions-state-memory/`
   提交推送，等 GitHub Actions 上线，核验 200 + canonical + og:image。
2. **Builder Center**：`adopt_session.py` → `publish.py doctor --md publish/sessions-state-memory.md`
   → `publish.py run --md publish/sessions-state-memory.md --images-dir publish/images/sessions-state-memory`。
   body 与 publish 必须**同一浏览器会话**（见 troubleshooting §15）。封面步骤若 150s 超时未出现
   "Saved cover image"，按 §11 核验，不要盲重传。
3. **Dev.to**：把 `publish/devto.md` 的 `published` 改 `true`，走 Forem API（org 2794），
   确认 canonical 指回主站。**必须用 curl + 浏览器 UA**，urllib 默认 UA 会被 403。
4. **Medium**：按 `sessions-state-memory-medium-manual.md` 手动 Import，选 subtitle、传 cover-medium、四枚标签。
5. **Slack**：把 `sessions-state-memory-slack.md` 里三个 `<..._URL>` 换成真实链接再发。

## 定稿一致性

- 正文 2851 词（不含 H1），三视角评审两轮 + 终审双 PASS
- 6 张图：S1（重启召回）→ S2（agent.state）→ S5（快照）→ S3（滑窗 14 vs 6）→ F1（三条泳道机制图）→ S4（摘要稳态 9）
- 三渠道正文同源，差异只有：图片 URL 形式、tags 数量、canonical 字段名、BC 多一行 Originally published
- 与前作的差异：本篇 `Try it yourself` 首屏是 `git clone` + venv 安装块（UC01/UC02 的口径），
  UC03 漏了这一块，补链时一并核对
