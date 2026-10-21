import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/home/dadrout/.cache/ms-playwright/chromium-1193/chrome-linux/chrome")
    page = browser.new_page()
    page.goto(Path(sys.argv[1]).resolve().as_uri())
    page.pdf(path=sys.argv[2], format="A4", print_background=True)
    browser.close()
print("saved", sys.argv[2])
