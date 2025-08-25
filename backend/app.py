import base64
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
from roboflow import Roboflow
from PIL import Image
import io
from cachetools import TTLCache, cached
from thefuzz import fuzz

app = Flask(__name__)
CORS(app)

# Create an 'uploads' directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Initialize a cache that holds up to 100 items and expires items after 1 hour (3600 seconds)
cache = TTLCache(maxsize=100, ttl=3600)

@cached(cache)
def scrape_fragrantica(perfume_name):
    """
    Scrapes Fragrantica.com for perfume notes. Results are cached.
    """
    search_url = f"https://www.fragrantica.com/search/?q={perfume_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

    try:
        search_response = requests.get(search_url, headers=headers)
        search_response.raise_for_status()
        soup = BeautifulSoup(search_response.text, 'html.parser')

        first_result = soup.find('div', class_='perfume-card-image')
        if not first_result or not first_result.find('a'):
            return {'error': f'Could not find perfume "{perfume_name}" on Fragrantica.'}

        perfume_url = "https://www.fragrantica.com" + first_result.find('a')['href']

        perfume_response = requests.get(perfume_url, headers=headers)
        perfume_response.raise_for_status()
        perfume_soup = BeautifulSoup(perfume_response.text, 'html.parser')

        pyramid_container = perfume_soup.find('div', id='pyramid')
        if not pyramid_container:
            return {'error': 'Could not find the fragrance pyramid on the page.'}

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

        return {'notes': notes, 'url': perfume_url}

    except requests.exceptions.RequestException as e:
        return {'error': f"Error fetching from Fragrantica: {e}"}
    except Exception as e:
        return {'error': f"An error occurred during scraping: {e}"}


def perform_ocr(image_bytes, api_key):
    """
    Performs OCR on an image using the Roboflow OCR API.
    """
    ocr_url = "https://infer.roboflow.com/doctr/ocr"
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    payload = {"image": {"type": "base64", "value": base64_image}}
    params = {'api_key': api_key}

    try:
        response = requests.post(ocr_url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Error calling OCR API: {e}"}

# --- New Fast Endpoint for Object Detection Only ---
@app.route('/api/identify', methods=['POST'])
def identify_objects():
    try:
        data = request.get_json()
        if 'image' not in data:
            return jsonify({'error': 'No image data found in request.'}), 400
        header, encoded = data['image'].split(',', 1)
        image_data = base64.b64decode(encoded)
    except Exception as e:
        return jsonify({'error': f'Error processing incoming image: {e}'}), 400

    try:
        api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            return jsonify({'error': 'ROBOFLOW_API_KEY not set.'}), 500

        rf = Roboflow(api_key=api_key)
        project = rf.workspace("zixen15").project("perfume-mfzff-sjzin")
        model = project.version(3).model
        prediction = model.predict(image_data, confidence=40, overlap=30).json()

        return jsonify(prediction)

    except Exception as e:
        return jsonify({'error': f'Failed during object detection: {e}'}), 500

# --- New Slow Endpoint for Getting Details on Demand ---
@app.route('/api/get_details', methods=['POST'])
def get_details():
    try:
        data = request.get_json()
        perfume_name = data.get('perfume_name')
        bounding_box = data.get('bounding_box')
        image_data_url = data.get('image_data_url')

        if not all([perfume_name, bounding_box, image_data_url]):
            return jsonify({'error': 'Missing perfume_name, bounding_box, or image_data_url'}), 400

        header, encoded = image_data_url.split(',', 1)
        image_data = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(image_data))

    except Exception as e:
        return jsonify({'error': f'Error processing incoming request data: {e}'}), 400

    # Scrape Fragrantica
    try:
        fragrance_data = scrape_fragrantica(perfume_name)
        fragrance_profile = fragrance_data if 'error' in fragrance_data else fragrance_data.get('notes', {})
        fragrantica_url = None if 'error' in fragrance_data else fragrance_data.get('url')
    except Exception as e:
        return jsonify({'error': f'Failed during Fragrantica scraping for "{perfume_name}": {e}'}), 500

    # Crop image and perform OCR
    try:
        x, y, width, height = bounding_box['x'], bounding_box['y'], bounding_box['width'], bounding_box['height']
        left, top, right, bottom = x - width / 2, y - height / 2, x + width / 2, y + height / 2
        cropped_img = img.crop((left, top, right, bottom))

        with io.BytesIO() as output:
            cropped_img.save(output, format="PNG")
            image_bytes_cropped = output.getvalue()

        api_key = os.environ.get("ROBOFLOW_API_KEY")
        ocr_result = perform_ocr(image_bytes_cropped, api_key)
        ocr_text = ocr_result.get('result', '')
    except Exception as e:
        return jsonify({'error': f'Failed during image cropping or OCR: {e}'}), 500

    # Verification
    is_verified = False
    if ocr_text:
        normalized_perfume_name = perfume_name.replace('-', ' ')
        if fuzz.partial_ratio(normalized_perfume_name, ocr_text.lower()) >= 90:
            is_verified = True

    return jsonify({
        'fragrance_profile': fragrance_profile,
        'fragrantica_url': fragrantica_url,
        'ocr_text': ocr_text,
        'is_verified': is_verified
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
