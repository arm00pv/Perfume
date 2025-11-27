import base64
import os
import uuid
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import easyocr
import re
from io import BytesIO
import json
import random

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

# --- Recommendation Engine Data ---
PERFUME_ARCHETYPES = {
    'fresh': {
        'desc': "clean, revitalizing, and full of energy",
        'occasion': "casual daily wear, the gym, or hot summer days",
        'similars': ["Acqua di Gio", "Dolce & Gabbana Light Blue", "Issey Miyake L'Eau d'Issey", "Davidoff Cool Water", "Versace Man Eau Fraiche"]
    },
    'floral': {
        'desc': "classic, graceful, and purely feminine",
        'occasion': "weddings, brunches, or daily elegance",
        'similars': ["Gucci Bloom", "Marc Jacobs Daisy", "Viktor&Rolf Flowerbomb", "Dior J'adore", "Chloe Eau de Parfum"]
    },
    'warm': {
        'desc': "mysterious, bold, and commanding",
        'occasion': "making a statement at evening events or during colder months",
        'similars': ["YSL Black Opium", "Tom Ford Tobacco Vanille", "Dior Sauvage", "Versace Eros", "Giorgio Armani Code"]
    },
    'sweet': {
        'desc': "youthful, fun, and comforting",
        'occasion': "casual outings or when you need a mood booster",
        'similars': ["Prada Candy", "Ariana Grande Cloud", "Aquolina Pink Sugar", "Mugler Angel", "Lancome La Vie Est Belle"]
    },
    'aquatic': {
        'desc': "crisp, oceanic, and refreshing",
        'occasion': "summer vacations or when you crave a sea breeze",
        'similars': ["Giorgio Armani Acqua di Gio", "Bvlgari Aqva Pour Homme", "Nautica Voyage", "Kenzo Homme"]
    },
    'wood': {
        'desc': "grounded, earthy, and sophisticated",
        'occasion': "the office or formal business meetings",
        'similars': ["Terre d'Hermes", "Bleu de Chanel", "Creed Aventus", "Tom Ford Oud Wood"]
    }
}

def analyze_notes(notes):
    """
    Analyzes notes to determine the archetype.
    """
    all_notes = []
    for category in notes.values():
        all_notes.extend([n.lower() for n in category])

    all_notes_str = " ".join(all_notes)

    # Archetypes
    scores = {
        'fresh': 0, 'floral': 0, 'warm': 0, 'sweet': 0, 'aquatic': 0, 'wood': 0
    }

    if any(x in all_notes_str for x in ['lemon', 'citrus', 'bergamot', 'lime', 'orange']): scores['fresh'] += 1
    if any(x in all_notes_str for x in ['rose', 'jasmine', 'lily', 'peony', 'lavender']): scores['floral'] += 1
    if any(x in all_notes_str for x in ['oud', 'amber', 'musk', 'leather', 'spice', 'tobacco']): scores['warm'] += 1
    if any(x in all_notes_str for x in ['vanilla', 'gourmand', 'chocolate', 'caramel', 'honey', 'sugar']): scores['sweet'] += 1
    if any(x in all_notes_str for x in ['water', 'sea', 'ocean', 'marine', 'salt']): scores['aquatic'] += 1
    if any(x in all_notes_str for x in ['wood', 'sandalwood', 'cedar', 'vetiver', 'pine', 'oak']): scores['wood'] += 1

    # Return dominant archetype
    best_match = max(scores, key=scores.get)
    if scores[best_match] == 0: return 'fresh' # Default
    return best_match

def get_recommendation_and_similars(notes):
    archetype = analyze_notes(notes)
    data = PERFUME_ARCHETYPES.get(archetype, PERFUME_ARCHETYPES['fresh'])

    intro = "This fragrance profile suggests a scent that is "
    full_text = intro + data['desc'] + ". It is likely best suited for " + data['occasion'] + "."

    # Pick 3 random similars
    similars = random.sample(data['similars'], min(3, len(data['similars'])))

    return full_text, similars

