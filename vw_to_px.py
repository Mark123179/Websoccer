#!/usr/bin/env python3
"""Convert vw/vh units to fixed px at the Game Stage logical dimensions.

Stage base: 1884 x 1177.5 px (16:10 ratio scaled from 1440x900).
  1vw -> 18.84 px
  1vh -> 11.775 px

Preserves: cqw, cqh, svw, svh, dvw, dvh, lvw, lvh (container/dynamic units).
Operates in-place on the listed CSS files.
"""
import re
import sys
from pathlib import Path

VW_PX = 18.84
VH_PX = 11.775

FILES = [
    "game/static/game/css/global-dashboard/layout-nav.css",
    "game/static/game/css/global-dashboard/overview-dashboard.css",
    "game/static/game/css/global-dashboard/tables-lists.css",
    "game/static/game/css/player-profile.css",
    "game/static/game/css/trophy-cabinet.css",
    "game/static/game/css/tactics.css",
    "game/static/game/css/club-profile/layout.css",
    "game/static/game/css/club-profile/cards.css",
    "game/static/game/css/club-profile/identity.css",
    "game/static/game/css/club-profile/matches.css",
    "game/static/game/css/club-profile/players.css",
    "game/static/game/css/club-profile/trophies.css",
    "game/static/game/css/club-profile/compact-panels.css",
]

# Match numbers followed by vw or vh, NOT preceded by letters c/s/d/l (cqw, svw, dvw, lvw).
# (?<![a-zA-Z]) ensures we don't match `cqw`, `svw`, etc.
NUM_VW = re.compile(r'(?<![a-zA-Z])(-?\d+(?:\.\d+)?)vw\b')
NUM_VH = re.compile(r'(?<![a-zA-Z])(-?\d+(?:\.\d+)?)vh\b')


def fmt(value: float) -> str:
    # Round to 3 decimals, strip trailing zeros.
    s = f"{value:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def convert(text: str) -> tuple[str, int, int]:
    vw_count = 0
    vh_count = 0

    def repl_vw(m: re.Match) -> str:
        nonlocal vw_count
        vw_count += 1
        return f"{fmt(float(m.group(1)) * VW_PX)}px"

    def repl_vh(m: re.Match) -> str:
        nonlocal vh_count
        vh_count += 1
        return f"{fmt(float(m.group(1)) * VH_PX)}px"

    text = NUM_VW.sub(repl_vw, text)
    text = NUM_VH.sub(repl_vh, text)
    return text, vw_count, vh_count


def main() -> int:
    root = Path(__file__).resolve().parent
    total_vw = total_vh = 0
    for rel in FILES:
        path = root / rel
        if not path.exists():
            print(f"  SKIP missing: {rel}")
            continue
        original = path.read_text(encoding="utf-8")
        converted, nvw, nvh = convert(original)
        if converted != original:
            path.write_text(converted, encoding="utf-8")
        total_vw += nvw
        total_vh += nvh
        print(f"  {rel}: {nvw} vw, {nvh} vh")
    print(f"\nTotal: {total_vw} vw, {total_vh} vh converted")
    print(f"  1vw = {VW_PX}px, 1vh = {VH_PX}px (stage 1884 x 1177.5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
