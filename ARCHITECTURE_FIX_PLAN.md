# Plan: Fixing the "Stuck on Analyzing" Issue

You've correctly identified that the application is getting stuck. My last change, which enabled multi-detection, made the server do too much work at once, causing it to time out.

The current architecture is not sustainable for a real-time app. We need to make a fundamental change to how the frontend and backend communicate.

### The Problem

Currently, for every single video frame, the backend does this for *every* detected perfume:
1.  Run Object Detection (fast)
2.  Run OCR (slow)
3.  Scrape Website (slow)

This takes too long and the connection times out.

### The Solution: A New Two-Step Architecture

I will refactor the application to be much smarter and faster:

**Step 1: Real-time Bounding Boxes (Instantaneous)**
- The backend will have a very fast endpoint that **only** does object detection.
- The frontend will call this endpoint in a loop. It will get back the locations of the perfume bottles almost instantly and draw the boxes on the screen. The UI will feel very responsive.

**Step 2: Get Details on Click (On-Demand)**
- When you **click** on a specific box on the screen, the frontend will then make a *second*, separate API call to the backend.
- This second call will tell the backend to do the slow work (scrape Fragrantica, run OCR) for **only the perfume you clicked on**.
- The app will then show the detailed profile for that specific perfume.

### Benefits of this New Architecture

*   **Fast & Responsive UI:** The bounding boxes will appear in real-time without any "stuck on analyzing" lag.
*   **Efficient:** The slow work is only done when you explicitly ask for it by clicking, not constantly in the background.
*   **Stable:** This will permanently fix the timeout errors.

This is a significant architectural improvement. If you approve, I will create a new plan to implement these changes on both the frontend and backend.
