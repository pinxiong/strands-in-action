"""Build publish/devto.md from article.md, unwrapping hard-wrapped lines.

Why: Dev.to (Forem) preserves a single newline inside a paragraph as a hard
line break. article.md wraps at ~95 characters for readability in the repo,
which is wider than the Dev.to column, so every source line spills its last
word or two onto a stub line. The rendered article then reads as a column of
ragged fragments. Hugo and Builder Center treat the same newline as a space,
so they are unaffected.

The fix is mechanical and content-neutral: join the continuation lines of each
paragraph, list item and blockquote into one line. Fenced code blocks, tables,
headings, images and raw HTML are left untouched. Code blocks need their
newlines, and a table row is already a line.

Usage:
    python tools/build_devto.py --check          # report only, write nothing
    python tools/build_devto.py --write          # rewrite every publish/devto.md
    python tools/build_devto.py --write usecases/04-sessions-state-memory

--check exits non-zero when a file would change, so it can gate a publish.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^(```|~~~)")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,2}\.)[ \t]+(.*)$")
BLOCK_START = ("|", "#", "![", "<")
RULE_LINES = {"---", "***", "___"}


def _split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.index("\n---", 3)
    return text[: end + 4], text[end + 4 :]


def _drop_h1(body: str) -> str:
    """The article H1 becomes the Dev.to title field, so drop it from the body."""
    text = body.lstrip("\n")
    if text.startswith("# "):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    return text


def unwrap(body: str) -> str:
    """Join hard-wrapped continuation lines inside paragraphs, items, quotes."""
    out: list[str] = []
    block: list | None = None  # [kind, parts, prefix]
    fence: str | None = None

    def flush() -> None:
        nonlocal block
        if block is None:
            return
        kind, parts = block[0], block[1]
        joined = " ".join(p for p in parts if p)
        if kind == "quote":
            out.append("> " + joined)
        elif kind == "item":
            out.append(block[2] + " " + joined)
        else:
            out.append(joined)
        block = None

    for raw in body.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        if fence is not None:
            out.append(line)
            if stripped.startswith(fence):
                fence = None
            continue

        if not stripped:
            flush()
            out.append("")
            continue

        if FENCE.match(stripped):
            flush()
            out.append(line)
            fence = stripped[:3]
            continue

        if stripped in RULE_LINES or stripped.startswith(BLOCK_START):
            flush()
            out.append(line)
            continue

        if stripped.startswith(">"):
            content = stripped.lstrip(">").strip()
            if block is not None and block[0] == "quote":
                block[1].append(content)
            else:
                flush()
                block = ["quote", [content]]
            continue

        item = LIST_ITEM.match(line)
        if item:
            flush()
            block = ["item", [item.group(3)], item.group(1) + item.group(2)]
            continue

        if block is None:
            block = ["para", [stripped]]
        else:
            block[1].append(stripped)

    flush()
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n") + "\n"


def squash(text: str) -> str:
    """Comparison key: every non-space character, so only layout may differ.

    Blockquote markers are dropped first: a wrapped quote repeats "> " on every
    source line while an unwrapped one carries a single marker, and that
    difference is layout, not content.
    """
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    return re.sub(r"\s+", "", text)


def strip_image_urls(text: str) -> str:
    """Image paths differ per channel, so compare the prose, not the URLs."""
    return re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"![\1]()", text)


def build(article: Path, write: bool) -> tuple[str, bool, bool, bool]:
    """Return (name, layout_only_change, in_sync_with_article, needs_write).

    The transform runs on publish/devto.md itself, never on article.md: the
    published image URLs are channel-specific (UC01 uses the site slug as its
    image directory), so rebuilding the body from the source would rewrite them.
    """
    devto = article.parent / "publish" / "devto.md"
    old_text = devto.read_text(encoding="utf-8")
    front_matter, old_body = _split_front_matter(old_text)

    new_body = unwrap(old_body)
    layout_only = squash(new_body) == squash(old_body)

    _, source_body = _split_front_matter(article.read_text(encoding="utf-8"))
    source_body = _drop_h1(source_body)
    in_sync = squash(strip_image_urls(new_body)) == squash(strip_image_urls(source_body))

    rebuilt = front_matter + "\n\n" + new_body
    needs_write = old_text.strip() != rebuilt.strip()

    if write and needs_write:
        devto.write_text(rebuilt, encoding="utf-8")

    return article.parent.name, layout_only, in_sync, needs_write


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="*", help="usecase directories")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.targets:
        articles = [Path(t).resolve() / "article.md" for t in args.targets]
    else:
        articles = sorted(REPO.glob("usecases/*/article.md"))

    changed = 0
    problems = 0
    for article in articles:
        name, layout_only, in_sync, needs = build(article, write=args.write)
        layout_flag = "layout only" if layout_only else "CONTENT CHANGED"
        sync_flag = "in sync" if in_sync else "DRIFTED FROM article.md"
        state = "rewritten" if (args.write and needs) else ("would rewrite" if needs else "already clean")
        print(f"{name:38} {layout_flag:15} {sync_flag:24} {state}")
        changed += int(needs)
        problems += int(not layout_only or not in_sync)

    if problems:
        print(f"\n{problems} file(s) failed verification; nothing should be published")
        return 2
    if not args.write:
        print(f"\n{changed} file(s) would be rewritten")
        return 1 if changed else 0
    print(f"\n{changed} file(s) rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
