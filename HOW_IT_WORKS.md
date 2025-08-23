# How the Perfume Identification Works: Object Detection vs. OCR

That's an excellent question! The app does **not** currently use OCR (Optical Character Recognition). Instead, it uses a technique called **Object Detection**. Here’s a simple breakdown of the difference and why we're using this method.

### What We Are Using: Object Detection (with YOLO & Roboflow)

*   **How it Works:** The YOLO model you trained on Roboflow learns to recognize the **visual appearance** of each perfume bottle—its shape, colors, cap design, and overall look.
*   **Training:** You trained it by showing it pictures and drawing boxes around each perfume, telling it, "This *looks like* a bottle of Chanel No. 5."
*   **Inference:** When the app sees a new image, it looks for those learned visual patterns and says, "I see an object that looks like the 'Chanel No. 5' I was trained on."
*   **Analogy:** Think of it like recognizing a friend's face from a distance. You don't need to read their name tag to know who they are; you recognize their unique features.

**Pros of this method:**
*   It can work even if the text is blurry, at a weird angle, or in a different language.
*   It's very fast and effective at finding the location of the object in the frame.

### What We Are NOT Using (But Will Add): OCR (Optical Character Recognition)

*   **How it Works:** OCR is a different technology specifically designed to **find and read text** in an image. An OCR-based approach would ignore the bottle's shape and color and just try to read the words "Chanel No. 5" from the label.
*   **Analogy:** This is like reading someone's name tag to identify them.

**Pros of OCR:**
*   Could identify perfumes the model wasn't explicitly trained on, as long as it can read the text.
*   Can be used to verify the object detection model's prediction, which is what we plan to do next.

**Cons of OCR:**
*   Can be very sensitive to lighting, angles, reflections on the bottle, and fancy fonts, which are common on perfumes.
*   It requires a different model or service.

### Summary & Next Steps

Our current approach uses **object detection**, which is a robust way to identify a known set of objects based on their appearance.

As per your excellent suggestion, our **next step** will be to add a second OCR model to run on the detected bounding box. This will act as a powerful verification step to make sure the identification is correct.
