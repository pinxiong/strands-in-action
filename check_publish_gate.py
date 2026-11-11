#!/usr/bin/env python3
"""Publish gate: verify Medium deliverables AND the reproducible repo entry point.

Usage:
    python3 check_publish_gate.py <slug> [--site /path/to/pinxiong.github.io]

Exit 0 = all checks pass and the article may be published.
Exit 1 = something is missing; fix it and run again. Never publish on exit 1.

Two families of checks:

1. Medium manual, 16:9 cover and Slack copy. Medium itself is not auto-published,
   but its manual materials ARE part of the release. This gate exists because UC05
   shipped without them (2026-11-09) -- the pipeline doc said "Medium only manual
   materials" and nobody produced them. The Medium URL starts life as a
   <MEDIUM_URL> placeholder and is backfilled after the manual Import; both states
   pass, because the gate checks that the slot exists.

2. Reproducible entry point. Pin ruled on 2026-11-06 that every article must give
   the FULL clone address (https://github.com/pinxiong/strands-in-action.git) plus
   the cd into the use case directory. That rule was written only in prose, got
   overwritten by later skill edits, and UC05/UC06 regressed to a bare
   "cd usecases/...". A reader cannot run that. This gate now checks EVERY article
   and EVERY channel copy mechanically, so the rule cannot be forgotten again.

3. Code block indentation. Pin ruled on 2026-11-11 that the first code line in
   every fenced block starts at column 0. UC06 shipped with SDK snippets pasted
   straight out of nested class methods, carrying 8/16/20 leading spaces while
   the annotation comment sat at 0. This gate scans every article and channel
   copy and rejects any block whose top-level code line is shifted right.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SITE = REPO_ROOT.parent / "pinxiong.github.io"
EXPECTED_W, EXPECTED_H = 1400, 788
MEDIUM_URL_RE = re.compile(r"https://medium\.com/@pinxiong\.cn/[a-z0-9-]+-[0-9a-f]{8,}", re.I)
REPO_URL = "https://github.com/pinxiong/strands-in-action"
CLONE_LINE = REPO_URL + ".git"

results: list[tuple[bool, str, str]] = []


def has_medium_slot(text: str) -> bool:
    """A placeholder before Import, or the real Medium URL after backfill."""
    return "<MEDIUM_URL>" in text or bool(MEDIUM_URL_RE.search(text))


def check(ok: bool, name: str, detail: str = "") -> bool:
    results.append((ok, name, detail))
    return ok


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        head = path.read_bytes()[:24]
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", head[16:24])
    except OSError:
        return None


def try_it_section(text: str) -> str:
    """The Try it yourself section, up to the next H2 (or EOF)."""
    match = re.search(r"^## Try it yourself\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def has_clone_block(text: str, usecase_dir: str) -> bool:
    """Full clone URL followed immediately by the cd into this use case."""
    pattern = re.escape(CLONE_LINE) + r"\ncd " + re.escape(f"strands-in-action/usecases/{usecase_dir}")
    return bool(re.search(pattern, try_it_section(text)))


# Pure output blocks (logs, traces, ASCII diagrams) are intentionally excluded:
# their indentation is data, not code structure.
CODE_LANGS = {
    "python", "py", "bash", "sh", "shell", "console", "json", "yaml", "yml",
    "javascript", "js", "ts", "typescript", "go", "java", "rust", "sql",
    "toml", "ini", "diff", "ruby", "php", "csharp", "cs",
}


def shifted_code_blocks(text: str) -> list[str]:
    """Find fenced blocks whose top-level code line does not start at column 0.

    A snippet pasted straight out of a nested class method carries the original
    indentation. Pin's rule: the first code line is at 0 and only relative
    nesting remains. A leading `# path:lines` annotation comment at column 0 is
    allowed and is not counted as a code line.
    """
    issues: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("```"):
            lang = lines[i][3:].strip().lower()
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            if lang in CODE_LANGS:
                body = lines[i + 1 : j]
                nonempty = [
                    (k, len(l) - len(l.lstrip(" ")))
                    for k, l in enumerate(body)
                    if l.strip()
                ]
                header = (
                    0
                    if body
                    and body[0].lstrip().startswith("#")
                    and len(body[0]) - len(body[0].lstrip(" ")) == 0
                    else None
                )
                candidates = [(k, ind) for k, ind in nonempty if k != header]
                if candidates:
                    shift = min(ind for _, ind in candidates)
                    if shift >= 4 and shift % 4 == 0:
                        issues.append(f"L{i + 1} lang={lang} shift={shift}")
            i = j + 1
        else:
            i += 1
    return issues


def indent_report(files: list[Path], root: Path) -> list[str]:
    bad: list[str] = []
    for p in files:
        if not p.is_file():
            continue
        for issue in shifted_code_blocks(p.read_text(encoding="utf-8")):
            bad.append(f"{p.relative_to(root).as_posix()}:{issue}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="article slug, e.g. reservations-fencing")
    ap.add_argument("--site", type=Path, default=DEFAULT_SITE)
    args = ap.parse_args()
    site: Path = args.site.resolve()
    slug = args.slug
    dist = site / "writing-lab" / "distribution"
    images = site / "static" / "images" / slug

    # 1. Medium manual
    manual = dist / f"{slug}-medium-manual.md"
    if check(manual.is_file(), "Medium 手册存在", str(manual)):
        text = manual.read_text(encoding="utf-8")
        check(has_medium_slot(text), "手册留了 Medium URL 位", "占位或已回填的真实链接均可")
        check(
            bool(re.search(r"(?i)subtitle", text)),
            "手册写了 Subtitle 章节",
            "Import 后 subtitle 恒为空，必须手填",
        )
        options = len(re.findall(r"\|\s*\*{0,2}[①②③④]", text))
        check(options >= 3, "手册有 ≥3 个 subtitle 选项", f"实际 {options} 个")
        check("canonical" in text.lower(), "手册含 canonical 勾选步骤", "Advanced settings")
        check("16:9" in text or "1400" in text, "手册注明封面规格", "1400×788 / 16:9")

    # 2. Slack copy
    slack = dist / f"{slug}-slack.md"
    if check(slack.is_file(), "Slack 文案存在", str(slack)):
        text = slack.read_text(encoding="utf-8")
        # Check the copy that actually gets pasted into Slack, not the doc's own notes.
        blocks = "\n".join(re.findall(r"```text\s*(.*?)```", text, re.S))
        check(has_medium_slot(blocks), "Slack 文案含 Medium URL 位", "占位或已回填的真实链接均可")
        check(
            "builder.aws.com/content/" in blocks
            and "dev.to/" in blocks
            and has_medium_slot(blocks)
            and "xiongpin.dev/posts/" not in blocks,
            "Slack 三渠道齐全且无主站链接",
            "BC / Dev.to / Medium；按 Pin 口径不放 Blog 链接",
        )
        check("evidence/" in text, "Slack 标注数字出处", "")

    # 3. Feature image, PNG + SVG source
    cover = images / "cover-medium.png"
    if check(cover.is_file(), "Medium 封面 PNG 存在", str(cover)):
        size = png_size(cover)
        check(
            size == (EXPECTED_W, EXPECTED_H),
            "封面尺寸 1400×788（16:9）",
            f"实际 {size[0]}x{size[1]}" if size else "无法读取 PNG 头",
        )
    svg = images / "cover-medium.svg"
    if check(svg.is_file(), "封面源 SVG 存在", str(svg)):
        text = svg.read_text(encoding="utf-8")
        check(
            'viewBox="0 0 1400 788"' in text,
            "SVG viewBox 为 0 0 1400 788",
            "不要先做 1.90:1 再补边",
        )

    # 4. Reproducible entry point: mechanical enforcement of Pin's 2026-11-06 rule.
    usecases = REPO_ROOT / "usecases"
    articles = sorted(usecases.glob("*/article.md"))
    bad_articles = [
        a.parent.name
        for a in articles
        if not has_clone_block(a.read_text(encoding="utf-8"), a.parent.name)
    ]
    check(
        bool(articles) and not bad_articles,
        "全系列正文含完整 clone 块",
        f"检查 {len(articles)} 篇；缺：" + (", ".join(bad_articles) if bad_articles else "无"),
    )

    channel_files = [
        p
        for p in sorted(usecases.glob("*/publish/*.md"))
        if p.name.lower() != "readme.md"
        and "## Try it yourself" in p.read_text(encoding="utf-8")
    ]
    bad_channels = [
        str(p.relative_to(REPO_ROOT))
        for p in channel_files
        if not has_clone_block(p.read_text(encoding="utf-8"), p.parent.parent.name)
    ]
    check(
        not bad_channels,
        "全系列渠道稿件含完整 clone 块",
        f"检查 {len(channel_files)} 份；缺：" + (", ".join(bad_channels) if bad_channels else "无"),
    )

    state = REPO_ROOT / "PIPELINE_STATE.md"
    current: Path | None = None
    if state.is_file():
        found = re.search(r"^current_piece:\s*UC(\d+)", state.read_text(encoding="utf-8"), re.M)
        if found:
            hits = sorted(usecases.glob(f"{found.group(1).zfill(2)}-*/article.md"))
            current = hits[0] if hits else None
    if current is None:
        check(False, "定位当前篇正文", "PIPELINE_STATE.md 的 current_piece 找不到对应目录")
    else:
        head = "\n".join(current.read_text(encoding="utf-8").splitlines()[:15])
        check(
            REPO_URL in head,
            "当前篇首屏含完整仓库 URL",
            current.relative_to(REPO_ROOT).as_posix(),
        )
        # The main-site copy may belong to an earlier piece when re-checking a
        # published slug, so validate its own cd target rather than the current one.
        post = site / "content" / "posts" / f"{slug}.md"
        if post.is_file():
            section = try_it_section(post.read_text(encoding="utf-8"))
            check(
                bool(re.search(re.escape(CLONE_LINE) + r"\ncd strands-in-action/usecases/[a-z0-9-]+", section)),
                "主站稿件含完整 clone 块",
                post.name,
            )

    # 5. Code block indentation. Pin 2026-11-11: the first code line starts at 0.
    #    Scan the whole series, not just the piece being published, so a past
    #    article cannot silently regress.
    bad_article_indent = indent_report(articles, REPO_ROOT)
    check(
        not bad_article_indent,
        "全系列正文代码块 0 缩进基线",
        f"检查 {len(articles)} 篇；违规："
        + (", ".join(bad_article_indent[:3]) if bad_article_indent else "无"),
    )

    all_channels = [
        p
        for p in sorted(usecases.glob("*/publish/*.md"))
        if p.name.lower() != "readme.md"
    ]
    bad_channel_indent = indent_report(all_channels, REPO_ROOT)
    check(
        not bad_channel_indent,
        "全系列渠道稿代码块 0 缩进基线",
        f"检查 {len(all_channels)} 份；违规："
        + (", ".join(bad_channel_indent[:3]) if bad_channel_indent else "无"),
    )

    post_path = site / "content" / "posts" / f"{slug}.md"
    bad_post_indent = indent_report([post_path], site) if post_path.is_file() else []
    check(
        not bad_post_indent,
        "主站稿件代码块 0 缩进基线",
        f"{post_path.name}；违规："
        + (", ".join(bad_post_indent[:3]) if bad_post_indent else "无"),
    )

    width = max(len(name) for _, name, _ in results)
    print(f"发布物料门禁 · {slug}")
    print(f"站点目录：{site}\n")
    for ok, name, detail in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name.ljust(width)}  {detail}")
    failed = [name for ok, name, _ in results if not ok]
    print()
    if failed:
        print(f"门禁未通过：{len(failed)} 项不满足 → {', '.join(failed)}")
        print("禁止发布、禁止把 PIPELINE_STATE.md 的 stage 改为 published。补齐后重跑本脚本。")
        return 1
    print(f"门禁通过：{len(results)}/{len(results)} 项。可以发布，并把 publish_gate 三个字段置为 true。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
