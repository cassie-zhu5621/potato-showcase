#!/usr/bin/env python3
"""
make_filmstrip.py — the five sweep views in a row, at their own aspect ratio.

  python3 robot/tools/make_filmstrip.py <dir-of-view_*.jpg> out.jpg

DO NOT USE `panorama.jpg` IN A FIGURE. It is a 3x2 contact sheet built for the
researcher -- `sweep_plan.py` says so: "local researcher-grid cell size (not
Gemini input)" -- and its cells are 480x360. The frames are 1280x720. So every
view in it is squashed from 16:9 into 4:3, by 33%, and a room photographed
that way looks subtly wrong in a way nobody can name.

A row, not a grid, and at native aspect: the sweep IS a row -- five angles left
to right -- so the grid was never the shape of the thing either.
"""
import os
import sys

from PIL import Image, ImageDraw


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().split("\n")[2].strip())
    src, out = sys.argv[1], sys.argv[2]
    order = ["-060", "-030", "+000", "+030", "+060"]
    paths = [os.path.join(src, f"view_{a}.jpg") for a in order]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        # Fall back to the tier-boxed set, which is the other thing in a
        # figure folder worth strip-ing.
        paths = [os.path.join(src, f"tiers_{a}.jpg") for a in order]
        missing = [p for p in paths if not os.path.exists(p)]
        if missing:
            sys.exit(f"missing: {missing}")

    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    for im in ims:
        if im.size != (w, h):
            sys.exit(f"views differ in size: {w}x{h} vs {im.size} -- "
                     f"a strip of mixed sizes would rescale and that is the "
                     f"bug this file exists to avoid")
    gap = max(2, w // 160)
    strip = Image.new("RGB", (w * 5 + gap * 4, h), (255, 255, 255))
    for i, im in enumerate(ims):
        strip.paste(im, (i * (w + gap), 0))

    d = ImageDraw.Draw(strip)
    for i, a in enumerate(order):
        label = f"{int(a):+d}°"
        x, y = i * (w + gap) + gap * 2, gap * 2
        # A plate under it: these rooms are white and a white label vanishes.
        d.rectangle([x - 4, y - 2, x + 9 * len(label), y + 22], fill=(0, 0, 0))
        d.text((x, y), label, fill=(255, 255, 255))

    strip.save(out, quality=95)
    print(f"{out}  {strip.size[0]}x{strip.size[1]}  "
          f"(each view {w}x{h}, aspect {w/h:.3f} — unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
