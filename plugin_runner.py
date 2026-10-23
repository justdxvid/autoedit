#!/usr/bin/env python3
"""FilmCraft native plugin runner and installer for AutoEdit (Linux, macOS, Windows)."""
import argparse
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_PTR = os.path.join(HERE, "autoedit_root.txt")
if os.path.isfile(ROOT_PTR):
    with open(ROOT_PTR, "r", encoding="utf-8") as _f:
        AUTOEDIT_ROOT = _f.read().strip()
else:
    AUTOEDIT_ROOT = HERE

if AUTOEDIT_ROOT not in sys.path:
    sys.path.insert(0, AUTOEDIT_ROOT)


def filmcraft_plugins_dir():
    """Return FilmCraft's cross-platform plugins directory."""
    override = os.environ.get("FILMCRAFT_PLUGINS_DIR")
    if override:
        return override
    data_override = os.environ.get("FILMCRAFT_DATA_DIR")
    if data_override:
        return os.path.join(data_override, "plugins")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/FilmCraft/plugins")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(appdata, "FilmCraft", "plugins")
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "filmcraft", "plugins")


def _enable_extensions_in_workspaces(plugins_root):
    """Ensure saved workspaces in FilmCraft's workspaces.json include the Extensions panel."""
    data_dir = os.path.dirname(os.path.abspath(plugins_root))
    ws_path = os.path.join(data_dir, "workspaces.json")
    if not os.path.isfile(ws_path):
        return
    try:
        with open(ws_path, "r", encoding="utf-8") as f:
            ws = json.load(f)
    except Exception:
        return

    def inject_tab(node):
        if not isinstance(node, dict):
            return False
        if "Tabs" in node and isinstance(node["Tabs"], dict):
            panels = node["Tabs"].get("panels", [])
            if "Extensions" in panels:
                return True
            if "History" in panels or "Effects" in panels or "Project" in panels:
                panels.append("Extensions")
                return True
        if "Split" in node and isinstance(node["Split"], dict):
            sp = node["Split"]
            return inject_tab(sp.get("a")) or inject_tab(sp.get("b"))
        return False

    changed = False
    entries = ws.get("saved", []) if isinstance(ws, dict) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        layout = entry.get("layout")
        if isinstance(layout, dict) and inject_tab(layout):
            changed = True
    if changed:
        try:
            with open(ws_path, "w", encoding="utf-8") as f:
                json.dump(ws, f, indent=2)
        except Exception:
            pass


def _patch_local_filmcraft_repo():
    """If a local FilmCraft checkout exists without the Extensions panel, apply our bundled patch."""
    import subprocess
    patch_file = os.path.join(AUTOEDIT_ROOT, "filmcraft_patch", "extensions.patch")
    if not os.path.isfile(patch_file):
        return
    candidates = [
        os.environ.get("FILMCRAFT_SRC", ""),
        os.path.join(os.path.dirname(AUTOEDIT_ROOT), "filmcraft"),
        os.path.expanduser("~/Projects/filmcraft"),
        os.path.expanduser("~/filmcraft"),
    ]
    for repo in candidates:
        if not repo or not os.path.isdir(os.path.join(repo, "crates", "ui-egui", "src", "panels")):
            continue
        ext_rs = os.path.join(repo, "crates", "ui-egui", "src", "panels", "extensions.rs")
        if os.path.isfile(ext_rs):
            return
        try:
            chk = subprocess.run(["git", "apply", "--check", patch_file], cwd=repo, capture_output=True)
            if chk.returncode == 0:
                subprocess.run(["git", "apply", patch_file], cwd=repo, capture_output=True)
        except Exception:
            pass
        return


def _activate_live_extensions_panel():
    """If FilmCraft is currently running on the control bridge, reload & reveal the Extensions panel."""
    import socket
    import subprocess
    port = int(os.environ.get("FILMCRAFT_CONTROL_PORT", "9876"))
    try:
        socket.create_connection(("127.0.0.1", port), 0.3).close()
    except OSError:
        return
    try:
        import autoedit
        cli = autoedit.find_cli()
        bridge = f"127.0.0.1:{port}"
        subprocess.run([cli, "--bridge", bridge, "exec", "extensions.reload", "{}"], capture_output=True, timeout=2)
        subprocess.run([cli, "--bridge", bridge, "exec", "extensions.open", '{"id":"autoedit"}'], capture_output=True, timeout=2)
    except Exception:
        pass


