import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autoedit

class TestAutoEdit(unittest.TestCase):
    def test_find_cli_custom_env(self):
        with patch.dict(os.environ, {"FILMCRAFT_CLI": "/custom/path/filmcraft-cli"}):
            self.assertEqual(autoedit.find_cli(), "/custom/path/filmcraft-cli")

    def test_find_cli_returns_valid_string(self):
        cli = autoedit.find_cli()
        self.assertTrue(isinstance(cli, str))
        self.assertTrue(len(cli) > 0)

    def test_ticks_constant(self):
        self.assertEqual(autoedit.TICKS, 254016000000)

    def test_normalize_args_reordering(self):
        # Flags after subcommand are moved before
        argv1 = ["zoom", "--project", "/path/to/proj.fcproj", "--amount", "10"]
        norm1 = autoedit.normalize_args(argv1)
        self.assertEqual(norm1[:2], ["--project", "/path/to/proj.fcproj"])
        self.assertIn("zoom", norm1)
        self.assertIn("--amount", norm1)

        # Flag with equals
        argv2 = ["smooth", "--bridge=127.0.0.1:9876", "--frames", "15"]
        norm2 = autoedit.normalize_args(argv2)
        self.assertEqual(norm2[0], "--bridge=127.0.0.1:9876")
        self.assertIn("smooth", norm2)

    @patch("subprocess.run")
    def test_fc_execution_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"path": "/tmp/test.fcproj"}', stderr="")
        args = MagicMock(project="/tmp/test.fcproj", bridge="127.0.0.1:9876")
        res = autoedit.fc(["inspect", "project"], args)
        self.assertEqual(res, {"path": "/tmp/test.fcproj"})

    @patch("subprocess.run")
    def test_fc_execution_raw_string(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="plain output string", stderr="")
        args = MagicMock(project=None, bridge="127.0.0.1:9876")
        res = autoedit.fc(["help"], args)
        self.assertEqual(res, "plain output string")

    def test_video_clips(self):
        s = {
            "video": [
                {"items": []},
                {"items": [{"clip": 1, "name": "clip1"}, {"clip": 2, "name": "clip2"}]}
            ]
        }
        clips = autoedit.video_clips(s)
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0]["clip"], 1)

    def test_ex_tracks_steps(self):
        autoedit.STEPS[0] = 0
        with patch("autoedit.fc", return_value={"ok": True}):
            a = MagicMock()
            # Non read-only command increments STEPS
            autoedit.ex(a, "timeline.razor", seconds=2.0)
            self.assertEqual(autoedit.STEPS[0], 1)
            # Read-only command does not increment STEPS
            autoedit.ex(a, "file.mediaProperties", items=[1])
            self.assertEqual(autoedit.STEPS[0], 1)

    def test_zoom_calculation(self):
        s = {
            "video": [
                {"items": [
                    {"clip": 1, "start": 0, "end": 254016000000, "duration": 254016000000, "durationFrames": 30,
                     "effects": [{"effect": "motion", "params": {"scale": {"value": "(100)%"}}}]},
                    {"clip": 2, "start": 254016000000, "end": 508032000000, "duration": 254016000000, "durationFrames": 30,
                     "effects": [{"effect": "motion", "params": {"scale": {"value": "(100)%"}}}]}
                ]}
            ]
        }
        with patch("autoedit.seq", return_value=s), patch("autoedit.ex") as mock_ex:
            a = argparse.Namespace(amount=10.0)
            autoedit.zoom(a)
            self.assertEqual(mock_ex.call_count, 4)

    def test_real_project_zoom_and_smooth(self):
        cli = autoedit.find_cli()
        if not shutil.which(cli) and not os.path.exists(cli):
            self.skipTest("filmcraft-cli not found")
        with tempfile.TemporaryDirectory() as td:
            proj_path = os.path.join(td, "demo.fcproj")
            r = autoedit.subprocess.run([cli, "--demo", "exec", "file.saveAs", f"path={proj_path}"],
                                        capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest(f"demo project creation failed: {r.stderr}")
            args = autoedit.argparse.Namespace(project=proj_path, bridge="127.0.0.1:9876", amount=5.0)
            autoedit.zoom(args)
            smooth_args = autoedit.argparse.Namespace(project=proj_path, bridge="127.0.0.1:9876", frames=10, music=None, mute_original=False)
            autoedit.smooth(smooth_args)

    def test_smooth_adds_dissolves(self):
        s = {
            "video": [
                {
                    "items": [{"clip": 1}, {"clip": 2}, {"clip": 3}],
                    "transitions": [{"from": 1, "to": 2, "effect": "crossDissolve"}]
                }
            ],
            "audio": [
                {"id": "a1", "items": [{"clip": 10}]}
            ],
            "duration": 500000000000
        }
        with patch("autoedit.seq", return_value=s), patch("autoedit.ex") as mock_ex:
            a = argparse.Namespace(frames=15, music=None, mute_original=True)
            autoedit.smooth(a)
            # Clip 2 already has transition from 1, so only clip 3 gets a transition
            mock_ex.assert_any_call(a, "sequence.applyVideoTransition", clip=3, effect="cross_dissolve", frames=15, edge="in")

    def test_silences_detection(self):
        s = {
            "video": [
                {"items": [{"name": "clipA.mov"}, {"name": "clipB.mp4"}]}
            ]
        }
        doc = {"media": [{"path": "/media/clipA.mov"}, {"path": "/media/clipB.mp4"}]}
        with tempfile.TemporaryDirectory() as td:
            p_file = os.path.join(td, "proj.fcproj")
            with open(p_file, "w") as f:
                json.dump(doc, f)

            with patch("autoedit.seq", return_value=s), \
                 patch("os.path.exists", return_value=True), \
                 patch("subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(
                    returncode=0,
                    stderr="[silencedetect @ 0x123] silence_start: 1.25\n[silencedetect @ 0x123] silence_end: 2.50\n"
                )
                a = argparse.Namespace(project=p_file, bridge="127.0.0.1:9876", noise=-35, min=0.5)
                # should run without errors
                autoedit.silences(a)
                self.assertEqual(mock_sub.call_count, 2)

if __name__ == "__main__":
    unittest.main()
