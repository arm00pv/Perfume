import unittest
from unittest.mock import patch, MagicMock
import app

class TestApp(unittest.TestCase):

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

if __name__ == '__main__':
    unittest.main()
