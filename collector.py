import os
import requests
import re
import time
import torch
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from PIL import Image

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

class DataCollector:
    def __init__(self, vision_engine):
        self.vision = vision_engine
        self.kb_dir = 'knowledge_base'
        if not os.path.exists(self.kb_dir):
            os.makedirs(self.kb_dir)

    def _get_safe_name(self, name):
        return re.sub(r'[^a-zA-Z0-9]', '_', name).lower()

    def load_from_cache(self, perfume_name):
        """
        Checks if embeddings and reference images already exist for this perfume.
        Returns list of (embedding, image_path) tuples.
        """
        safe_name = self._get_safe_name(perfume_name)
        folder = os.path.join(self.kb_dir, safe_name)
        embedding_file = os.path.join(folder, 'embeddings.pt')

        if os.path.exists(embedding_file):
            print(f"Loaded {perfume_name} from Knowledge Base.")
            try:
                data = torch.load(embedding_file)
                # verify images still exist
                valid_data = []
                for emb, img_path in data:
                    if os.path.exists(img_path):
                        valid_data.append((emb, img_path))
                return valid_data
            except Exception as e:
                print(f"Error loading cache: {e}")
        return None

    def save_to_cache(self, perfume_name, data):
        """
        Saves list of (embedding, image_path) to disk.
        """
        safe_name = self._get_safe_name(perfume_name)
        folder = os.path.join(self.kb_dir, safe_name)
        if not os.path.exists(folder):
            os.makedirs(folder)

        embedding_file = os.path.join(folder, 'embeddings.pt')
        torch.save(data, embedding_file)
        print(f"Saved {len(data)} embeddings for {perfume_name} to Knowledge Base.")

    def collect_and_learn(self, perfume_name):
        """
        1. Check Cache.
        2. If not found, Search & Download.
        3. Generate Embeddings.
        4. Save to Cache.
        Returns list of (embedding, image_path).
        """
        # 1. Check Cache
        cached_data = self.load_from_cache(perfume_name)
        if cached_data:
            return cached_data

        print(f"Learning new scent: {perfume_name}...")

        # 2. Search & Download
        safe_name = self._get_safe_name(perfume_name)
        save_dir = os.path.join(self.kb_dir, safe_name)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        query = f"{perfume_name} perfume bottle"
        urls = self.search_images_basic(query, max_images=5)

        new_data = []
        count = 0

        for url in urls:
            path = self.download_image(url, save_dir, f"ref_{count}")
            if path:
                # 3. Embed (using the same crop logic as user image for consistency?)
                # Ideally yes, but reference images usually clear. We'll crop them too!

                try:
                    # Detect/Crop reference image too for better feature matching
                    cropped_ref = self.vision.detect_and_crop(path)
                    emb = self.vision.get_embedding(cropped_ref)

                    if emb is not None:
                        new_data.append((emb, path))
                        count += 1
                except Exception as e:
                    print(f"Error processing reference {path}: {e}")

        # 4. Save
        if new_data:
            self.save_to_cache(perfume_name, new_data)

        return new_data

    def search_images_basic(self, query, max_images=3):
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')

            image_urls = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('http') and 'logos' not in src:
                    image_urls.append(src)
                    if len(image_urls) >= max_images:
                        break
            return image_urls
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def download_image(self, url, folder, prefix):
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            if response.status_code == 200:
                filename = f"{prefix}_{int(time.time()*1000)}.jpg"
                path = os.path.join(folder, filename)
                with open(path, 'wb') as f:
                    f.write(response.content)
                return path
        except:
            pass
        return None

    def search_knowledge_base(self, query_embedding, threshold=0.7):
        """
        Iterates through the entire knowledge base to find the best visual match
        for the given query embedding.

        Returns:
            (best_name, best_score, best_image_path) or None
        """
        print("Searching Knowledge Base for visual match...")
        best_match = None
        best_score = -1.0

        # Iterate over all perfume folders
        if not os.path.exists(self.kb_dir):
            return None

        for perfume_name in os.listdir(self.kb_dir):
            folder_path = os.path.join(self.kb_dir, perfume_name)
            if not os.path.isdir(folder_path):
                continue

            embedding_file = os.path.join(folder_path, 'embeddings.pt')
            if not os.path.exists(embedding_file):
                continue

            try:
                # Load embeddings for this perfume
                data = torch.load(embedding_file)
                for stored_emb, img_path in data:
                    # Compute similarity
                    score = self.vision.compute_similarity(query_embedding, stored_emb)
                    if score > best_score:
                        best_score = score
                        # Convert directory name back to readable name (e.g., dior_sauvage -> Dior Sauvage)
                        readable_name = perfume_name.replace('_', ' ').title()
                        best_match = (readable_name, best_score, img_path)
            except Exception as e:
                print(f"Error reading cache for {perfume_name}: {e}")
                continue

        if best_match and best_match[1] >= threshold:
            print(f"Visual Match Found: {best_match[0]} (Score: {best_match[1]:.2f})")
            return best_match

        print(f"No strong visual match found (Best: {best_score:.2f})")
        return None
