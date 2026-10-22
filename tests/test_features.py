import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import features as F

class TestFeatures(unittest.TestCase):
    def test_find_whisper_custom_env(self):
        with patch.dict(os.environ, {"WHISPER_CLI": "/custom/whisper-cli"}):
            self.assertEqual(F.find_whisper(), "/custom/whisper-cli")

    def test_find_whisper_returns_valid_string(self):
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

        s24 = {"settings": {"frame_rate": {"num": 24, "den": 1}}}
        self.assertEqual(F.frame_ticks(s24), F.TICKS // 24)

    def test_all_clips(self):
        s = {
            "video": [
                {"items": [{"clip": 1}, {"clip": 2}]},
                {"items": [{"clip": 3}]}
            ],
            "audio": [
                {"items": [{"clip": 4}]}
            ]
        }
        v_clips = F.all_clips(s, "video")
        self.assertEqual(len(v_clips), 3)
        a_clips = F.all_clips(s, "audio")
        self.assertEqual(len(a_clips), 1)

    def test_whisper_words_parsing(self):
        import tempfile
        sample_output = {
            "transcription": [
                {
                    "tokens": [
                        {"text": " Hello", "offsets": {"from": 100, "to": 400}},
                        {"text": " world", "offsets": {"from": 450, "to": 900}},
                        {"text": "[_BEG_]", "offsets": {"from": 900, "to": 950}}
                    ]
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            wav_path = os.path.join(td, "speech.wav")
            with open(wav_path, "wb") as f:
                f.write(b"dummy")

            def mock_sh(cmd, **kwargs):
                # cmd: [whisper, -m, ..., -of, out, ...]
                out_idx = cmd.index("-of") + 1
                out_prefix = cmd[out_idx]
                with open(out_prefix + ".json", "w") as jf:
                    import json
                    json.dump(sample_output, jf)
                return MagicMock(returncode=0)

            with patch("features.sh", side_effect=mock_sh):
                words = F.whisper_words(wav_path, offset=1.0, model="dummy.bin", lang="en")
                self.assertEqual(len(words), 2)
                self.assertEqual(words[0]["text"], "Hello")
                self.assertAlmostEqual(words[0]["start"], 1.1)
                self.assertAlmostEqual(words[0]["end"], 1.4)
                self.assertEqual(words[1]["text"], "world")
                self.assertAlmostEqual(words[1]["start"], 1.45)

    def test_norm(self):
        self.assertEqual(F.norm("Hello, World!"), "helloworld")
        self.assertEqual(F.norm("don't"), "don't")

    def test_find_retake_detected(self):
        words = [
            {"text": "today"}, {"text": "we"}, {"text": "will"},
            {"text": "today"}, {"text": "we"}, {"text": "will"},
            {"text": "show"}, {"text": "you"}
        ]
        retake = F.find_retake(words)
        self.assertIsNotNone(retake)
        self.assertEqual(retake, (0, 3))

    def test_find_retake_none(self):
        words = [
            {"text": "one"}, {"text": "two"}, {"text": "three"},
            {"text": "four"}, {"text": "five"}
        ]
        self.assertIsNone(F.find_retake(words))

    def test_script_font_detection(self):
        # Hindi: Devangari characters
        hindi_text = "नमस्ते दुनिया कैसे हो आप"
        font = F.script_font(hindi_text)
        self.assertEqual(font, "Kohinoor Devanagari")

        # Standard English: Latin characters (returns None, default font used)
        latin_text = "Hello world this is a test"
        self.assertIsNone(F.script_font(latin_text))

if __name__ == "__main__":
    unittest.main()
