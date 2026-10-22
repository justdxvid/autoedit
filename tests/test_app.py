import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

class TestApp(unittest.TestCase):
    def test_paths_configured(self):
        self.assertTrue(os.path.isabs(app.AUDIO))
        self.assertTrue(os.path.isabs(app.HISTORY_DIR))
        self.assertTrue(os.path.isabs(app.UNSAVED_DIR))
        self.assertTrue(os.path.isabs(app.LOG))

    def test_add_songs(self):
        with tempfile.TemporaryDirectory() as td:
            song_path = os.path.join(td, "test_song.wav")
            with open(song_path, "wb") as f:
                f.write(b"RIFFdummydataWAVE")
            
            with tempfile.TemporaryDirectory() as audio_dir:
                with patch.object(app, "AUDIO", audio_dir):
                    added = app.add_songs([song_path])
                    self.assertEqual(added, ["test_song.wav"])
                    self.assertTrue(os.path.exists(os.path.join(audio_dir, "test_song.wav")))

    def test_history_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            hist_file = os.path.join(td, "history.json")
            with patch.object(app, "HISTORY_DIR", td), patch.object(app, "HISTORY", hist_file):
                entries = [{"id": 1, "time": "12:00", "label": "test", "reverted": False, "project": "test"}]
                app.save_history(entries)
                loaded = app.load_history()
                self.assertEqual(loaded, entries)

    def test_connected_check_false(self):
        with patch("socket.create_connection", side_effect=OSError("connection refused")):
            with patch.object(app, "TEST_PROJECT", None):
                self.assertFalse(app.connected())

if __name__ == "__main__":
    unittest.main()
