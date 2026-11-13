#!/usr/bin/env python3
"""Build the three cover sizes for a Strands in Action article.

The dark cover used by UC01-UC04 is the series baseline (see
usecases/04-sessions-state-memory/publish-assets/cover.svg). UC05 and UC06
shipped with a light #f8fafc layout that no longer matched the series; this
generator makes the baseline the single source of truth so a new instalment
cannot drift again.

Usage (resvg-py lives in the project venv):
    .venv/bin/python tools/build_covers.py                 # all configured covers
    .venv/bin/python tools/build_covers.py --slug orchestrating-swarm
    .venv/bin/python tools/build_covers.py --check       # verify SVG + PNG only

Outputs, per slug, under pinxiong.github.io/static/images/<slug>/:
    cover.svg / cover.png                 1600x900 -> 1400x788   (site og:image)
    cover-devto.svg / cover-devto.png    1600x672 -> 1200x504   (Dev.to)
    cover-medium.svg / cover-medium.png 1400x788 -> 1400x788   (Medium, 16:9)
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SITE = REPO.parent / "pinxiong.github.io"


# --- series baseline, taken verbatim from the UC01-UC04 dark covers --------
FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, Menlo, monospace"
BG_STOPS = ('<stop offset="0" stop-color="#0b2547"/>', '<stop offset="1" stop-color="#14407c"/>')


def frame(w: int, h: int, num: int, body: str, *, scale_inner: bool = False) -> str:
    """Dark canvas + two corner circles + optional 0.875-scaled 1600x900 scene."""
    gid, mid = f"bgDark{num}", f"covArr{num}"
    if scale_inner:
        # Medium is 1400x788: keep the whole 1600x900 scene proportional.
        circles = (
            '  <circle cx="1520" cy="60" r="320" fill="#16407a"/>\n'
            '  <circle cx="40" cy="880" r="260" fill="#103258"/>\n'
        )
        inner = f'<g transform="scale({w / 1600:g})">\n{circles}{body}\n</g>'
    else:
        tall = h > 700
        cx1, cy1, r1 = (1520, 60, 320) if tall else (1560, -40, 280)
        cx2, cy2, r2 = (40, 880, 260) if tall else (30, 700, 220)
        circles = (
            f'  <circle cx="{cx1}" cy="{cy1}" r="{r1}" fill="#16407a"/>\n'
            f'  <circle cx="{cx2}" cy="{cy2}" r="{r2}" fill="#103258"/>\n'
        )
        inner = circles + body
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FONT}">
  <defs>
    <linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">
      {BG_STOPS[0]}
      {BG_STOPS[1]}
    </linearGradient>
    <marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#7db4ff"/>
    </marker>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#{gid})"/>
{inner}
</svg>
"""


def headline(lines: list[tuple[str, bool]], ys: list[int], size: int, x: int = 108) -> str:
    """White title with one #7db4ff highlighted line, as in UC01/UC04."""
    out = []
    for (text, hi), y in zip(lines, ys):
        colour = "#7db4ff" if hi else "#ffffff"
        out.append(f'  <text x="{x}" y="{y}" font-size="{size}" font-weight="800" fill="{colour}">{text}</text>')
    return "\n".join(out)


def sublines(lines: list[str], ys: list[int], size: int) -> str:
    return "\n".join(
        f'  <text x="110" y="{y}" font-size="{size}" fill="#c3d6f2">{text}</text>'
        for text, y in zip(lines, ys)
    )


def footer(y: int, size: int, num: int) -> str:
    return (
        f'  <text x="110" y="{y}" font-family="{MONO}" font-size="{size}" fill="#8fb3e3">'
        f"strands-agents 1.63.0 · every claim verified by running it</text>"
    )


def tag(y: int, w: int, h: int, rx: int, size: int, num: int, text_y: int) -> str:
    cx = 110 + w / 2
    return (
        f'  <rect x="110" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#1d4ed8"/>\n'
        f'  <text x="{cx:g}" y="{text_y}" font-size="{size}" font-weight="700" fill="#ffffff" '
        f'text-anchor="middle" letter-spacing="2.5">STRANDS IN ACTION · {num:02d}</text>'
    )


