from playwright.sync_api import sync_playwright

def verify_features():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the index.html directly
        page.goto("file:///app/index.html")

        # Verify basic elements are still there
        assert page.locator("#pills-camera-tab").is_visible()

        # Manually inject mock data to verify the new AI Vision section appears
        mock_data = {
            "fragrance_profile": {
                "name": "Test Perfume",
                "recommendation": "A test scent.",
                "notes": {"Top": ["Lemon"]},
                "image_url": "https://via.placeholder.com/200"
            },
            "ai_debug": {
                "cropped_image": "https://via.placeholder.com/100/0000FF/FFFFFF?text=Crop",
                "dominant_colors": ["#FF0000", "#00FF00", "#0000FF"]
            },
            "source": "Test Source",
            "ocr_text": []
        }

        page.evaluate(f"renderResults({mock_data})")

        # Wait for results section
        results = page.locator("#results-section")
        results.wait_for()

        # Check if AI Vision section is visible
        ai_section = page.locator("#ai-vision-section")
        assert ai_section.is_visible()

        # Check if crop image is present
        crop_img = page.locator("#vision-crop")
        assert crop_img.is_visible()

        # Check if palette is present
        palette = page.locator("#vision-palette")
        assert palette.is_visible()

        # Check if colors are rendered (divs with background color)
        color_dots = palette.locator("div")
        assert color_dots.count() == 3

        print("Verified AI Vision section rendering.")

        # Screenshot
        page.screenshot(path="/home/jules/verification/scentlens_vision.png")
        browser.close()

if __name__ == "__main__":
    verify_features()
