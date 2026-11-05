"""E6: count the deprecated tools on your own machine.

Counts strands_tools modules carrying _DEPRECATION_MESSAGE and lists the
vended_tools replacements. No API call needed.
"""
import pathlib
import sys

SITE_PACKAGES = pathlib.Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
tools_dir = SITE_PACKAGES / "strands_tools"
vended_dir = SITE_PACKAGES / "strands" / "vended_tools"

deprecated = sorted(
    p.stem for p in tools_dir.glob("*.py")
    if p.stem != "__init__" and "_DEPRECATION_MESSAGE" in p.read_text()
)
total = sorted(
    p.stem for p in tools_dir.glob("*.py")
    if p.stem != "__init__" and not p.stem.startswith("_")
)
vended = sorted(
    p.stem for p in vended_dir.iterdir()
    if p.stem != "__init__" and not p.stem.startswith("_")
)

print("STRANDS_TOOLS_MODULES :", len(total))
print("DEPRECATED_COUNT      :", len(deprecated))
print("VENDED_COUNT          :", len(vended))
print()
print("DEPRECATED:", ", ".join(deprecated))
print()
print("VENDED    :", ", ".join(vended))
