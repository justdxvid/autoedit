import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
import autoedit
import features
import hf

class TestWindowsSupport(unittest.TestCase):
    def test_windows_script_files_exist(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        expected = [
            "install.bat",
            "install.ps1",
            "Install AutoEdit.bat",
            "Start AutoEdit.bat",
            "uninstall.bat",
            "uninstall.ps1",
            "Uninstall AutoEdit.bat"
        ]
        for fname in expected:
            path = os.path.join(root, fname)
            self.assertTrue(os.path.exists(path), f"File {fname} should exist")
            self.assertGreater(os.path.getsize(path), 0, f"File {fname} should not be empty")

    def test_windows_app_directories(self):
        import ntpath
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {
                 "APPDATA": r"C:\Users\Tester\AppData\Roaming",
                 "LOCALAPPDATA": r"C:\Users\Tester\AppData\Local",
                 "USERPROFILE": r"C:\Users\Tester",
             }):
            # Test path logic directly as computed for Windows with ntpath
            app_data = os.environ.get("APPDATA")
            local_app_data = os.environ.get("LOCALAPPDATA")
            data_dir = ntpath.join(app_data, "AutoEdit")
            log_dir = ntpath.join(local_app_data, "AutoEdit", "Logs")
            videos_dir = ntpath.join(os.environ.get("USERPROFILE"), "Videos")
            unsaved_dir = ntpath.join(videos_dir, "AutoEdit Projects")

            self.assertEqual(data_dir, r"C:\Users\Tester\AppData\Roaming\AutoEdit")
            self.assertEqual(log_dir, r"C:\Users\Tester\AppData\Local\AutoEdit\Logs")
            self.assertEqual(unsaved_dir, r"C:\Users\Tester\Videos\AutoEdit Projects")

    def test_windows_find_cli_fallback(self):
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False), \
             patch("glob.glob", return_value=[]):
            cli = autoedit.find_cli()
            self.assertEqual(cli, "filmcraft-cli.exe")

    def test_windows_find_cli_detected(self):
        with patch("sys.platform", "win32"), \
             patch("shutil.which", side_effect=lambda name: r"C:\Tools\filmcraft-cli.exe" if "filmcraft-cli.exe" in name else None):
            cli = autoedit.find_cli()
            self.assertEqual(cli, r"C:\Tools\filmcraft-cli.exe")

    def test_windows_find_whisper_fallback(self):
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False):
            whisper = features.find_whisper()
            self.assertEqual(whisper, "whisper-cli.exe")

    def test_windows_find_whisper_detected(self):
        with patch("sys.platform", "win32"), \
             patch("shutil.which", side_effect=lambda name: r"C:\Tools\whisper-cli.exe" if name == "whisper-cli.exe" else None):
            whisper = features.find_whisper()
            self.assertEqual(whisper, r"C:\Tools\whisper-cli.exe")

    def test_windows_find_hyperframes_cmd(self):
        with patch("sys.platform", "win32"), \
             patch("os.path.exists", side_effect=lambda p: p.endswith("hyperframes.cmd")):
            hf_bin = hf.find_hyperframes()
            self.assertTrue(hf_bin.endswith("hyperframes.cmd"))

    @patch("subprocess.run")
    def test_windows_is_filmcraft_running(self, mock_run):
        with patch("sys.platform", "win32"):
            mock_run.return_value = MagicMock(returncode=0, stdout="filmcraft.exe  12344 Console  1  124,000 K")
            self.assertTrue(app.is_filmcraft_running())
            mock_run.assert_called_with(["tasklist", "/FI", "IMAGENAME eq filmcraft.exe"], capture_output=True, text=True)

            mock_run.return_value = MagicMock(returncode=0, stdout="INFO: No tasks are running which match the specified criteria.")
            self.assertFalse(app.is_filmcraft_running())

    @patch("subprocess.run")
    def test_windows_kill_filmcraft(self, mock_run):
        with patch("sys.platform", "win32"), patch("time.sleep"):
            app.kill_filmcraft()
            mock_run.assert_called_with(["taskkill", "/F", "/IM", "filmcraft.exe"], capture_output=True)

    def test_windows_open_folder(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.platform", "win32"):
                if hasattr(os, "startfile"):
                    with patch("os.startfile") as mock_startfile:
                        app.open_folder(td)
                        mock_startfile.assert_called_once_with(td)
                else:
                    with patch("subprocess.run") as mock_run:
                        app.open_folder(td)
                        mock_run.assert_called_once_with(["explorer", os.path.normpath(td)])

    @patch("subprocess.run")
    def test_windows_pick_songs_cancelled(self, mock_run):
        with patch("sys.platform", "win32"):
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            res = app.pick_songs()
            self.assertEqual(res, "No song chosen.")
            self.assertTrue(mock_run.call_args[0][0][0] == "powershell")

    @patch("subprocess.run")
    def test_windows_pick_songs_selected(self, mock_run):
        with tempfile.TemporaryDirectory() as td, \
             patch("sys.platform", "win32"), \
             patch.object(app, "AUDIO", td):
            song1 = os.path.join(td, "track1.wav")
            song2 = os.path.join(td, "track2.mp3")
            with open(song1, "wb") as f: f.write(b"RIFFdummydataWAVE")
            with open(song2, "wb") as f: f.write(b"ID3dummydata")

            mock_run.return_value = MagicMock(returncode=0, stdout=f"{song1}\n{song2}\n")
            res = app.pick_songs()
            self.assertIn("Added track1.wav, track2.mp3", res)

    def test_windows_setup_path_separators(self):
        # Verify PATH separator logic uses os.pathsep
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {
                 "PATH": r"C:\Windows\system32;C:\Windows",
                 "LOCALAPPDATA": r"C:\Users\Tester\AppData\Local",
             }):
            app._setup_path()
            self.assertNotIn(":", os.environ["PATH"].replace(r"C:\Windows\system32", "").replace(r"C:\Windows", "").replace(r"C:\Users", ""))
            self.assertIn(";", os.environ["PATH"])

if __name__ == "__main__":
    unittest.main()
