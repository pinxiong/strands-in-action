#!/usr/bin/env python3
"""Render a Markdown article into a self-contained HTML preview page.

Local preview only. Nothing here publishes anything.

Usage:
    python tools/make_preview.py usecases/01-the-loop/article.md \
        --title "The Agent That Wouldn't Start" \
        --subtitle "Verified on 2026-11-01 against strands-agents 1.63.0..." \
        --tags ai,agents,strands,aws \
        --canonical "https://xiongpin.dev/posts/the-agent-that-wouldnt-start/" \
        --slug the-loop

Defaults: output is <article dir>/preview.html, images resolve to ./images/.
"""

import argparse
import datetime
import html
import os
import re
import subprocess
import sys

# Light-theme syntax colours for pandoc's short token classes
# (kw keyword, cf control flow, dt type, st string, co comment, fu function ...).
HIGHLIGHT_CSS = """
  pre.sourceCode span.kw, pre.sourceCode span.cf { color: #0550ae; font-weight: 600; }
  pre.sourceCode span.dt, pre.sourceCode span.bu, pre.sourceCode span.ex { color: #953800; }
  pre.sourceCode span.dv, pre.sourceCode span.fl, pre.sourceCode span.at { color: #0550ae; }
  pre.sourceCode span.st, pre.sourceCode span.vs, pre.sourceCode span.ch { color: #0a7d32; }
  pre.sourceCode span.co { color: #6b747d; font-style: italic; }
  pre.sourceCode span.fu { color: #0b7285; }
  pre.sourceCode span.im, pre.sourceCode span.va { color: #953800; }
  pre.sourceCode span.op { color: #444c56; }
  pre.sourceCode span.sc, pre.sourceCode span.ss { color: #0a7d32; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --ink: #1f2328;
    --ink-soft: #4b535c;
    --line: #dfe4ea;
    --accent: #2f6fb0;
    --accent-soft: #eef4fb;
    --code-bg: #f6f8fa;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px 20px 96px;
    background: #ffffff;
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
                 "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 17px;
    line-height: 1.75;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; }}

  .meta {{
    background: var(--accent-soft);
    border: 1px solid #d3e3f4;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 36px;
    font-size: 14.5px;
    line-height: 1.6;
    color: var(--ink-soft);
  }}
  .meta h2 {{
    margin: 0 0 12px;
    font-size: 13px;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 700;
  }}
  .meta dl {{ margin: 0; display: grid; grid-template-columns: 132px 1fr; gap: 6px 14px; }}
  .meta dt {{ color: #7b858f; }}
  .meta dd {{ margin: 0; color: var(--ink); word-break: break-word; }}
  .tag {{
    display: inline-block;
    background: #ffffff;
    border: 1px solid #cddff2;
    color: var(--accent);
    border-radius: 999px;
    padding: 1px 10px;
    margin-right: 6px;
    font-size: 13px;
  }}

  h1 {{
    font-size: 34px;
    line-height: 1.25;
    letter-spacing: -.01em;
    margin: 0 0 18px;
  }}
  h2 {{
    font-size: 24px;
    margin: 46px 0 14px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--line);
  }}
  h3 {{ font-size: 19px; margin: 30px 0 10px; }}
  p {{ margin: 0 0 18px; }}
  a {{ color: var(--accent); }}

  blockquote {{
    margin: 0 0 26px;
    padding: 2px 0 2px 18px;
    border-left: 3px solid #cddff2;
    color: var(--ink-soft);
    font-size: 16px;
  }}
  blockquote p {{ margin: 8px 0; }}

  ul, ol {{ margin: 0 0 18px; padding-left: 24px; }}
  li {{ margin-bottom: 8px; }}

  code {{
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                 "Liberation Mono", monospace;
    font-size: 14px;
  }}
  p code, li code, td code {{
    background: var(--code-bg);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 1px 5px;
  }}
  pre {{
    background: var(--code-bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 0 0 22px;
    line-height: 1.55;
  }}
  pre code {{ background: none; border: 0; padding: 0; font-size: 13.5px; }}

  figure {{ margin: 28px 0; }}
  figure img {{
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 8px;
    display: block;
  }}
  figcaption {{
    margin-top: 8px;
    font-size: 14px;
    color: #6b747d;
    text-align: center;
    line-height: 1.55;
  }}

  table {{ border-collapse: collapse; width: 100%; margin: 0 0 22px; font-size: 15.5px; }}
  th, td {{ border: 1px solid var(--line); padding: 8px 12px; text-align: left; }}
  th {{ background: var(--code-bg); }}

  hr {{ border: 0; border-top: 1px solid var(--line); margin: 40px 0; }}

{highlight_css}
</style>
</head>
<body>
<div class="wrap">
<div class="meta">
  <h2>Local preview &mdash; not published</h2>
  <dl>
    <dt>Title</dt><dd>{title}</dd>
    <dt>Subtitle</dt><dd>{subtitle}</dd>
    <dt>Tags</dt><dd>{tags_html}</dd>
    <dt>Canonical</dt><dd>{canonical}</dd>
    <dt>Generated</dt><dd>{generated} &middot; from <code>{source}</code></dd>
    <dt>Images</dt><dd>{image_note}</dd>
  </dl>
</div>

{body}
</div>
</body>
</html>
"""


