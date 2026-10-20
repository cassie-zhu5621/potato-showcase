#!/usr/bin/env python3
"""
render_report_cards.py — the Study 2 reports worth talking about, as cards.

  python3 robot/tools/render_report_cards.py picks.json out_dir/

Each card is one report a participant actually received: what they asked, the
storyboard strip the robot made, the sentence it wrote, and what the
participant did with it -- the 1-5 rating and whether they kept it. The quote,
where there is one, is the interview line that §8.4 of EVIDENCE_INDEX.md
already ties to that moment; this tool does not choose quotes.

READ-ONLY ON evaluation/. The ratings come from the participants' review CSVs
and the strips from the session feed; nothing is written back.

picks.json is a list of
  {pid, time, request, report, rating, keep, strip, why, quote?}
"""
import html
import json
import os
import sys


CSS = """
*{box-sizing:border-box}
body{margin:0;padding:28px;background:#f4f2ed;font-family:-apple-system,
  "Helvetica Neue",Helvetica,Arial,sans-serif;color:#1c1c1a}
.card{background:#fff;border-radius:14px;padding:22px 26px;margin:0 0 26px;
  width:1700px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.top{display:flex;align-items:baseline;gap:14px;margin-bottom:10px}
.pid{font-weight:800;font-size:22px}
.ask{font-size:18px;color:#55524b}
.ask b{color:#1c1c1a;font-weight:600}
.strip{width:100%;display:block;border-radius:6px}
.said{font-size:19px;margin:12px 0 10px;line-height:1.35}
.foot{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.dots{display:flex;gap:6px}
.dots i{width:16px;height:16px;border-radius:50%;background:#e2dfd7}
.dots i.on{background:#d95b5b}
.score{font-weight:700;font-size:17px;min-width:44px}
.keep{font-size:14px;font-weight:700;letter-spacing:.06em;padding:5px 11px;
  border-radius:20px}
.keep.y{background:#d9e157;color:#262626}
.keep.n{background:#ece9e2;color:#8a867d}
.why{font-size:16px;color:#8a6a00;font-weight:600}
.quote{margin-top:12px;padding-left:14px;border-left:3px solid #d9e157;
  font-size:17px;font-style:italic;color:#3a3a36}
"""


def card(p):
    r = int(p["rating"]) if str(p.get("rating", "")).isdigit() else 0
    dots = "".join(f'<i class="{"on" if k < r else ""}"></i>' for k in range(5))
    kept = p.get("keep") == "keep"
    q = (f'<div class=quote>“{html.escape(p["quote"])}”</div>'
         if p.get("quote") else "")
    return f"""<div class=card id="{p['pid']}_{p['time'].replace(':','')}">
  <div class=top><span class=pid>{p['pid']}</span>
    <span class=ask>asked <b>“{html.escape(p['request'])}”</b> · {p['time']}</span></div>
  <img class=strip src="file://{os.path.abspath(p['strip'])}">
  <div class=said>{html.escape(p['report'])}</div>
  <div class=foot><div class=dots>{dots}</div>
    <span class=score>{r or '–'} / 5</span>
    <span class="keep {'y' if kept else 'n'}">{'KEPT' if kept else 'NOT KEPT'}</span>
    <span class=why>{html.escape(p['why'])}</span></div>
  {q}
</div>"""


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: render_report_cards.py picks.json out_dir/")
    picks = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    page = (f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}"
            f"</style></head><body>{''.join(card(p) for p in picks)}</body></html>")
    hp = os.path.join(out, "report_cards.html")
    open(hp, "w").write(page)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1800, "height": 1200},
                        device_scale_factor=2)
        pg.goto("file://" + os.path.abspath(hp))
        pg.wait_for_load_state("networkidle")
        for p in picks:
            cid = f"{p['pid']}_{p['time'].replace(':', '')}"
            path = os.path.join(out, f"{cid}.png")
            pg.locator(f"#{cid}").screenshot(path=path)
            print(path)
        b.close()
    print(hp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
