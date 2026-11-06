# Medium 发布操作卡 · UC02

## 2026-11-05 修订（读者评论触发，需手工同步）

BC 评论有读者指出 make_shell 并无 allowlist（属实）。正文该段已在主站/BC/Dev.to 同步修订，
Medium 为 Import 稿，需手工改一次：打开已发布文章进编辑模式，全文搜
`wrapping the execution in your own`，把该句到段末替换为：

> `vended_tools` does ship a `make_shell`, but the factory takes no allowlist. Its
> arguments are `sandbox`, `name` and `description`. The model still fills in `command` and
> `timeout`. What the factory does is bind execution to a sandbox you supply, such as a
> `DockerSandbox` with a read-only mount and no network. An allowlist belongs in a
> `BeforeToolCallEvent` hook, which sees the command before execution and can refuse the
> call. That combination is the one I would run anywhere near production. Do not switch
> imports just to silence a warning.

（粘贴时把换行合成一个自然段即可。）

## 步骤

1. 打开 https://medium.com/p/import
2. 贴入主站 URL：`https://xiongpin.dev/posts/the-tools-that-got-replaced/`
3. Import 后检查：标题、正文、5 张图是否完整带入
4. 手动补 **Subtitle**（见下方三选一）
5. 封面：上传 `publish/images/the-tools-that-got-replaced/cover-medium.png`（深蓝版，1400×788）
6. Tags（Medium 限 5 个）：`AI` `Agents` `AWS` `Strands` `Software Engineering`
7. Import 方式会自动带上 canonical link 指回主站，无需手设

## Subtitle 选项

**A（推荐 · 与预览页副标题一致，148 字符）**
> A @tool function is twelve lines. What the model receives is a contract written in your docstring — and 38 of the 46 built-in tools are being replaced.

**B（悬念短版 · 与封面 takeaway 呼应，82 字符）**
> What the model reads is a contract written in your docstring — and it never asks for permission.

**C（收益清单式 · 118 字符）**
> Read the Strands source with me: how a docstring becomes a tool spec, and why 38 of the 46 built-in tools are gone.

备注：Medium 列表页副标题约 140 字符截断，B/C 在安全线内，A 会微裁但信息最完整。
