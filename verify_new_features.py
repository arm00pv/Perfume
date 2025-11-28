from playwright.sync_api import sync_playwright
import os
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Open the local HTML file
        url = "file://" + os.path.abspath("index.html")
        page.goto(url)

        print(f"Loaded {page.title()}")

        # 1. Check Mix Lab
        print("Checking Mix Lab Tab...")
        page.click("#pills-mix-tab")
        time.sleep(1)

        mix_btn = page.is_visible("#mix-btn")
        if mix_btn:
            print("PASS: Mix Lab interface is visible.")
        else:
            print("FAIL: Mix Lab interface not found.")

        # 2. Check Vibe Check Toggle (Camera Tab)
        print("Checking Vibe Check Toggle...")
        page.click("#pills-camera-tab")
        time.sleep(1)

        vibe_toggle = page.is_visible("label[for='mode-vibe']")
        if vibe_toggle:
            print("PASS: Vibe Check toggle is visible.")
        else:
            print("FAIL: Vibe Check toggle not found.")

        # Screenshot
        page.screenshot(path="scentlens_new_features.png")
        print("Screenshot saved to scentlens_new_features.png")

        browser.close()

if __name__ == "__main__":
    run()
