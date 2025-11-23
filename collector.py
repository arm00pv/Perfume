import os
import requests
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import time

# Heuristic headers to look like a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def search_images_ddg(query, max_images=3):
    """
    Searches DuckDuckGo for images and returns a list of URLs.
    This is a simplified scraper.
    """
    print(f"Searching images for: {query}")
    url = f"https://duckduckgo.com/?q={quote_plus(query)}&t=h_&iax=images&ia=images"

    # Note: scraping DDG directly often requires executing JS or hitting their API endpoint directly.
    # We will try a known endpoint pattern `https://duckduckgo.com/i.js`.

    params = {
        'l': 'us-en',
        'o': 'json',
        'q': query,
        'vqd': '', # This usually needs a token, which makes DDG hard to scrape simply.
        'f': ',,,',
        'p': '1'
    }

    # Alternative: Use a generic simplified scraping method or fallback.
    # Since complex scraping is fragile, we'll try a very simple Google Images fallback via HTML parsing
    # if we can't get an easy API hit.

    # Let's try a direct HTML scrape of a search engine that renders static HTML more easily?
    # Bing is often easier.

    return scrape_google_images_basic(query, max_images)

def scrape_google_images_basic(query, max_images=3):
    """
    A very basic HTML parser for Google Images.
    Google sends simplified HTML to older user agents or basic requests.
    """
    url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # Google's basic HTML often puts images in <img> tags inside tables or divs
        # But in modern results, they are in script tags or complex JSON.
        # However, `tbm=isch` often returns thumbnails in src attributes directly.

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

def download_image(url, folder, prefix):
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)

        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            filename = f"{prefix}_{int(time.time()*1000)}.jpg"
            path = os.path.join(folder, filename)
            with open(path, 'wb') as f:
                f.write(response.content)
            return path
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return None

class DataCollector:
    def __init__(self, vision_engine):
        self.vision = vision_engine
        self.dataset_dir = 'dataset'

    def collect_and_learn(self, perfume_name):
        """
        1. Search for images of the perfume.
        2. Download them.
        3. Generate embeddings.
        4. Return the list of new embeddings.
        """
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', perfume_name).lower()
        save_dir = os.path.join(self.dataset_dir, clean_name)

        # 1. Search
        # We append "perfume bottle" to ensure we get the bottle, not just a logo or ad
        query = f"{perfume_name} perfume bottle"
        urls = search_images_ddg(query, max_images=4)

        if not urls:
            print("No images found.")
            return []

        # 2. Download
        new_embeddings = []
        count = 0
        for url in urls:
            path = download_image(url, save_dir, f"ref_{count}")
            if path:
                # 3. Embed
                emb = self.vision.get_embedding(path)
                if emb is not None:
                    new_embeddings.append(emb)
                    count += 1

        print(f"Collected {count} reference images for {perfume_name}")
        return new_embeddings
