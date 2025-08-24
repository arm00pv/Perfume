# Optimization Plan: OCR-First Detection

This document outlines your excellent suggestion to use OCR as a "trigger" for the object detection model. This is a smart optimization strategy.

### How It Would Work (The New Flow)

Currently, we run the heavy object detection model on every frame. Your idea would change the process to this:

1.  **Run OCR First:** On each frame from the camera, we would first run the fast OCR model.
2.  **Scan for Keywords:** We would check the text returned by the OCR for a list of "trigger words" (e.g., "parfum", "toilette", "cologne", "fragrance", "eau de parfum", "eau de toilette").
3.  **Trigger Object Detection:** **Only if** one of those keywords is found do we then run the more powerful (and slower) YOLO object detection model on that frame to identify the specific perfume.

### Pros and Cons

*   **Pro: Better Performance.** This could make the application feel much faster and more responsive, as it wouldn't be doing the heavy work of object detection on every single frame. It would only "wake up" the main AI when it sees a hint that a perfume might be present.
*   **Con: Potential to Miss Detections.** If the OCR fails to read the text on a bottle due to difficult lighting, a strange font, or an awkward angle, the object detection model would never be triggered, and we might miss a perfume that the YOLO model could have identified visually.

### Summary

This is a trade-off between performance and detection robustness. The OCR-first approach is a great strategy for optimizing the application.

If you would like to proceed with this change, I will create a new plan to refactor the backend code to implement this new logic.
