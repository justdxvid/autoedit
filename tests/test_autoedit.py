import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autoedit

class TestAutoEdit(unittest.TestCase):
    def test_find_cli(self):
        cli = autoedit.find_cli()
        self.assertTrue(isinstance(cli, str))
        self.assertTrue(len(cli) > 0)

    def test_ticks_constant(self):
        self.assertEqual(autoedit.TICKS, 254016000000)

    @patch("subprocess.run")
    def test_fc_execution(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"path": "/tmp/test.fcproj"}', stderr="")
        args = MagicMock(project="/tmp/test.fcproj", bridge="127.0.0.1:9876")
        res = autoedit.fc(["inspect", "project"], args)
        self.assertEqual(res, {"path": "/tmp/test.fcproj"})

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

    def test_real_project_zoom_and_smooth(self):
        import shutil, tempfile
        cli = autoedit.find_cli()
        if not shutil.which(cli) and not os.path.exists(cli):
            self.skipTest("filmcraft-cli not found")
        with tempfile.TemporaryDirectory() as td:
            proj_path = os.path.join(td, "demo.fcproj")
            # Create project from demo
            r = autoedit.subprocess.run([cli, "--demo", "exec", "file.saveAs", f"path={proj_path}"],
                                        capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest(f"demo project creation failed: {r.stderr}")
            args = autoedit.argparse.Namespace(project=proj_path, bridge="127.0.0.1:9876", amount=5.0)
            autoedit.zoom(args)
            smooth_args = autoedit.argparse.Namespace(project=proj_path, bridge="127.0.0.1:9876", frames=10, music=None, mute_original=False)
            autoedit.smooth(smooth_args)

if __name__ == "__main__":
    unittest.main()
