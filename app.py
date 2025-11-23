import base64
import os
import uuid
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import easyocr
import re

# Import our In-House Engines
from vision import VisionEngine
from collector import DataCollector

app = Flask(__name__)
CORS(app)

# Create an 'uploads' directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Lazy load global instances
reader = None
vision_engine = None
data_collector = None

def get_reader():
    global reader
    if reader is None:
        print("Initializing EasyOCR reader...")
        reader = easyocr.Reader(['en'])
        print("EasyOCR reader initialized.")
    return reader

def get_vision_engine():
    global vision_engine
    if vision_engine is None:
        vision_engine = VisionEngine()
    return vision_engine

def get_data_collector():
    global data_collector
    if data_collector is None:
        data_collector = DataCollector(get_vision_engine())
    return data_collector

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# --- Scraper Helpers (Keep existing Fragrantica logic) ---
def get_recommendation(notes):
    """
    Generates a creative recommendation based on scent notes.
    """
    all_notes = []
    for category in notes.values():
        all_notes.extend([n.lower() for n in category])

    all_notes_str = " ".join(all_notes)

    # Archetypes
    is_fresh = any(x in all_notes_str for x in ['lemon', 'citrus', 'bergamot', 'lime', 'orange', 'fresh', 'water', 'sea'])
    is_floral = any(x in all_notes_str for x in ['rose', 'jasmine', 'floral', 'lily', 'peony', 'lavender'])
    is_warm = any(x in all_notes_str for x in ['oud', 'amber', 'musk', 'leather', 'spice', 'wood', 'tobacco', 'sandalwood'])
    is_sweet = any(x in all_notes_str for x in ['vanilla', 'sweet', 'gourmand', 'chocolate', 'caramel', 'honey'])

    intro = "This fragrance profile suggests a scent that is "
    desc = []
    occasion = "It is likely best suited for "

    if is_fresh and is_floral:
        desc.append("bright, uplifting, and elegantly blooming")
        occasion += "daytime wear in spring or summer, perfect for a garden party or a breezy walk."
    elif is_fresh and is_warm:
        desc.append("crisp yet deeply grounded, balancing energy with sophistication")
        occasion += "office wear or early autumn days where you want to feel professional yet approachable."
    elif is_floral and is_sweet:
        desc.append("playful, romantic, and invitingly delicious")
        occasion += "date nights or cozy gatherings where you want to leave a memorable impression."
    elif is_warm and is_sweet:
        desc.append("rich, intoxicating, and comfortably luxurious")
        occasion += "winter evenings, formal events, or nights out by the fire."
    elif is_fresh:
        desc.append("clean, revitalizing, and full of energy")
        occasion += "casual daily wear, the gym, or hot summer days."
    elif is_warm:
        desc.append("mysterious, bold, and commanding")
        occasion += "making a statement at evening events or during colder months."
    elif is_floral:
        desc.append("classic, graceful, and purely feminine")
        occasion += "weddings, brunches, or daily elegance."
    elif is_sweet:
        desc.append("youthful, fun, and comforting")
        occasion += "casual outings or when you need a mood booster."
    else:
        desc.append("complex and unique")
        occasion += "versatile occasions, adapting to your personal style."

    full_text = intro + desc[0] + ". " + occasion
    return full_text

def scrape_fragrantica(perfume_name):
    """
    Scrapes Fragrantica.com for perfume notes and image.
    Includes headers to mimic a real browser and fallback mock data.
    """
    search_url = f"https://www.fragrantica.com/search/?q={perfume_name}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
    }

    result_data = {
        'name': perfume_name,
        'notes': {},
        'image_url': None,
        'recommendation': None
    }

    try:
        session = requests.Session()

        # First, search for the perfume
        search_response = session.get(search_url, headers=headers, timeout=10)

        if search_response.status_code == 403:
            print(f"Blocked by Fragrantica (403) for {perfume_name}. Returning mock data.")
            return get_mock_data(perfume_name)

        search_response.raise_for_status()
        soup = BeautifulSoup(search_response.text, 'html.parser')

        first_result = soup.find('div', class_='perfume-card-image')
        if not first_result or not first_result.find('a'):
             return get_mock_data(perfume_name)

        link_tag = first_result.find('a')
        perfume_url = "https://www.fragrantica.com" + link_tag['href']

        img_tag = first_result.find('img')
        if img_tag and img_tag.get('src'):
            result_data['image_url'] = img_tag['src']

        perfume_response = session.get(perfume_url, headers=headers, timeout=10)
        perfume_response.raise_for_status()
        perfume_soup = BeautifulSoup(perfume_response.text, 'html.parser')

        title_tag = perfume_soup.find('h1')
        if title_tag:
            result_data['name'] = title_tag.get_text(strip=True)

        pyramid_container = perfume_soup.find('div', id='pyramid')
        if not pyramid_container:
             result_data['recommendation'] = "Scent profile not detailed."
             return result_data

        notes = {}
        for h3 in pyramid_container.find_all('h3'):
            note_type = h3.get_text(strip=True)
            note_list = []
            note_container = h3.find_next_sibling('div')
            if note_container:
                for note_div in note_container.find_all('div', recursive=False):
                    note_text = note_div.get_text(strip=True)
                    if note_text:
                        note_list.append(note_text)
            if note_list:
                notes[note_type] = note_list

        result_data['notes'] = notes
        result_data['recommendation'] = get_recommendation(notes)

        return result_data

    except Exception as e:
        print(f"Scraping error: {e}")
        return get_mock_data(perfume_name)