# --- per-article content ---------------------------------------------------
UC05_VISUAL = f"""
  <!-- right visual: the delayed commit race, trial 1 of 5 -->
  <rect x="950" y="150" width="470" height="180" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="985" y="190" font-family="{MONO}" font-size="17" fill="#8fb3e3">expiry  1.003s  capacity released</text>
  <text x="985" y="222" font-family="{MONO}" font-size="17" fill="#8fb3e3">retry   1.407s  commit lands</text>
  <text x="985" y="254" font-family="{MONO}" font-size="17" fill="#8fb3e3">old     2.405s  commit lands again</text>
  <text x="985" y="286" font-family="{MONO}" font-size="17" fill="#ffffff">effects=2  duplicates=1</text>
  <text x="985" y="316" font-size="13" fill="#5f83b8" font-family="{MONO}">naive reconciler, trial 1 of 5</text>

  <line x1="1185" y1="330" x2="1185" y2="412" stroke="#7db4ff" stroke-width="2.5" marker-end="url(#covArr5)"/>

  <rect x="950" y="420" width="225" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1062" y="464" font-size="30" font-weight="700" fill="#9cc2ff" text-anchor="middle">5</text>
  <text x="1062" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">duplicate writes, naive</text>

  <rect x="1195" y="420" width="255" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1322" y="464" font-size="30" font-weight="700" fill="#ffffff" text-anchor="middle">0</text>
  <text x="1322" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">duplicates, terminal state</text>

  <!-- takeaway chip -->
  <rect x="950" y="576" width="470" height="92" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1185" y="616" font-size="21" font-weight="600" fill="#ffffff" text-anchor="middle">"Not found" is not an outcome</text>
  <text x="1185" y="646" font-family="{MONO}" font-size="16" fill="#8fb3e3" text-anchor="middle">hold the reservation until a terminal state</text>
"""

UC06_VISUAL = f"""
  <!-- right visual: a handoff chain with no scheduler -->
  <rect x="950" y="150" width="470" height="180" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="985" y="190" font-family="{MONO}" font-size="17" fill="#8fb3e3">researcher &#8594; handoff_to_agent</text>
  <text x="985" y="222" font-family="{MONO}" font-size="17" fill="#8fb3e3">calculator &#8594; handoff_to_agent</text>
  <text x="985" y="254" font-family="{MONO}" font-size="17" fill="#8fb3e3">writer     &#8594; silence</text>
  <text x="985" y="286" font-family="{MONO}" font-size="17" fill="#ffffff">no scheduler, no route table</text>
  <text x="985" y="316" font-size="13" fill="#5f83b8" font-family="{MONO}">three agents, one shared task</text>

  <line x1="1185" y1="330" x2="1185" y2="412" stroke="#7db4ff" stroke-width="2.5" marker-end="url(#covArr6)"/>

  <rect x="950" y="420" width="225" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1062" y="464" font-size="30" font-weight="700" fill="#9cc2ff" text-anchor="middle">3</text>
  <text x="1062" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">agents, one shared task</text>

  <rect x="1195" y="420" width="255" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1322" y="464" font-size="30" font-weight="700" fill="#ffffff" text-anchor="middle">0</text>
  <text x="1322" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">orchestrators in the runtime</text>

  <!-- takeaway chip -->
  <rect x="950" y="576" width="470" height="92" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1185" y="616" font-size="21" font-weight="600" fill="#ffffff" text-anchor="middle">silence ends the swarm</text>
  <text x="1185" y="646" font-family="{MONO}" font-size="16" fill="#8fb3e3" text-anchor="middle">completed means nobody asked for help</text>
"""

UC07_VISUAL = f"""
  <!-- right visual: predicate evaluations and a join that ran twice -->
  <rect x="950" y="150" width="470" height="180" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="985" y="190" font-family="{MONO}" font-size="17" fill="#8fb3e3">condition(state) &#8594; bool</text>
  <text x="985" y="222" font-family="{MONO}" font-size="17" fill="#8fb3e3">model calls at eval  2 / 2 / 0</text>
  <text x="985" y="254" font-family="{MONO}" font-size="17" fill="#8fb3e3">order  A, join, B, join</text>
  <text x="985" y="286" font-family="{MONO}" font-size="17" fill="#ffffff">one parent is enough to fire</text>
  <text x="985" y="316" font-size="13" fill="#5f83b8" font-family="{MONO}">strands-agents 1.63.0, us-east-1</text>

  <line x1="1185" y1="330" x2="1185" y2="412" stroke="#7db4ff" stroke-width="2.5" marker-end="url(#covArr7)"/>

  <rect x="950" y="420" width="225" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1062" y="464" font-size="30" font-weight="700" fill="#9cc2ff" text-anchor="middle">3</text>
  <text x="1062" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">predicate evals, one edge</text>

  <rect x="1195" y="420" width="255" height="96" rx="12" fill="#1a4a8f" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1322" y="464" font-size="30" font-weight="700" fill="#ffffff" text-anchor="middle">2</text>
  <text x="1322" y="492" font-size="13.5" fill="#9cc2ff" text-anchor="middle">times the join ran</text>

  <!-- takeaway chip -->
  <rect x="950" y="576" width="470" height="92" rx="14" fill="#123a6b" stroke="#4f8ff7" stroke-width="2"/>
  <text x="1185" y="616" font-size="21" font-weight="600" fill="#ffffff" text-anchor="middle">structure is yours, input is not</text>
  <text x="1185" y="646" font-family="{MONO}" font-size="16" fill="#8fb3e3" text-anchor="middle">set a cap and prove that it converges</text>
"""

