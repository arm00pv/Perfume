import unittest
from unittest.mock import patch, MagicMock
import app

class TestApp(unittest.TestCase):

    def test_get_recommendation(self):
        notes = {'Top': ['Citrus', 'Lemon'], 'Base': ['Musk']}
        rec = app.get_recommendation(notes)
        self.assertIn("crisp", rec)

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