def get_mock_data(name):
    lower_name = name.lower()

    notes = {}
    image_url = "https://via.placeholder.com/200?text=Perfume"

    if 'sauvage' in lower_name:
        notes = {
            'Top Notes': ['Calabrian bergamot', 'Pepper'],
            'Middle Notes': ['Sichuan Pepper', 'Lavender', 'Pink Pepper', 'Vetiver', 'Patchouli'],
            'Base Notes': ['Ambroxan', 'Cedar', 'Labdanum']
        }
        image_url = "https://fimgs.net/mdimg/perfume/375x500.31861.jpg"
    elif 'chanel' in lower_name and '5' in lower_name:
        notes = {
            'Top Notes': ['Aldehydes', 'Ylang-Ylang', 'Neroli', 'Bergamot', 'Lemon'],
            'Middle Notes': ['Iris', 'Jasmine', 'Rose', 'Orris Root', 'Lily-of-the-Valley'],
            'Base Notes': ['Civet', 'Amber', 'Sandalwood', 'Musk', 'Moss', 'Vetiver', 'Vanilla', 'Patchouli']
        }
        image_url = "https://fimgs.net/mdimg/perfume/375x500.608.jpg"
    elif 'aventus' in lower_name:
        notes = {
            'Top Notes': ['Pineapple', 'Bergamot', 'Black Currant', 'Apple'],
            'Middle Notes': ['Birch', 'Patchouli', 'Moroccan Jasmine', 'Rose'],
            'Base Notes': ['Musk', 'Oak moss', 'Ambergris', 'Vanille']
        }
        image_url = "https://fimgs.net/mdimg/perfume/375x500.9828.jpg"
    else:
        notes = {
            'Top Notes': ['Citrus', 'Fresh Air'],
            'Middle Notes': ['Floral', 'Spices'],
            'Base Notes': ['Wood', 'Musk']
        }

    recommendation = get_recommendation(notes)
    return {
        'name': name.title(),
        'notes': notes,
        'image_url': image_url,
        'recommendation': recommendation + " (Note: This is a simulated result as live data was inaccessible.)"
    }

@app.route('/api/search', methods=['POST'])
def search_perfume():
    data = request.get_json()
    if 'query' not in data:
        return jsonify({'error': 'No query provided'}), 400

    perfume_name = data['query']
    fragrance_profile = scrape_fragrantica(perfume_name)
    return jsonify({'fragrance_profile': fragrance_profile})

@app.route('/api/identify', methods=['POST'])
def identify_perfume():
    data = request.get_json()
    if 'image' not in data:
        return jsonify({'error': 'No image data found'}), 400

    try:
        header, encoded = data['image'].split(',', 1)
        image_data = base64.b64decode(encoded)
    except Exception as e:
        return jsonify({'error': f'Invalid image data: {e}'}), 400

    filename = f"{uuid.uuid4()}.png"
    image_path = os.path.join('uploads', filename)
    with open(image_path, 'wb') as f:
        f.write(image_data)

    detected_labels = []
    ocr_text = []
    fragrance_profile = None
    search_query = ""
    source = ""
    status_message = ""

    # 1. OCR Scan
    try:
        r = get_reader()
        ocr_result = r.readtext(image_path)
        # Filter for confident text
        ocr_text = [text for (_, text, prob) in ocr_result if prob > 0.3]
        print(f"OCR Result: {ocr_text}")
    except Exception as e:
        print(f"OCR Error: {e}")

    # 2. Refined Search Query from OCR
    if ocr_text:
        # Simple heuristic: longer words are more likely to be the brand/name
        # Filter out "Eau", "De", "Toilette", "Parfum", "Vol", "ml"
        ignore_list = ['eau', 'de', 'toilette', 'parfum', 'vol', 'ml', 'spray', 'vaporisateur']
        valid_words = [w for w in ocr_text if len(w) > 2 and w.lower() not in ignore_list]
        if valid_words:
            search_query = " ".join(valid_words[:4])
            source = "OCR Analysis"

    # 3. "The Automated Equation" - Visual Verification & Learning
    if search_query:
        print(f"Potential Match found via OCR: {search_query}. Verifying visually...")

        # A. Trigger Data Collector to "Learn" this scent (Download refs & embed)
        # This makes the AI "look into the Internet" as requested
        collector = get_data_collector()
        vision = get_vision_engine()

        # Get embeddings for the user's image
        user_embedding = vision.get_embedding(image_path)

        # Fetch reference images from the web
        ref_embeddings = collector.collect_and_learn(search_query)

        # B. Compare
        best_score = 0
        if user_embedding is not None and ref_embeddings:
            for ref_emb in ref_embeddings:
                score = vision.compute_similarity(user_embedding, ref_emb)
                if score > best_score:
                    best_score = score

            print(f"Visual Similarity Score: {best_score}")

            if best_score > 0.6: # Threshold for "It looks similar"
                source = f"Visual AI Verified (Confidence: {best_score:.2f})"
                status_message = "Visual match confirmed via automated web learning."
            else:
                source = f"OCR Only (Visual Confidence Low: {best_score:.2f})"
                status_message = "Visual match uncertain, but text matches."
        else:
             status_message = "Could not verify visually (network or embedding error)."

    # 4. Search Fragrantica for Profile
    if search_query:
        fragrance_profile = scrape_fragrantica(search_query)
        if fragrance_profile:
             fragrance_profile['status'] = status_message
    else:
        fragrance_profile = {'error': 'Could not identify perfume box or bottle.'}

    # Clean up
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting file {image_path}: {e}")

    return jsonify({
        'detected_labels': [search_query] if search_query else [], # Repurposing this field for frontend compatibility
        'ocr_text': ocr_text,
        'search_query': search_query,
        'source': source,
        'fragrance_profile': fragrance_profile,
        'visual_confidence': status_message
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