COVERS = {
    "reservations-fencing": {
        "num": 5,
        "title": [('When "Not Found"', False), ("Doesn't Mean", False), ('"Never Happened"', True)],
        "subtitle": [
            "Leases, idempotency keys and fences, when a quota",
            "is shared by many workers.",
        ],
        "visual": UC05_VISUAL,
    },
    "orchestrating-swarm": {
        "num": 6,
        "title": [("Nobody Decides", False), ("Who Goes", False), ("Next", True)],
        "subtitle": [
            "The routing decision is one tool call.",
            "Silence ends the swarm, not the task.",
        ],
        "visual": UC06_VISUAL,
    },
    "orchestrating-graph": {
        "num": 7,
        "title": [("The Graph", False), ("Is Yours, the", False), ("Judgment Isn't", True)],
        "subtitle": [
            "Routing is a Python predicate, not a model call.",
            "A join is an OR, and a cycle is unbounded by default.",
        ],
        "visual": UC07_VISUAL,
    },
}


def site_body(cfg: dict) -> str:
    n = cfg["num"]
    return "\n".join([
        tag(104, 300, 40, 20, 17, n, 130),
        "  <!-- title -->",
        headline(cfg["title"], [316, 400, 484], 68),
        "  <!-- subtitle -->",
        sublines(cfg["subtitle"], [556, 592], 25),
        "  <!-- footer -->",
        footer(796, 19, n),
        cfg["visual"],
    ])


def devto_body(cfg: dict) -> str:
    n = cfg["num"]
    return "\n".join([
        tag(72, 280, 36, 18, 15, n, 96),
        "  <!-- title -->",
        headline(cfg["title"], [200, 272, 344], 54),
        "  <!-- subtitle -->",
        sublines(cfg["subtitle"], [402, 436], 23),
        "  <!-- footer -->",
        footer(596, 17, n),
        f'  <g transform="translate(410, 40) scale(0.72)">{cfg["visual"]}</g>',
    ])


def svg_for(slug: str, kind: str) -> str:
    cfg = COVERS[slug]
    n = cfg["num"]
    if kind == "cover":
        return frame(1600, 900, n, site_body(cfg))
    if kind == "cover-devto":
        return frame(1600, 672, n, devto_body(cfg))
    if kind == "cover-medium":
        # Gate requires the literal viewBox 0 0 1400 788; scale the 1600x900 body.
        return frame(1400, 788, n, site_body(cfg), scale_inner=True)
    raise ValueError(kind)


TARGETS = {
    "cover": (1600, 900, 1400, 788),
    "cover-devto": (1600, 672, 1200, 504),
    "cover-medium": (1400, 788, 1400, 788),
}


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        head = path.read_bytes()[:24]
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", head[16:24])
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", choices=sorted(COVERS))
    ap.add_argument("--check", action="store_true", help="verify rendered PNG sizes only")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else sorted(COVERS)
    failures = []

    for slug in slugs:
        out_dir = SITE / "static" / "images" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        for kind, (_, _, want_w, want_h) in TARGETS.items():
            svg_path, png_path = out_dir / f"{kind}.svg", out_dir / f"{kind}.png"
            if not args.check:
                svg_path.write_text(svg_for(slug, kind), encoding="utf-8")
                try:
                    import resvg_py

                    png_path.write_bytes(resvg_py.svg_to_bytes(svg_path=str(svg_path), width=want_w))
                except ImportError:
                    print("resvg-py missing; run with .venv/bin/python", file=sys.stderr)
                    return 1
            svg_ok = svg_path.is_file() and all(s in svg_path.read_text(encoding="utf-8") for s in BG_STOPS)
            got = png_size(png_path)
            ok = svg_ok and got == (want_w, want_h)
            print(f"{'PASS' if ok else 'FAIL'}  {slug}/{kind}  png={got}  want={want_w}x{want_h}  dark_svg={svg_ok}")
            if not ok:
                failures.append(f"{slug}/{kind}")
    print(f"\n{'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