def read_first_heading(md_path: str) -> str:
    with open(md_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(md_path)


def read_verified_blockquote(md_path: str) -> str:
    """First blockquote line, flattened: used as the default subtitle."""
    lines = []
    with open(md_path, encoding="utf-8") as fh:
        started = False
        for line in fh:
            if line.startswith("> "):
                started = True
                lines.append(line[2:].strip())
            elif started:
                break
    return " ".join(lines)


def run(cmd: list) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return proc.stdout


def build(md_path, out_path, title, subtitle, tags, canonical, slug):
    md_path = os.path.abspath(md_path)
    md_dir = os.path.dirname(md_path)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    rel_img = os.path.relpath(os.path.join(md_dir, "images"), out_dir)

    body = run([
        "pandoc", md_path, "-f", "markdown", "-t", "html",
        "--highlight-style=pygments",
        "--wrap=none",  # keep h1/h2 on one line; pandoc folds them at 72 columns otherwise
    ])

    # Online absolute image paths -> local relative paths for preview.
    body = re.sub(r'src="/images/[^/]+/', f'src="{rel_img}/', body)
    body = re.sub(r'src="(?!(?:https?:|data:|\.))/?images/', f'src="{rel_img}/', body)

    highlight_css = HIGHLIGHT_CSS

    tags_html = " ".join(
        f'<span class="tag">#{html.escape(t.strip())}</span>' for t in tags.split(",") if t.strip()
    )

    local_img_count = len(re.findall(r"<img ", body))
    image_note = (
        f"{local_img_count} image(s), loaded from <code>{rel_img}/</code> "
        f"&mdash; keep this file next to that folder"
    )

    page = TEMPLATE.format(
        title=html.escape(title),
        subtitle=html.escape(subtitle),
        tags_html=tags_html,
        canonical=html.escape(canonical) if canonical else "(not set yet)",
        generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        source=os.path.relpath(md_path, start=os.path.dirname(os.path.abspath(out_path))),
        image_note=image_note,
        highlight_css=highlight_css,
        body=body,
    )

    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"wrote {out_path}  ({len(page)} bytes, {local_img_count} images)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--tags", default="ai,agents")
    ap.add_argument("--canonical", default=None)
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()

    md = args.md
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(md)), "preview.html")
    title = args.title or read_first_heading(md)
    subtitle = args.subtitle or read_verified_blockquote(md)
    canonical = args.canonical
    if not canonical and args.slug:
        canonical = f"https://xiongpin.dev/posts/{args.slug}/"

    build(md, out, title, subtitle, args.tags, canonical, args.slug)


if __name__ == "__main__":
    main()
