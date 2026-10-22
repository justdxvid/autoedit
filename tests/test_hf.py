import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hf

class TestHyperFrames(unittest.TestCase):
    def test_themes_exist(self):
        for name in ["pastel", "bold", "clean"]:
            self.assertIn(name, hf.THEMES)
            self.assertIn("text", hf.THEMES[name])
            self.assertIn("accent", hf.THEMES[name])

    def test_phrases_grouping(self):
        words = [
            {"text": "Hello", "start": 0.0, "end": 0.3},
            {"text": "world", "start": 0.35, "end": 0.7},
            {"text": "Hey", "start": 1.5, "end": 1.8},
            {"text": "there", "start": 1.85, "end": 2.1},
        ]
        groups = hf.phrases(words, gap=0.5)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(len(groups[1]), 2)

    def test_card_doc_generation(self):
        doc = hf.card_doc(1920, 1080, 3.0, "Test Title", "Test Subtitle", "pastel", "top")
        self.assertIn("Test Title", doc)
        self.assertIn("Test Subtitle", doc)
        self.assertIn("data-width=\"1920\"", doc)
        self.assertIn("data-height=\"1080\"", doc)

if __name__ == "__main__":
    unittest.main()
