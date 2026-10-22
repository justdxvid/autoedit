import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

class MockHTTPHandler:
    """Simulates BaseHTTPRequestHandler methods to test handler logic."""
    def __init__(self, path, method="GET", headers=None, rfile_bytes=b""):
        self.path = path
        self.command = method
        self.headers = headers or {}
        import io
        self.rfile = io.BytesIO(rfile_bytes)
        self.wfile = io.BytesIO()
        self.response_code = None
        self.response_headers = {}

    def send_response(self, code):
        self.response_code = code

    def send_header(self, key, val):
        self.response_headers[key] = val

    def end_headers(self):
        pass

    def log_message(self, *args):
        pass

    def send(self, body, ctype="application/json"):
        if isinstance(body, str):
            b = body.encode()
        else:
            b = body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

class TestServer(unittest.TestCase):
    def test_get_status_disconnected(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(app, "AUDIO", td), \
                 patch.object(app, "connected", return_value=False):
                handler = MockHTTPHandler("/status")
                app.H.do_GET(handler)
                self.assertEqual(handler.response_code, 200)
                body = json.loads(handler.wfile.getvalue().decode())
                self.assertFalse(body["connected"])
                self.assertEqual(body["project"], "")
                self.assertEqual(body["music"], [])

    def test_get_status_with_music(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "track1.mp3"), "w") as f: f.write("x")
            with open(os.path.join(td, "track2.wav"), "w") as f: f.write("x")
            with open(os.path.join(td, "notes.txt"), "w") as f: f.write("ignore")
            with patch.object(app, "AUDIO", td), \
                 patch.object(app, "connected", return_value=True), \
                 patch.object(app, "current_project", return_value="/tmp/test.fcproj"):
                handler = MockHTTPHandler("/status")
                app.H.do_GET(handler)
                body = json.loads(handler.wfile.getvalue().decode())
                self.assertTrue(body["connected"])
                self.assertEqual(body["project"], "/tmp/test.fcproj")
                self.assertEqual(body["music"], ["track1.mp3", "track2.wav"])

    def test_get_history(self):
        entries = [{"id": 1, "time": "12:00", "label": "zoom", "reverted": False, "result": "ok"}]
        with patch.object(app, "history", return_value=entries):
            handler = MockHTTPHandler("/history")
            app.H.do_GET(handler)
            self.assertEqual(handler.response_code, 200)
            body = json.loads(handler.wfile.getvalue().decode())
            self.assertEqual(body, entries)

    def test_get_ui_html(self):
        handler = MockHTTPHandler("/")
        app.H.do_GET(handler)
        self.assertEqual(handler.response_code, 200)
        self.assertIn(b"<!doctype html>", handler.wfile.getvalue())

    def test_post_upload(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(app, "AUDIO", td):
                data = b"RIFFsamplewavdata"
                handler = MockHTTPHandler("/upload", method="POST",
                                          headers={"Content-Length": str(len(data)), "X-Filename": "my_beat.wav"},
                                          rfile_bytes=data)
                app.H.do_POST(handler)
                self.assertEqual(handler.response_code, 200)
                body = json.loads(handler.wfile.getvalue().decode())
                self.assertTrue(body["ok"])
                self.assertEqual(body["name"], "my_beat.wav")
                self.assertTrue(os.path.exists(os.path.join(td, "my_beat.wav")))

    def test_post_musicfolder(self):
        with patch("app.open_folder") as mock_open:
            handler = MockHTTPHandler("/musicfolder", method="POST", headers={"Content-Length": "0"})
            app.H.do_POST(handler)
            self.assertEqual(handler.response_code, 200)
            body = json.loads(handler.wfile.getvalue().decode())
            self.assertEqual(body["kind"], "info")
            mock_open.assert_called_once()

    def test_post_picksong(self):
        with patch("app.pick_songs", return_value="Song chosen."):
            handler = MockHTTPHandler("/picksong", method="POST", headers={"Content-Length": "0"})
            app.H.do_POST(handler)
            self.assertEqual(handler.response_code, 200)
            body = json.loads(handler.wfile.getvalue().decode())
            self.assertIn("Song chosen", body["msg"])

if __name__ == "__main__":
    unittest.main()
