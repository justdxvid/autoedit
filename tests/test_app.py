import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

class MockRequest:
    def __init__(self, raw_input=b""):
        self.raw_input = io.BytesIO(raw_input)
    def makefile(self, *args, **kwargs):
        return self.raw_input

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

    def test_add_songs_filters_invalid_extensions(self):
        with tempfile.TemporaryDirectory() as td:
            txt_path = os.path.join(td, "not_a_song.txt")
            with open(txt_path, "w") as f:
                f.write("text content")
            with patch.object(app, "AUDIO", td):
                added = app.add_songs([txt_path, "nonexistent.mp3"])
                self.assertEqual(added, [])

    def test_history_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            hist_file = os.path.join(td, "history.json")
            with patch.object(app, "HISTORY_DIR", td), patch.object(app, "HISTORY", hist_file):
                entries = [{"id": 1, "time": "12:00", "label": "test", "reverted": False, "project": "test"}]
                app.save_history(entries)
                loaded = app.load_history()
                self.assertEqual(loaded, entries)

    def test_history_corrupt_file_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            hist_file = os.path.join(td, "history.json")
            with open(hist_file, "w") as f:
                f.write("invalid json {{{")
            with patch.object(app, "HISTORY", hist_file):
                self.assertEqual(app.load_history(), [])

    def test_connected_check_false(self):
        with patch("socket.create_connection", side_effect=OSError("connection refused")):
            with patch.object(app, "TEST_PROJECT", None):
                self.assertFalse(app.connected())

    def test_connected_check_true(self):
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value = MagicMock()
            with patch.object(app, "TEST_PROJECT", None):
                self.assertTrue(app.connected())

    def test_connected_check_with_test_project(self):
        with patch.object(app, "TEST_PROJECT", "/path/to/project.fcproj"):
            self.assertTrue(app.connected())

    def test_log_creates_dir_and_appends(self):
        with tempfile.TemporaryDirectory() as td:
            log_file = os.path.join(td, "logs", "test.log")
            with patch.object(app, "LOG", log_file):
                app.log("hello test log")
                self.assertTrue(os.path.exists(log_file))
                with open(log_file) as f:
                    content = f.read()
                    self.assertIn("hello test log", content)

    def test_open_folder(self):
        with tempfile.TemporaryDirectory() as td:
            if sys.platform == "win32" and hasattr(os, "startfile"):
                with patch("os.startfile") as mock_start:
                    app.open_folder(td)
                    mock_start.assert_called_once_with(td)
            else:
                with patch("subprocess.run") as mock_run:
                    app.open_folder(td)
                    mock_run.assert_called_once()

    def test_snapshot_and_restore(self):
        with tempfile.TemporaryDirectory() as td:
            history_dir = os.path.join(td, "history")
            unsaved_dir = os.path.join(td, "unsaved")
            orig_proj = os.path.join(td, "my_project.fcproj")
            with open(orig_proj, "w") as f:
                f.write("{}")

            with patch.object(app, "HISTORY_DIR", history_dir), \
                 patch.object(app, "UNSAVED_DIR", unsaved_dir), \
                 patch("autoedit.fc", return_value={"path": orig_proj}), \
                 patch("autoedit.ex") as mock_ex:
                
                a = app.engine()
                proj, snap = app.snapshot(a, "zoom")
                self.assertEqual(proj, orig_proj)
                mock_ex.assert_called_with(a, "file.saveCopy", path=snap)

                entry = {"project": orig_proj, "snap": snap}
                app.restore(a, entry)
                mock_ex.assert_any_call(a, "file.open", path=snap)
                mock_ex.assert_any_call(a, "file.saveAs", path=orig_proj)

    def test_pick_songs_zenity(self):
        with tempfile.TemporaryDirectory() as td:
            song = os.path.join(td, "track.mp3")
            with open(song, "wb") as f: f.write(b"ID3")
            with patch("sys.platform", "linux"), \
                 patch("shutil.which", side_effect=lambda x: "/usr/bin/zenity" if x == "zenity" else None), \
                 patch("subprocess.run") as mock_sub, \
                 patch.object(app, "AUDIO", td):
                mock_sub.return_value = MagicMock(returncode=0, stdout=song + "\n")
                msg = app.pick_songs()
                self.assertIn("Added track.mp3", msg)

    def test_pick_songs_fallback_folder(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.platform", "linux"), \
                 patch("shutil.which", return_value=None), \
                 patch.object(app, "open_folder") as mock_open, \
                 patch.object(app, "AUDIO", td):
                msg = app.pick_songs()
                mock_open.assert_called_once_with(td)
                self.assertIn("Opened your music folder", msg)

    def test_run_action_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            hist_file = os.path.join(td, "history.json")
            proj_file = os.path.join(td, "test.fcproj")
            snap_file = os.path.join(td, "snap.fcproj")
            with open(proj_file, "w") as f: f.write("{}")
            with open(snap_file, "w") as f: f.write("{}")

            with patch.object(app, "HISTORY_DIR", td), \
                 patch.object(app, "HISTORY", hist_file), \
                 patch("app.snapshot", return_value=(proj_file, snap_file)), \
                 patch("app.restore") as mock_restore, \
                 patch("app.project_path", return_value=proj_file):

                # 1. Success run
                dummy_fn = MagicMock(side_effect=lambda a: print("applied zoom"))
                with patch.dict(app.ACTIONS, {"zoom": (dummy_fn, lambda o: {"amount": 5.0})}):
                    res = app.run("zoom", {"amount": 5.0})
                    self.assertEqual(res["kind"], "ok")
                    self.assertIn("applied zoom", res["msg"])
                    h = app.load_history()
                    self.assertEqual(len(h), 1)
                    self.assertEqual(h[0]["action"], "zoom")

                # 2. Revert run
                rev_res = app.revert(h[0]["id"])
                self.assertEqual(rev_res["kind"], "info")
                self.assertIn("Reverted", rev_res["msg"])
                mock_restore.assert_called_once()
                h2 = app.load_history()
                self.assertTrue(h2[0]["reverted"])

                # 3. Failing run triggers auto-restore
                failing_fn = MagicMock(side_effect=RuntimeError("simulated render failure"))
                with patch.dict(app.ACTIONS, {"smooth": (failing_fn, lambda o: {})}):
                    fail_res = app.run("smooth", {})
                    self.assertEqual(fail_res["kind"], "error")
                    self.assertIn("simulated render failure", fail_res["msg"])
                    # restore should have been called again
                    self.assertEqual(mock_restore.call_count, 2)

if __name__ == "__main__":
    unittest.main()
