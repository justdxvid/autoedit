import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
import plugin_runner


class TestFilmCraftPlugin(unittest.TestCase):
    def test_manifest_matches_app_actions(self):
        manifest_path = os.path.join(plugin_runner.AUTOEDIT_ROOT, "plugin.json")
        self.assertTrue(os.path.isfile(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["id"], "autoedit")
        self.assertEqual(manifest["name"], "AutoEdit")
        action_ids = {a["id"] for a in manifest["actions"]}
        self.assertEqual(action_ids, set(app.ACTIONS.keys()))

        for action in manifest["actions"]:
            self.assertTrue(action["command"], f"Action {action['id']} missing command")
            self.assertIn("{plugin_dir}/plugin_runner.py", action["command"][1])
            self.assertEqual(action["command"][2], action["id"])

    def test_plugins_dir_cross_platform(self):
        with patch.dict(os.environ, {"FILMCRAFT_PLUGINS_DIR": ""}, clear=False):
            os.environ.pop("FILMCRAFT_PLUGINS_DIR", None)
            os.environ.pop("FILMCRAFT_DATA_DIR", None)

            with patch("sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": r"C:\Users\Tester\AppData\Roaming"}):
                p = plugin_runner.filmcraft_plugins_dir()
                self.assertIn("FilmCraft", p)
                self.assertTrue(p.endswith("plugins"))

            with patch("sys.platform", "darwin"):
                p = plugin_runner.filmcraft_plugins_dir()
                self.assertTrue(p.endswith("Library/Application Support/FilmCraft/plugins"))

            with patch("sys.platform", "linux"), patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg_data"}):
                p = plugin_runner.filmcraft_plugins_dir()
                self.assertEqual(p, os.path.join("/tmp/xdg_data", "filmcraft", "plugins"))

    def test_install_and_uninstall_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            dest = plugin_runner.install_plugin(td)
            self.assertTrue(os.path.isdir(dest))
            self.assertTrue(os.path.isfile(os.path.join(dest, "plugin.json")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "plugin_runner.py")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "autoedit_root.txt")))
            with open(os.path.join(dest, "autoedit_root.txt"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), plugin_runner.AUTOEDIT_ROOT)

            removed = plugin_runner.uninstall_plugin(td)
            self.assertTrue(removed)
            self.assertFalse(os.path.exists(dest))
            self.assertFalse(plugin_runner.uninstall_plugin(td))

    def test_enable_extensions_in_workspaces(self):
        with tempfile.TemporaryDirectory() as td:
            plugins_dir = os.path.join(td, "plugins")
            os.makedirs(plugins_dir, exist_ok=True)
            ws_path = os.path.join(td, "workspaces.json")
            sample_ws = {
                "saved": [
                    {
                        "name": "Editing",
                        "layout": {
                            "Split": {
                                "a": {"Tabs": {"panels": ["Project", "Effects"], "active": 0}},
                                "b": {"Tabs": {"panels": ["Timeline"], "active": 0}},
                            }
                        },
                    }
                ]
            }
            with open(ws_path, "w", encoding="utf-8") as f:
                json.dump(sample_ws, f)

            plugin_runner._enable_extensions_in_workspaces(plugins_dir)
            with open(ws_path, "r", encoding="utf-8") as f:
                updated = json.load(f)
            panels_a = updated["saved"][0]["layout"]["Split"]["a"]["Tabs"]["panels"]
            self.assertIn("Extensions", panels_a)

    def test_run_action_dispatches_with_params(self):
        called = {}

        def fake_zoom(ns):
            called["amount"] = ns.amount
            called["bridge"] = ns.bridge
            print(f"zoom: animated (±{ns.amount}%)")

        with patch.dict(app.ACTIONS, {"zoom": (fake_zoom, app.ACTIONS["zoom"][1])}):
            out = plugin_runner.run_action("zoom", {"amount": 12.5}, bridge="127.0.0.1:9999")
            self.assertEqual(called["amount"], 12.5)
            self.assertEqual(called["bridge"], "127.0.0.1:9999")
            self.assertIn("12.5%", out)

    def test_main_cli_json_params(self):
        def fake_zoom(ns):
            print(f"zoom ok {ns.amount}")

        with patch.dict(app.ACTIONS, {"zoom": (fake_zoom, app.ACTIONS["zoom"][1])}):
            rc = plugin_runner.main(["zoom", "--params-json", '{"amount": 6.0}', "--bridge", "127.0.0.1:9876"])
            self.assertEqual(rc, 0)

    def test_music_protected_does_not_lock_or_trim_voiceover_audio(self):
        import argparse
        import features as F

        seq_state = {
            "video": [{"id": "V1", "locked": False, "items": [{"clip": 1, "item": 10, "start": 0, "end": 10 * F.TICKS}]}],
            "audio": [{"id": "A1", "locked": False, "items": [{"clip": 2, "item": 20, "start": 0, "end": 50 * F.TICKS}]}],
        }
        calls = []

        def fake_ex(a, cid, **kw):
            calls.append((cid, kw))
            if cid == "transcript.inspect":
                return {"items": [{"item": 20, "words": 180}]}
            if cid == "file.mediaProperties":
                it = kw["items"][0]
                if it == 10:
                    return [{"type": "Still", "path": "/tmp/1.jpg"}]
                return [{"type": "AudioOnly", "audio": True, "path": "/tmp/vo.mp3"}]
            return {}

        with patch("features.seq", return_value=seq_state), patch("features.ex", side_effect=fake_ex):
            with F.music_protected(argparse.Namespace()):
                pass

        locked_tracks = [kw["track"] for cid, kw in calls if cid == "timeline.setTrack" and kw.get("locked") is True]
        self.assertIn("V1", locked_tracks)
        self.assertNotIn("A1", locked_tracks)
        trim_calls = [kw for cid, kw in calls if cid == "timeline.trim"]
        self.assertEqual(trim_calls, [])


if __name__ == "__main__":
    unittest.main()
