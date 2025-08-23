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
        # First, search for the perfume
        search_response = requests.get(search_url, headers=headers)
        search_response.raise_for_status()
        soup = BeautifulSoup(search_response.text, 'html.parser')

        # Find the first search result link
        # This is a bit fragile and might need adjustment if the site structure changes
        first_result = soup.find('div', class_='perfume-card-image')
        if not first_result or not first_result.find('a'):
            return {'error': f'Could not find perfume "{perfume_name}" on Fragrantica.'}

        perfume_url = "https://www.fragrantica.com" + first_result.find('a')['href']

        # Now, scrape the perfume's page
        perfume_response = requests.get(perfume_url, headers=headers)
        perfume_response.raise_for_status()
        perfume_soup = BeautifulSoup(perfume_response.text, 'html.parser')

        # Find the pyramid
        pyramid_container = perfume_soup.find('div', id='pyramid')
        if not pyramid_container:
            return {'error': 'Could not find the fragrance pyramid on the page.'}

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

    # Roboflow OCR API expects base64 encoded image
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    payload = {
        "image": {
            "type": "base64",
            "value": base64_image
        }
    }

    params = {
        'api_key': api_key
    }

    try:
        response = requests.post(ocr_url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f"Error calling OCR API: {e}"}


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
            return jsonify({'error': 'ROBOFLOW_API_KEY environment variable not set.'}), 500

        rf = Roboflow(api_key=api_key)
        project = rf.workspace("zixen15").project("perfume-detection-5gyru")
        model = project.version(3).model

        # Run inference
        prediction = model.predict(image_path, confidence=40, overlap=30).json()

        detected_labels = []
        fragrance_profile = {}
        ocr_result = {}

        if prediction['predictions']:
            # Sort by confidence and take the top one
            top_prediction = sorted(prediction['predictions'], key=lambda x: x['confidence'], reverse=True)[0]
            detected_labels = [p['class'] for p in prediction['predictions']]
            perfume_name = top_prediction['class']

            # Scrape Fragrantica with the identified perfume name
            fragrance_data = scrape_fragrantica(perfume_name)
            if 'error' not in fragrance_data:
                fragrance_profile = fragrance_data.get('notes', {})
                fragrantica_url = fragrance_data.get('url')
            else:
                fragrance_profile = fragrance_data
                fragrantica_url = None


            # --- OCR Step ---
            img = Image.open(image_path)

            # Bounding box coordinates
            x = top_prediction['x']
            y = top_prediction['y']
            width = top_prediction['width']
            height = top_prediction['height']

            # Calculate coordinates for cropping
            left = x - width / 2
            top = y - height / 2
            right = x + width / 2
            bottom = y + height / 2

            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))

            # Convert cropped image to bytes for OCR
            with io.BytesIO() as output:
                cropped_img.save(output, format="PNG")
                image_bytes = output.getvalue()

            # Perform OCR
            ocr_result = perform_ocr(image_bytes, api_key)

        else:
            fragrance_profile = {'error': 'No perfume detected in the image.'}

        # --- Verification Step ---
        is_verified = False
        ocr_text = ""
        if 'result' in ocr_result:
            ocr_text = ocr_result['result']
            # Simple verification: check if the detected class name is in the OCR text
            # (after normalizing the class name from e.g. 'chanel-no-5' to 'chanel no 5')
            normalized_perfume_name = perfume_name.replace('-', ' ')
            if normalized_perfume_name in ocr_text.lower():
                is_verified = True

        return jsonify({
            'detected_labels': detected_labels,
            'fragrance_profile': fragrance_profile,
            'fragrantica_url': fragrantica_url,
            'ocr_text': ocr_text,
            'is_verified': is_verified,
            'raw_prediction': prediction
        })

    except Exception as e:
        return jsonify({'error': f'An error occurred during Roboflow inference: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
