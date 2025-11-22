import base64
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from roboflow import Roboflow

app = Flask(__name__)
CORS(app)

# Create an 'uploads' directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def get_recommendation(notes):
    """
    Generates a simple recommendation based on scent notes.
    """
    recommendations = []
    all_notes = []
    for category in notes.values():
        all_notes.extend([n.lower() for n in category])

    all_notes_str = " ".join(all_notes)

    if any(x in all_notes_str for x in ['lemon', 'citrus', 'bergamot', 'lime', 'orange', 'fresh']):
        recommendations.append("Perfect for bright summer days.")
    if any(x in all_notes_str for x in ['oud', 'amber', 'musk', 'leather', 'spice', 'wood', 'tobacco']):
        recommendations.append("Great for evening wear or colder months.")
    if any(x in all_notes_str for x in ['rose', 'jasmine', 'floral', 'lily', 'peony']):
        recommendations.append("A romantic choice, suitable for spring.")
    if any(x in all_notes_str for x in ['vanilla', 'sweet', 'gourmand', 'chocolate', 'caramel']):
        recommendations.append("Cozy and inviting, good for dates.")

    if not recommendations:
        recommendations.append("A versatile fragrance for any occasion.")

    return " ".join(recommendations)

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
            # Fallback to simulated data if blocked
            print(f"Blocked by Fragrantica (403) for {perfume_name}. Returning mock data.")
            return get_mock_data(perfume_name)

        search_response.raise_for_status()
        soup = BeautifulSoup(search_response.text, 'html.parser')

        # Find the first search result link
        first_result = soup.find('div', class_='perfume-card-image')
        if not first_result or not first_result.find('a'):
             # Try to search loosely if exact match fails
             return get_mock_data(perfume_name)

        link_tag = first_result.find('a')
        perfume_url = "https://www.fragrantica.com" + link_tag['href']

        # Try to get image from search result
        img_tag = first_result.find('img')
        if img_tag and img_tag.get('src'):
            result_data['image_url'] = img_tag['src']

        # Now, scrape the perfume's page
        perfume_response = session.get(perfume_url, headers=headers, timeout=10)
        perfume_response.raise_for_status()
        perfume_soup = BeautifulSoup(perfume_response.text, 'html.parser')

        # Update name if possible
        title_tag = perfume_soup.find('h1')
        if title_tag:
            result_data['name'] = title_tag.get_text(strip=True)

        # Find the pyramid
        pyramid_container = perfume_soup.find('div', id='pyramid')
        if not pyramid_container:
            # Maybe it's not available, return partial
             result_data['recommendation'] = "Scent profile not detailed."
             return result_data

        notes = {}
        for h3 in pyramid_container.find_all('h3'):
            note_type = h3.get_text(strip=True)
            note_list = []
            # This logic assumes notes are in the next sibling div
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
    """
    Returns mock data so the app is usable even if scraping fails.
    """
    # Normalize name for better mock matching
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
        # Generic Mock
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

    image_path = os.path.join('uploads', 'captured_image.png')
    with open(image_path, 'wb') as f:
        f.write(image_data)

    try:
        # Initialize Roboflow
        api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            return jsonify({
                'error': 'Roboflow API Key missing. Please use Manual Search.',
                'detected_labels': [],
                'fragrance_profile': None
            }), 503

        rf = Roboflow(api_key=api_key)
        project = rf.workspace("zixen15").project("perfume-detection-5gyru")
        model = project.version(3).model

        # Run inference
        prediction = model.predict(image_path, confidence=40, overlap=30).json()

        detected_labels = []
        fragrance_profile = None

        if prediction['predictions']:
            # Sort by confidence and take the top one
            top_prediction = sorted(prediction['predictions'], key=lambda x: x['confidence'], reverse=True)[0]
            detected_labels = [p['class'] for p in prediction['predictions']]
            perfume_name = top_prediction['class']

            # Scrape Fragrantica with the identified perfume name
            fragrance_profile = scrape_fragrantica(perfume_name)
        else:
            fragrance_profile = {'error': 'No perfume detected in the image.'}

        return jsonify({
            'detected_labels': detected_labels,
            'fragrance_profile': fragrance_profile,
            'raw_prediction': prediction
        })

    except Exception as e:
        return jsonify({'error': f'AI Identification failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
