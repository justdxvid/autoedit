import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import features as F

class TestFeatures(unittest.TestCase):
    def test_find_whisper(self):
        whisper = F.find_whisper()
        self.assertTrue(isinstance(whisper, str))
        self.assertTrue(len(whisper) > 0)

    def test_model_file_names(self):
        with patch("os.path.exists", return_value=True):
            en_path = F.model_file("en")
            self.assertTrue(en_path.endswith("ggml-base.en.bin"))
            other_path = F.model_file("es")
            self.assertTrue(other_path.endswith("ggml-small.bin"))

    def test_frame_ticks(self):
        s = {"settings": {"frame_rate": {"num": 30, "den": 1}}}
        ticks = F.frame_ticks(s)
        self.assertEqual(ticks, F.TICKS // 30)

    def test_all_clips(self):
        s = {
            "video": [
                {"items": [{"clip": 1}, {"clip": 2}]},
                {"items": [{"clip": 3}]}
            ]
        }
        clips = F.all_clips(s, "video")
        self.assertEqual(len(clips), 3)

if __name__ == "__main__":
    unittest.main()
