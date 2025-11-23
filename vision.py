import torch
import torchvision.transforms as transforms
from torchvision import models
from PIL import Image
import torch.nn.functional as F
import numpy as np
from sklearn.cluster import KMeans
import os

class VisionEngine:
    def __init__(self):
        print("Initializing Vision Engine...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 1. Embedding Model (MobileNetV3 Small)
        self.embedder = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        self.embedder.eval()
        self.embedder.classifier = torch.nn.Identity() # Remove classification head
        self.embedder.to(self.device)

        # 2. Object Detection Model (SSDLite MobileNetV3)
        # We use this to find the bottle in the frame
        self.detector = models.detection.ssdlite320_mobilenet_v3_large(weights=models.detection.SSDLite320_MobileNet_V3_Large_Weights.DEFAULT)
        self.detector.eval()
        self.detector.to(self.device)

        # Transforms
        self.embed_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        self.detect_transform = transforms.Compose([
            transforms.ToTensor(),
        ])

        print(f"Vision Engine Ready on {self.device}.")

    def detect_and_crop(self, image_path):
        """
        Detects the most prominent object (likely bottle) and returns the cropped PIL image.
        If no object is confident, returns the original image.
        """
        try:
            original_image = Image.open(image_path).convert('RGB')
            input_tensor = self.detect_transform(original_image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                prediction = self.detector(input_tensor)[0]

            # COCO Class 44 is 'bottle'. But generic objects usually work for this context.
            # We'll filter for high confidence detections.
            boxes = prediction['boxes'].cpu().numpy()
            scores = prediction['scores'].cpu().numpy()
            labels = prediction['labels'].cpu().numpy()

            best_box = None
            max_score = 0.0

            for box, score, label in zip(boxes, scores, labels):
                if score > 0.3: # Confidence threshold
                    # Priority to bottles (44), but accept others if high confidence (e.g. box)
                    if label == 44 or score > 0.5:
                        if score > max_score:
                            max_score = score
                            best_box = box

            if best_box is not None:
                # Crop with some padding
                x1, y1, x2, y2 = best_box
                w, h = original_image.size
                pad = 10
                x1 = max(0, x1 - pad)
                y1 = max(0, y1 - pad)
                x2 = min(w, x2 + pad)
                y2 = min(h, y2 + pad)

                cropped = original_image.crop((x1, y1, x2, y2))
                print(f"Object detected! Cropped to {cropped.size}")
                return cropped

            print("No specific object detected. Using full image.")
            return original_image

        except Exception as e:
            print(f"Detection error: {e}")
            return Image.open(image_path).convert('RGB')

    def get_embedding(self, image_input):
        """
        Generates a feature vector for an image (path or PIL Image).
        """
        try:
            if isinstance(image_input, str):
                image = Image.open(image_input).convert('RGB')
            else:
                image = image_input

            input_tensor = self.embed_transform(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                embedding = self.embedder(input_tensor)

            return F.normalize(embedding, p=2, dim=1).cpu()
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    def compute_similarity(self, emb1, emb2):
        if emb1 is None or emb2 is None:
            return 0.0
        return F.cosine_similarity(emb1, emb2).item()

    def extract_colors(self, image_input, k=3):
        """
        Extracts K dominant colors using K-Means.
        Returns a list of hex strings.
        """
        try:
            if isinstance(image_input, str):
                image = Image.open(image_input).convert('RGB')
            else:
                image = image_input

            # Resize for speed
            image = image.resize((100, 100))
            data = np.array(image).reshape(-1, 3)

            kmeans = KMeans(n_clusters=k, n_init=5)
            kmeans.fit(data)
            colors = kmeans.cluster_centers_.astype(int)

            hex_colors = ['#{:02x}{:02x}{:02x}'.format(r, g, b) for r, g, b in colors]
            return hex_colors
        except Exception as e:
            print(f"Color extraction error: {e}")
            return []

    def analyze_color_psychology(self, hex_colors):
        """
        Maps a list of hex colors to scent archetypes/notes using basic color theory.
        Returns a dict with predicted 'vibe' and 'notes'.
        """
        if not hex_colors:
            return None

        # Simple mapping of hue ranges/dominant channel to notes
        scent_map = {
            'red': {'vibe': 'Romantic & Spicy', 'notes': ['Rose', 'Berry', 'Pepper', 'Cinnamon']},
            'blue': {'vibe': 'Fresh & Aquatic', 'notes': ['Sea Notes', 'Mint', 'Water', 'Blueberry']},
            'green': {'vibe': 'Natural & Herbal', 'notes': ['Vetiver', 'Grass', 'Basil', 'Green Tea']},
            'yellow': {'vibe': 'Bright & Citrusy', 'notes': ['Lemon', 'Bergamot', 'Yuzu', 'Honey']},
            'orange': {'vibe': 'Warm & Energetic', 'notes': ['Orange', 'Amber', 'Ginger', 'Mandarin']},
            'brown': {'vibe': 'Earthy & Woody', 'notes': ['Oud', 'Leather', 'Sandalwood', 'Tobacco']},
            'purple': {'vibe': 'Mysterious & Floral', 'notes': ['Lavender', 'Plum', 'Iris', 'Violet']},
            'pink': {'vibe': 'Sweet & Playful', 'notes': ['Peony', 'Candy', 'Raspberry', 'Vanilla']},
            'black': {'vibe': 'Intense & Night', 'notes': ['Smoke', 'Leather', 'Black Pepper', 'Incense']},
            'white': {'vibe': 'Clean & Minimalist', 'notes': ['White Musk', 'Jasmine', 'Cotton', 'Lily']}
        }

        # Count occurrences of archetypes based on the palette
        counts = {}
        for hex_code in hex_colors:
            r = int(hex_code[1:3], 16)
            g = int(hex_code[3:5], 16)
            b = int(hex_code[5:7], 16)

            # Very basic color classifier
            category = 'white' # default

            if r < 40 and g < 40 and b < 40: category = 'black'
            elif r > 200 and g > 200 and b > 200: category = 'white'
            elif r > g and r > b:
                if g > 150: category = 'yellow'
                elif g > 100: category = 'orange'
                elif b > 150: category = 'pink'
                else: category = 'red'
            elif g > r and g > b:
                category = 'green'
            elif b > r and b > g:
                if r > 100: category = 'purple'
                else: category = 'blue'
            elif r > 150 and g > 100 and b < 100:
                category = 'brown'

            if category not in counts: counts[category] = 0
            counts[category] += 1

        # Get dominant category
        dominant = max(counts, key=counts.get)
        result = scent_map.get(dominant, scent_map['white'])

        return {
            'dominant_color_name': dominant,
            'vibe': result['vibe'],
            'predicted_notes': result['notes']
        }
