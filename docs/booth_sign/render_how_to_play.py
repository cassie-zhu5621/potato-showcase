from playwright.sync_api import sync_playwright
import os
p=os.path.abspath('how_to_play.svg')
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page(viewport={'width':1738,'height':1130}, device_scale_factor=2560/1738)
    pg.goto('file://'+p); pg.wait_for_timeout(300); pg.screenshot(path='how_to_play.png'); b.close()
