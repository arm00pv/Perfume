import torch
import torchvision.transforms as transforms
from torchvision import models
from PIL import Image
import torch.nn.functional as F
import os

class VisionEngine:
    def __init__(self):
        print("Initializing Vision Engine (MobileNetV3)...")
        # Load a lightweight, pre-trained model
        self.model = models.mobilenet_v3_small(pretrained=True)
        self.model.eval()
        # Remove the classification head to get embeddings
        self.model.classifier = torch.nn.Identity()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        print("Vision Engine Ready.")

    def get_embedding(self, image_path):
        """
        Generates a feature vector (embedding) for an image.
        """
        try:
            image = Image.open(image_path).convert('RGB')
            input_tensor = self.transform(image).unsqueeze(0)

            with torch.no_grad():
                embedding = self.model(input_tensor)

            # Normalize the embedding
            return F.normalize(embedding, p=2, dim=1)
        except Exception as e:
            print(f"Error generating embedding for {image_path}: {e}")
            return None

    def compute_similarity(self, emb1, emb2):
        """
        Computes Cosine Similarity between two embeddings.
        Returns a float between 0 and 1.
        """
        if emb1 is None or emb2 is None:
            return 0.0

        return F.cosine_similarity(emb1, emb2).item()
