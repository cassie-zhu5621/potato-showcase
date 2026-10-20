#!/usr/bin/env python3
"""
make_decision_strip.py — the five sweep views, each with its score, and the one
the robot chose.

  python3 robot/tools/make_decision_strip.py <sweep_dir> out.jpg

WHAT THIS SHOWS. How the angle is decided, which `panorama.jpg` never did -- it
is a squashed contact sheet with no numbers on it. The rule, from
`planning/station_score.py`:

    score = 100 x (boxes of the object the rule names)
          +   3 x (focus boxes)
          +   1 x (context boxes)

The 100 is the whole decision whenever the named object is seen anywhere: a
person will walk over to the plant, and the plant will never walk over to the
person, so the robot aims at the half that cannot come to it. People and
furniture only break ties -- and decide everything when the object was boxed
nowhere, which is worth seeing too.

THE NUMBERS ARE RECOMPUTED BY THE SAME FUNCTION THE ROBOT USED, from the boxes
it recorded, and checked against the score it wrote down that day. If they
disagree this refuses to draw: a figure explaining a decision with numbers that
did not produce it would be worse than no figure.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from PIL import Image, ImageDraw, ImageFont

from planning.station_score import (ANCHOR_WEIGHT, CONTEXT_POINTS,
                                    FOCUS_POINTS, _anchor_hits, spec_anchors,
                                    station_score)


def _font(size):
    for f in ("/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def breakdown(dets, anchors, provider):
    """-> (score, text) for one station, using the robot's own function."""
    boxes = [(d["label"], d.get("tier", "context"), d.get("box")) for d in dets]
    sc = station_score(boxes, provider=provider, anchors=anchors)
    a = _anchor_hits(boxes, anchors)
    f = sum(1 for _, t, _ in boxes if t == "focus")
    c = len(boxes) - f
    parts = []
    if a:
        parts.append(f"{'/'.join(anchors)} x{a} = {a * ANCHOR_WEIGHT}")
    if f:
        parts.append(f"focus x{f} = {f * FOCUS_POINTS}")
    if c:
        parts.append(f"context x{c} = {c * CONTEXT_POINTS}")
    return sc, ("  +  ".join(parts) if parts else "nothing boxed")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: make_decision_strip.py <sweep_dir> out.jpg")
    sweep, out = sys.argv[1], sys.argv[2]
    plan = json.load(open(os.path.join(sweep, "plan.json")))
    anchors = spec_anchors(plan.get("watch_spec"))
    provider = plan.get("provider") or "gemini"
    shots = sorted(plan["shots"], key=lambda s: s["pan"])

    rows = []
    for s in shots:
        sc, why = breakdown(s.get("dets") or [], anchors, provider)
        rows.append((s, sc, why))
    best = max(rows, key=lambda r: r[1])
    # Same tie-break the robot used: first station in sweep order wins a tie.
    for r in rows:
        if r[1] == best[1]:
            best = r
            break

    if best[1] != plan["richest_score"] or best[0]["pan"] != plan["richest_pan"]:
        sys.exit(f"recomputed {best[1]} at {best[0]['pan']:+d}, but the robot "
                 f"recorded {plan['richest_score']} at "
                 f"{plan['richest_pan']:+d}. Refusing to draw a decision with "
                 f"numbers that did not make it.")

    ims = [Image.open(os.path.join(sweep, s["file"])).convert("RGB")
           for s, _, _ in rows]
    w, h = ims[0].size
    gap, band = max(4, w // 120), int(h * 0.30)
    W = w * len(ims) + gap * (len(ims) - 1)
    strip = Image.new("RGB", (W, h + band), (255, 255, 255))
    d = ImageDraw.Draw(strip)
    big, small = _font(int(band * 0.34)), _font(int(band * 0.15))

    for i, ((s, sc, why), im) in enumerate(zip(rows, ims)):
        x = i * (w + gap)
        strip.paste(im, (x, 0))
        chosen = s is best[0]
        if chosen:
            t = max(8, w // 90)
            d.rectangle([x, 0, x + w - 1, h - 1], outline=(255, 205, 0), width=t)
        col = (20, 20, 20) if chosen else (140, 140, 140)
        d.text((x + gap * 2, h + band * 0.06), f"{s['pan']:+d}°   {sc}",
               fill=col, font=big)
        d.text((x + gap * 2, h + band * 0.52), why, fill=col, font=small)
        if chosen:
            d.text((x + gap * 2, h + band * 0.74), "→ watch here",
                   fill=(200, 140, 0), font=small)

    strip.save(out, quality=95)
    print(f"{out}  {W}x{h + band}")
    print(f"  anchors {anchors or '(none -- the rule names no object)'}  "
          f"chose {best[0]['pan']:+d} with {best[1]} -- matches the record")
    for s, sc, why in rows:
        print(f"    {s['pan']:+4d}  {sc:>4}  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