def install_plugin(target_root=None):
    """Install AutoEdit into FilmCraft's plugins directory and reveal the Extensions panel."""
    plugins_root = target_root or filmcraft_plugins_dir()
    dest = os.path.join(plugins_root, "autoedit")
    os.makedirs(dest, exist_ok=True)
    src_manifest = os.path.join(AUTOEDIT_ROOT, "plugin.json")
    src_runner = os.path.join(AUTOEDIT_ROOT, "plugin_runner.py")
    shutil.copy2(src_manifest, os.path.join(dest, "plugin.json"))
    shutil.copy2(src_runner, os.path.join(dest, "plugin_runner.py"))
    with open(os.path.join(dest, "autoedit_root.txt"), "w", encoding="utf-8") as f:
        f.write(AUTOEDIT_ROOT)
    src_hf = os.path.join(AUTOEDIT_ROOT, "hyperframes")
    dest_hf = os.path.join(dest, "hyperframes")
    if os.path.isdir(src_hf) and os.path.abspath(src_hf) != os.path.abspath(dest_hf) and not os.path.exists(dest_hf):
        try:
            os.symlink(src_hf, dest_hf, target_is_directory=True)
        except OSError:
            pass
    _enable_extensions_in_workspaces(plugins_root)
    if target_root is None:
        _patch_local_filmcraft_repo()
        _activate_live_extensions_panel()
    return dest


def uninstall_plugin(target_root=None):
    """Remove AutoEdit from FilmCraft's plugins directory."""
    plugins_root = target_root or filmcraft_plugins_dir()
    dest = os.path.join(plugins_root, "autoedit")
    if os.path.exists(dest):
        shutil.rmtree(dest)
        return True
    return False


DEFAULT_PARAMS = {
    "smooth": {"frames": 15, "music": "", "db": -14.0, "mute": False},
    "zoom": {"amount": 8.0},
    "beatcuts": {},
    "beatzoom": {"every": 4, "amount": 7.0},
    "beatmarkers": {"every": 1},
    "captions": {"style": "pop", "language": "auto"},
    "animcaptions": {"style": "karaoke", "language": "auto"},
    "pauses": {"min": 0.3, "language": "auto"},
    "fillers": {"language": "auto"},
    "badtakes": {"language": "auto"},
    "title": {"title": "Summer Edit", "subtitle": "", "theme": "pastel", "position": "middle", "seconds": 3.0},
    "outro": {"title": "Follow for more", "subtitle": "", "theme": "pastel", "position": "middle", "seconds": 3.0},
    "reel": {"music": "", "length": 30.0, "bps": 2},
}


def run_action(action_id, raw_params=None, bridge=None, project=None):
    """Execute an AutoEdit plugin action against FilmCraft."""
    import app
    import autoedit

    if action_id not in app.ACTIONS:
        raise ValueError(f"Unknown AutoEdit plugin action: {action_id}")

    merged = dict(DEFAULT_PARAMS.get(action_id, {}))
    if raw_params:
        merged.update(raw_params)

    fn, build_kwargs = app.ACTIONS[action_id]
    kwargs = build_kwargs(merged)

    port = os.environ.get("FILMCRAFT_CONTROL_PORT", "9876")
    bridge_addr = bridge or os.environ.get("FILMCRAFT_BRIDGE") or f"127.0.0.1:{port}"
    proj_path = project if project is not None else os.environ.get("AUTOEDIT_PROJECT")

    ns = argparse.Namespace(project=proj_path, bridge=bridge_addr, **kwargs)
    autoedit.STEPS[0] = 0
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        fn(ns)
    finally:
        sys.stdout = old_stdout
    out = buf.getvalue().strip()
    return out or f"{app.LABELS.get(action_id, action_id)}: done"


def main(argv=None):
    parser = argparse.ArgumentParser(description="AutoEdit FilmCraft Plugin Runner")
    parser.add_argument("action", nargs="?", help="Action ID to execute, or 'install' / 'uninstall'")
    parser.add_argument("--params-json", default=None, help="JSON object of action parameters")
    parser.add_argument("--bridge", default=None, help="FilmCraft control bridge host:port")
    parser.add_argument("--project", default=None, help="Offline .fcproj path")
    args = parser.parse_args(argv)

    if args.action == "install":
        dest = install_plugin()
        print(f"Installed AutoEdit plugin to {dest}")
        return 0
    if args.action == "uninstall":
        removed = uninstall_plugin()
        print("Removed AutoEdit plugin." if removed else "AutoEdit plugin was not installed.")
        return 0
    if not args.action:
        parser.print_help()
        return 2

    raw_json = args.params_json or os.environ.get("AUTOEDIT_PARAMS_JSON") or "{}"
    try:
        params = json.loads(raw_json)
    except Exception as exc:
        sys.stderr.write(f"Invalid parameter JSON: {exc}\n")
        return 1

    try:
        msg = run_action(args.action, params, bridge=args.bridge, project=args.project)
        print(msg)
        return 0
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, str):
            sys.stderr.write(f"{code}\n")
            return 1
        return int(code or 0)
    except Exception as exc:
        sys.stderr.write(f"AutoEdit error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
