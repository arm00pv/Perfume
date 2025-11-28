import unittest
from unittest.mock import patch, MagicMock
import app
import json
import base64
from io import BytesIO
from PIL import Image

class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = app.app
        self.client = self.app.test_client()
        self.app.config['TESTING'] = True

    def test_get_recommendation_and_similars(self):
        notes = {'Top': ['Citrus', 'Lemon'], 'Base': ['Musk']}
        rec, similars = app.get_recommendation_and_similars(notes)
        self.assertIn("clean", rec) # "clean" is in 'fresh' description
        self.assertIsInstance(similars, list)
        self.assertTrue(len(similars) > 0)

    @patch('app.easyocr.Reader')
    def test_lazy_loading(self, mock_reader):
        # Ensure reader is None initially
        app.reader = None

        # Call get_reader
        r = app.get_reader()

        # Check if Reader was initialized
        mock_reader.assert_called_once_with(['en'])
        self.assertIsNotNone(app.reader)

        # Call again, should not initialize again
        app.get_reader()
        mock_reader.assert_called_once()

    def test_chat_response(self):
        # Test Definition
        resp = app.chat_response("What is Oud?")
        self.assertIn("resinous", resp.lower())

        # Test Recommendation
        resp = app.chat_response("Recommend a fresh scent")
        self.assertIn("recommend", resp.lower())
        self.assertIn("fresh", resp.lower())

        # Test Mixing
        resp = app.chat_response("Can I mix rose and oud?")
        self.assertIn("layering", resp.lower())

    def test_mix_perfumes(self):
        # Mock scrape_fragrantica
        with patch('app.scrape_fragrantica') as mock_scrape:
            mock_scrape.side_effect = [
                {'name': 'Perfume A', 'notes': {'Top': ['Lemon']}, 'image_url': 'url1'},
                {'name': 'Perfume B', 'notes': {'Top': ['Vanilla']}, 'image_url': 'url2'}
            ]

            response = self.client.post('/api/mix',
                                      data=json.dumps({'perfume1': 'A', 'perfume2': 'B'}),
                                      content_type='application/json')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('Perfume A x Perfume B', data['name'])
            self.assertIn('Lemon', data['notes']['Top'])
            self.assertIn('Vanilla', data['notes']['Top'])

    def test_vibe_check_mock(self):
         # Mock vision engine components
         with patch('app.get_vision_engine') as mock_engine_getter:
            mock_vision = MagicMock()
            mock_vision.extract_colors.return_value = ['#ff0000', '#00ff00']
            mock_vision.analyze_color_psychology.return_value = {
                'vibe': 'energetic',
                'dominant_color_name': 'red',
                'predicted_notes': ['Pepper']
            }
            mock_engine_getter.return_value = mock_vision

            # Create dummy image
            img_byte_arr = BytesIO()
            Image.new('RGB', (100, 100), color='red').save(img_byte_arr, format='PNG')
            encoded_img = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

            response = self.client.post('/api/vibe_check',
                                        data=json.dumps({'image': f"data:image/png;base64,{encoded_img}"}),
                                        content_type='application/json')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['vibe'], 'energetic')
            self.assertEqual(data['color_name'], 'red')

if __name__ == '__main__':
    unittest.main()
