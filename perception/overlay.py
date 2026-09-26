"""
overlay.py — everything drawn on a frame, in one place.

Colours are shared with the web UI's
vocabulary chips on purpose: a relation that is yellow-green in the video must be
yellow-green in the panel, or the two views cannot be read together.
"""
from __future__ import annotations

import cv2
import numpy as np

# VOCAB is the 11-row relation table (docs/relation_table.md). shot_trace names
# rows from it, which is what keeps a story's caption in the same vocabulary the
# planner compiled against.
from planning.planner import VOCAB
from perception.gaze import (draw_text, draw_box, draw_arrow, draw_circle,
                             draw_panel, C_GREEN, C_RED, C_YELLOW, C_ORANGE,
                             C_MAGENTA, C_CYAN, C_WHITE)



C_SKEL = (90, 255, 30)

# THE RELATION RIBBON IS GONE, deliberately and not behind a flag.
#
# It printed rows 1-11 as `1 gaze 2 joint 3 eye ...` across the bottom of the
# frame, lit as each fired. The trouble was never the drawing, it was that it
# was drawn INTO the frame: one annotated stream feeds the developer page and
# the visitor's tablet alike, so eleven abbreviations from a vocabulary nobody
# in the room has read ended up over the bottom of the picture a visitor was
# looking at.
#
# Nothing was lost. The developer page renders the same eleven rows as HTML
# chips, lit per frame from the same truth map, and the tablet shows the one
# rule that matters in the same words. Both are legible; this was not.
#
# A flag was the obvious fix and the wrong one: a debug view that reaches the
# audience by default, kept alive by a switch nobody remembers on the day, is
# the failure again with an extra step in front of it.

def make_strip(shots, height=None):
    """The comic strip: N shots -> one horizontal story image.

    `height=None` keeps the camera's own resolution. It used to default to 300,
    which threw away four fifths of every panel on the way to disk: the shots
    arrive at 1280x720 and were saved 533x300. Nothing needed them small -- the
    card thumbnail is resized separately in `feed.publish`, and the browser
    scales with CSS -- so the loss showed up only later, when someone tried to
    enlarge a panel during the review phase and found there was nothing behind
    the pixels.

    A 5-panel strip is about 400 KB at native size against 90 KB before. The
    in-memory cache in `feed.publish` holds twenty of them, so roughly 8 MB.
    """
    if height is None:
        height = max(s.shape[0] for s in shots)
    tiles = []
    for s in shots:
        h, w = s.shape[:2]
        tiles.append(s if h == height
                     else cv2.resize(s, (max(1, int(w * height / h)), height)))
    return np.hstack(tiles)

def shot_trace(truth, viz):
    """One panel's GROUNDED detection summary (what the system actually saw this frame), so the
    story description is narrated from the real detected sequence — not re-captioned off a photo."""
    dets = viz.get("dets", [])
    parts, seen = [], set()
    for relname, h in viz.get("hits", []):              # gazing-at / pointing-at (have a target)
        di = h.get("det") if isinstance(h, dict) else None
        tgt = dets[di].label if isinstance(di, int) and 0 <= di < len(dets) else ""
        key = f"{relname} {tgt}".strip()
        if key not in seen:
            seen.add(key); parts.append(key)
    hit_names = {relname for relname, _ in viz.get("hits", [])}
    for i, on in truth.items():                         # truth-only rows (proxemic, approach, hands-on…)
        if on:
            nm = VOCAB.get(i, str(i)).split("—")[0].strip()
            if nm not in hit_names and nm not in seen:
                seen.add(nm); parts.append(nm)
    return ", ".join(parts) if parts else "quiet"