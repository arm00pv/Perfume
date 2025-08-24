import base64
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
from roboflow import Roboflow
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

# Create an 'uploads' directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

def scrape_fragrantica(perfume_name):
    """
    Scrapes Fragrantica.com for perfume notes.
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


@app.route('/api/identify', methods=['POST'])
def identify_perfume():
    # --- 1. Get and Save Image ---
    try:
        data = request.get_json()
        if 'image' not in data:
            return jsonify({'error': 'No image data found in request.'}), 400
        header, encoded = data['image'].split(',', 1)
        image_data = base64.b64decode(encoded)
        image_path = os.path.join('uploads', 'captured_image.png')
        with open(image_path, 'wb') as f:
            f.write(image_data)
    except Exception as e:
        return jsonify({'error': f'Error processing incoming image: {e}'}), 400

    # --- 2. Object Detection ---
    try:
        api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            return jsonify({'error': 'ROBOFLOW_API_KEY environment variable not set on server.'}), 500

        rf = Roboflow(api_key=api_key)
        project = rf.workspace("zixen15").project("perfume-mfzff-sjzin")
        model = project.version(3).model
        prediction = model.predict(image_path, confidence=40, overlap=30).json()
    except Exception as e:
        return jsonify({'error': f'Failed during object detection step: {e}'}), 500

    if not prediction.get('predictions'):
        return jsonify({'error': 'No perfume detected in the image.'})

    # --- 3. Process Top Prediction ---
    top_prediction = sorted(prediction['predictions'], key=lambda x: x['confidence'], reverse=True)[0]
    perfume_name = top_prediction['class']
    detected_labels = [p['class'] for p in prediction['predictions']]

    # --- 4. Scrape Fragrantica ---
    try:
        fragrance_data = scrape_fragrantica(perfume_name)
        if 'error' in fragrance_data:
            fragrance_profile = fragrance_data
            fragrantica_url = None
        else:
            fragrance_profile = fragrance_data.get('notes', {})
            fragrantica_url = fragrance_data.get('url')
    except Exception as e:
        return jsonify({'error': f'Failed during Fragrantica scraping step for "{perfume_name}": {e}'}), 500

    # --- 5. Crop Image and Perform OCR ---
    try:
        img = Image.open(image_path)
        x, y, width, height = top_prediction['x'], top_prediction['y'], top_prediction['width'], top_prediction['height']
        left, top, right, bottom = x - width / 2, y - height / 2, x + width / 2, y + height / 2
        cropped_img = img.crop((left, top, right, bottom))

        with io.BytesIO() as output:
            cropped_img.save(output, format="PNG")
            image_bytes = output.getvalue()

        ocr_result = perform_ocr(image_bytes, api_key)
    except Exception as e:
        return jsonify({'error': f'Failed during image cropping or OCR step: {e}'}), 500

    # --- 6. Verification Logic ---
    is_verified = False
    ocr_text = ""
    if 'result' in ocr_result:
        ocr_text = ocr_result.get('result', '')
        normalized_perfume_name = perfume_name.replace('-', ' ')
        if normalized_perfume_name in ocr_text.lower():
            is_verified = True

    # --- 7. Final Response ---
    return jsonify({
        'detected_labels': detected_labels,
        'fragrance_profile': fragrance_profile,
        'fragrantica_url': fragrantica_url,
        'ocr_text': ocr_text,
        'is_verified': is_verified,
        'raw_prediction': prediction
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
