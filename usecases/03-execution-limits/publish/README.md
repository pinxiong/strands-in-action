# UC03 发布物料清单

状态：**待发布**（文章与物料已定稿，三处线上链接未生成）

## 文件

| 渠道 | 文件 | 说明 |
|---|---|---|
| 主站 xiongpin.dev | `pinxiong.github.io/content/posts/execution-limits.md` | Hugo 稿件，front matter 已带 cover 与 description |
| 主站图片 | `pinxiong.github.io/static/images/execution-limits/` | 7 张正文图（2880 宽）+ cover.png 1400×788 + cover-devto.png 1200×504 |
| AWS Builder Center | `publish/execution-limits.md` | tags `["ai","agents"]`、canonical、正文顶部母版链接行 |
| BC 图片 | `publish/images/execution-limits/` | 正文图 2000 宽降采样 + cover-medium.png 1400×788 |
| Dev.to | `publish/devto.md` | `published: false`，图片走 xiongpin.dev 绝对 URL |
| Medium | `writing-lab/distribution/execution-limits-medium-manual.md` | 唯一 Medium 物料（subtitle 四条候选，全部 ≤140 字符） |
| Slack | `writing-lab/distribution/execution-limits-slack.md` | 标准版 + 短版，链接占位待回填 |
| 封面源文件 | `publish-assets/cover.svg` / `cover-devto.svg` | 改字重出即可，渲染后用 `sips` 裁到目标尺寸 |

## 发布顺序

1. **Pages**：把 `content/posts/execution-limits.md` 与 `static/images/execution-limits/` 提交推送，
   等 GitHub Actions 上线，核验 200 + canonical + og:image。
2. **Builder Center**：`adopt_session.py` → `publish.py doctor --md publish/execution-limits.md`
   → `publish.py run --md publish/execution-limits.md --images-dir publish/images/execution-limits`。
   封面步骤若 150s 超时未出现 "Saved cover image"，按技能 troubleshooting §11 核验，不要盲重传。
3. **Dev.to**：把 `publish/devto.md` 的 `published` 改 `true`，走 Forem API（org 2794），
   确认 canonical 指回主站。
4. **Medium**：按 `execution-limits-medium-manual.md` 手动 Import，选 subtitle、传 cover-medium、五枚标签。
5. **Slack**：把 `execution-limits-slack.md` 里三个 `<..._URL>` 换成真实链接再发。

## 定稿一致性

- 正文 1866 词，机械检查 0 缺陷，平均句长 14.2、连接词 0.80/100w、>40 词长句 0
- 7 张图：S2（9 vs 3 turns）→ S1（三个探针）→ S3 → S4 → S5 → S6 → F1
- 三渠道正文同源，差异只有：图片 URL 形式、tags 数量、canonical 字段名
