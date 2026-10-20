#!/usr/bin/env python3
"""
render_spec_cell.py — the tablet's rule cell, as an image, for a figure.

  python3 robot/tools/render_spec_cell.py 9 plant out.png            # lit
  python3 robot/tools/render_spec_cell.py 9 plant out.png --waiting  # not yet
  python3 robot/tools/render_spec_cell.py 9 plant out.png --tight

THE REAL CSS, NOT A REDRAWING. The stylesheet is lifted out of webui/booth.py's
PAGE at run time and the markup is what specInner()/ruleRow() emit, so the
picture in the paper is the screen a visitor saw -- including the details
nobody would think to copy, like the object chip being monospace while the
relation chip is not.

Rendered in headless Chromium at 3x for print. On a machine without
libXdamage (the Cowork sandbox) extract it from the Ubuntu package and put it
on LD_LIBRARY_PATH; on a Mac with playwright installed, it just runs.
"""
import argparse
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rel", type=int, help="relation id, e.g. 9 for hands on")
    ap.add_argument("obj", nargs="?", default="", help="the `on` object")
    ap.add_argument("out")
    ap.add_argument("--waiting", action="store_true",
                    help="the unlit state: WAITING FOR, nothing true yet")
    ap.add_argument("--tight", action="store_true",
                    help="crop to the content instead of the tablet cell")
    a = ap.parse_args()

    from webui.booth import PAGE, REL_NAMES
    css = re.search(r"<style>(.*?)</style>", PAGE, re.S).group(1)
    name = REL_NAMES[a.rel]
    lit = not a.waiting
    t = " t" if lit else ""
    obj = (f'<span class=op>on</span><span class="obj{t}">{a.obj}</span>'
           if a.obj else "")
    cell = (f'<div class="cell spec{" sat" if lit else ""}" id=cap>'
            f'<span class=lb>{"TRUE NOW" if lit else "WATCHING FOR 1 THING"}</span>'
            f'<div class="rules n1"><div class="rule{" sat" if lit else ""}">'
            f'<span class="rel{t}">{name}</span>{obj}</div></div></div>')
    size = ("#cap{width:auto;height:auto;display:inline-flex;padding:18px 26px;gap:10px}"
            if a.tight else "#cap{width:560px;height:315px;display:flex}")
    html = (f"<!doctype html><html><head><meta charset=utf-8><style>{css}"
            f"body{{background:#141414;height:auto;padding:24px;display:block}}"
            f"{size}</style></head><body>{cell}</body></html>")

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 1024},
                        device_scale_factor=3)
        pg.goto("file://" + f.name)
        pg.wait_for_timeout(300)
        pg.locator("#cap").screenshot(path=a.out)
        b.close()
    os.unlink(f.name)
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
