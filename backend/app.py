import base64
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

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

        return notes

    except requests.exceptions.RequestException as e:
        return {'error': f"Error fetching from Fragrantica: {e}"}
    except Exception as e:
        return {'error': f"An error occurred during scraping: {e}"}


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

    with open(os.path.join('uploads', 'captured_image.png'), 'wb') as f:
        f.write(image_data)

    # Placeholder for YOLO/Roboflow integration
    return jsonify({
        'message': 'Google Cloud Vision removed. YOLO/Roboflow integration pending.'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
