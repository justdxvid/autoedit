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
            self.assertIn("pill", hf.THEMES[name])
            self.assertIn("shadow", hf.THEMES[name])

    def test_caption_styles(self):
        for style in ["karaoke", "pastel", "bounce"]:
            self.assertIn(style, hf.CAPTION_STYLES)
            self.assertIn("theme", hf.CAPTION_STYLES[style])
            self.assertIn("highlight", hf.CAPTION_STYLES[style])
            self.assertIn("enter", hf.CAPTION_STYLES[style])

    def test_phrases_grouping_normal(self):
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

    def test_phrases_empty(self):
        self.assertEqual(hf.phrases([]), [])

    def test_phrases_punctuation_split(self):
        words = [
            {"text": "Stop!", "start": 0.0, "end": 0.4},
            {"text": "Go", "start": 0.5, "end": 0.8},
        ]
        groups = hf.phrases(words, gap=1.0)
        self.assertEqual(len(groups), 2)

    def test_card_doc_generation(self):
        for pos in ["top", "middle", "bottom"]:
            for th in ["pastel", "bold", "clean"]:
                doc = hf.card_doc(1920, 1080, 3.0, "Test Title", "Test Subtitle", th, pos)
                self.assertIn("Test Title", doc)
                self.assertIn("Test Subtitle", doc)
                self.assertIn("data-width=\"1920\"", doc)
                self.assertIn("data-height=\"1080\"", doc)

    def test_captions_doc_generation(self):
        groups = [
            [{"text": "Hello", "start": 0.0, "end": 0.5}, {"text": "world", "start": 0.6, "end": 1.0}]
        ]
        for style in ["karaoke", "pastel", "bounce"]:
            doc = hf.captions_doc(1080, 1920, 2.0, groups, style)
            self.assertIn("Hello", doc)
            self.assertIn("world", doc)
            self.assertIn("data-width=\"1080\"", doc)
            self.assertIn("data-height=\"1920\"", doc)

    def test_seq_format(self):
        s = {
            "settings": {
                "width": 1920,
                "height": 1080,
                "frame_rate": {"num": 60, "den": 1}
            }
        }
        w, h, fps = hf.seq_format(s)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)
        self.assertEqual(fps, 60)

if __name__ == "__main__":
    unittest.main()
