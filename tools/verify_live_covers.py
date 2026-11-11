#!/usr/bin/env python3
"""Verify that every AUTOMATED channel really serves the dark series cover.

Pin 2026-11-11: rebuilding cover PNGs locally is not the same as replacing the
hero image on already-published articles. Builder Center keeps its own asset in
prod-assets.cosmic.aws.dev, Dev.to caches its image proxy, and the Hugo site
keeps the file name. After any cover rebuild, run this for every published
piece and fix whatever reports FAIL before closing the task.

Usage:
  .venv/bin/python tools/verify_live_covers.py \
      --site  https://xiongpin.dev/posts/<slug>/ \
      --devto https://dev.to/aws-builders/<slug-article> \
      --bc    https://builder.aws.com/content/<id>/<slug>

Medium has no API and its editor does not initialise in the automation browser,
so it is reported as MANUAL, never silently as PASS.
"""
from __future__ import annotations

import argparse, base64, html, io, json, re, sys, urllib.request
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"}
ALLOWED_SIZES = {(1400, 788), (1200, 504)}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read()


def og_image(page: str) -> str:
    text = fetch(page).decode("utf-8", "ignore")
    m = (re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
         or re.search(r'<meta[^>]*content="([^"]+)"[^>]*property="og:image"', text))
    return html.unescape(m.group(1)) if m else ""


def check_pixels(url: str, label: str) -> bool:
    try:
        im = Image.open(io.BytesIO(fetch(url))).convert("RGB")
        corner = im.getpixel((10, 10))
        mid = im.getpixel((im.width // 2, im.height // 2))
        dark = corner[0] < 45 and corner[1] < 80 and corner[2] > 45 and mid[0] < 45
        ok = dark and im.size in ALLOWED_SIZES
        print(f"{'PASS' if ok else 'FAIL'} {label}: {im.size} corner={corner} "
              f"mid={mid} dark={dark} {url[:150]}")
        return ok
    except Exception as exc:
        print(f"FAIL {label}: cannot read {url[:150]}: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="published xiongpin.dev post URL")
    ap.add_argument("--devto", required=True, help="published Dev.to article URL")
    ap.add_argument("--bc", required=True, help="published Builder Center article URL")
    a = ap.parse_args()

    results = []
    for label, page in (("SITE", a.site), ("DEVTO", a.devto)):
        og = og_image(page)
        results.append((label, bool(og) and check_pixels(og, label)))

    bc_og = og_image(a.bc)
    hero = ""
    if "og-images" in bc_og and "d=" in bc_og:
        d = re.search(r"[?&]d=([^&]+)", bc_og)
        if d:
            raw = base64.urlsafe_b64decode(d.group(1) + "=" * (-len(d.group(1)) % 4))
            hero = json.loads(raw.decode()).get("hero", "")
    results.append(("BC", bool(hero) and check_pixels(hero, "BC")))

    print("MANUAL MEDIUM: no public API; replace the first inline image in the "
          "story editor with static/images/<slug>/cover-medium.png, then "
          "Save and publish. Verify og:image changes afterwards.")
    bad = [name for name, ok in results if not ok]
    print("RESULT:", "ALL AUTOMATED CHANNELS PASS" if not bad
          else "FAILED: " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
