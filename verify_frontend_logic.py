from playwright.sync_api import sync_playwright

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the index.html directly
        page.goto("file:///app/index.html")

        # Wait for the title
        page.wait_for_selector("h1")

        # Check Hero Text
        hero_text = page.locator("h1.display-4").inner_text()
        print(f"Hero Text: {hero_text}")
        assert "Discover Your Perfect Scent" in hero_text

        # Check if tabs are present
        assert page.locator("#pills-camera-tab").is_visible()
        assert page.locator("#pills-collection-tab").is_visible()

        # Trigger the "Loading" overlay manually to verify the text logic
        # We can execute JS to show it
        page.evaluate("showLoading(true)")
        page.wait_for_timeout(500) # Wait for animation/text update

        # Check initial loading text
        loading_text = page.locator("#loading-text").inner_text()
        print(f"Loading Text: {loading_text}")
        assert "Extracting visual features..." in loading_text

        # Wait a bit for the text to rotate (interval is 2000ms)
        page.wait_for_timeout(2100)
        rotated_text = page.locator("#loading-text").inner_text()
        print(f"Rotated Text: {rotated_text}")
        assert "Reading text labels..." in rotated_text

        # Take screenshot of the loading state
        page.screenshot(path="/home/jules/verification/scentlens_loading.png")

        # Hide loading to see the main UI again
        page.evaluate("showLoading(false)")
        page.wait_for_timeout(500)

        # Take screenshot of the main UI
        page.screenshot(path="/home/jules/verification/scentlens_main.png")

        browser.close()

if __name__ == "__main__":
    verify_frontend()