# --- Scraper Helpers (Keep existing Fragrantica logic) ---

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
        'recommendation': None,
        'similars': []
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
        rec, sims = get_recommendation_and_similars(notes)
        result_data['recommendation'] = rec
        result_data['similars'] = sims

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

    rec, sims = get_recommendation_and_similars(notes)
    return {
        'name': name.title(),
        'notes': notes,
        'image_url': image_url,
        'recommendation': rec + " (Note: This is a simulated result as live data was inaccessible.)",
        'similars': sims
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

    ai_debug = {
        'cropped_image': None,
        'best_match_image': None,
        'dominant_colors': []
    }

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
        ignore_list = ['eau', 'de', 'toilette', 'parfum', 'vol', 'ml', 'spray', 'vaporisateur']
        valid_words = [w for w in ocr_text if len(w) > 2 and w.lower() not in ignore_list]
        if valid_words:
            search_query = " ".join(valid_words[:4])
            source = "OCR Analysis"

    # 3. In-House AI Logic
    collector = get_data_collector()
    vision = get_vision_engine()

    # A. Detect & Crop Object (Always do this for analysis)
    cropped_img = vision.detect_and_crop(image_path)

    # Convert cropped image to base64 for frontend display
    buffered = BytesIO()
    cropped_img.save(buffered, format="PNG")
    ai_debug['cropped_image'] = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode('utf-8')

    # B. Extract Colors
    ai_debug['dominant_colors'] = vision.extract_colors(cropped_img)

    # C. Get User Embedding
    user_embedding = vision.get_embedding(cropped_img)

    # D. Identification Pipeline

    # Path 1: Text-Based ID (OCR -> Scrape -> Verify)
    if search_query:
        print(f"Verifying text query: {search_query}...")
        ref_data = collector.collect_and_learn(search_query)

        best_score = 0
        if user_embedding is not None and ref_data:
            for ref_emb, ref_path in ref_data:
                score = vision.compute_similarity(user_embedding, ref_emb)
                if score > best_score:
                    best_score = score

            if best_score > 0.6:
                source = f"Visual AI Verified (Confidence: {best_score:.2f})"
                status_message = "Visual match confirmed via Knowledge Base."
            else:
                source = f"OCR Only (Visual Confidence Low: {best_score:.2f})"
                status_message = "Visual match uncertain, but text matches."

        fragrance_profile = scrape_fragrantica(search_query)
        if fragrance_profile:
             fragrance_profile['status'] = status_message

    # Path 2: Blind Visual Search (Reverse Image Search)
    elif user_embedding is not None:
        print("No OCR text found. Attempting Blind Visual Search...")
        best_match = collector.search_knowledge_base(user_embedding, threshold=0.65)

        if best_match:
            name, score, _ = best_match
            search_query = name
            source = f"Blind Visual Match (Score: {score:.2f})"
            status_message = f"Identified purely by bottle shape/style."
            fragrance_profile = scrape_fragrantica(search_query)
            if fragrance_profile:
                fragrance_profile['status'] = status_message

    # Path 3: Synesthesia AI (Color Psychology Fallback)
    if not fragrance_profile or 'error' in fragrance_profile:
        print("Identification failed. Falling back to Color Psychology.")
        color_analysis = vision.analyze_color_psychology(ai_debug['dominant_colors'])

        if color_analysis:
            source = "Synesthesia AI (Color Analysis)"
            status_message = "Exact match not found. Generating profile from bottle aesthetics."

            # Map color vibe to archetype
            vibe = color_analysis.get('vibe', 'fresh')
            # Simple mapping from vibe string to archetype key
            archetype_key = 'fresh'
            if 'romance' in vibe or 'floral' in vibe: archetype_key = 'floral'
            elif 'bold' in vibe or 'warm' in vibe: archetype_key = 'warm'
            elif 'sweet' in vibe: archetype_key = 'sweet'
            elif 'aquatic' in vibe or 'fresh' in vibe: archetype_key = 'aquatic'
            elif 'earthy' in vibe: archetype_key = 'wood'

            # Get similars for this archetype
            similars = PERFUME_ARCHETYPES[archetype_key]['similars']

            fragrance_profile = {
                'name': f"Mystery Scent ({color_analysis['dominant_color_name'].title()} Aura)",
                'recommendation': f"Based on the {color_analysis['dominant_color_name']} hues, this scent likely has a {color_analysis['vibe']} character.",
                'notes': {
                    'Predicted Notes': color_analysis['predicted_notes']
                },
                'image_url': None,
                'status': status_message,
                'similars': similars
            }
        else:
            fragrance_profile = {'error': 'Could not identify perfume box or bottle.'}

    # Clean up
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting file {image_path}: {e}")

    return jsonify({
        'detected_labels': [search_query] if search_query else [],
        'ocr_text': ocr_text,
        'search_query': search_query,
        'source': source,
        'fragrance_profile': fragrance_profile,
        'visual_confidence': status_message,
        'ai_debug': ai_debug
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
