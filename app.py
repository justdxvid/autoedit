#!/usr/bin/env python3
"""Point-and-click front end for autoedit (stdlib only). Run it, or double-click Start AutoEdit.command."""
import argparse, contextlib, re, shutil, sys, urllib.parse, io, json, os, socket, subprocess, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import autoedit

AUDIO = os.path.expanduser("~/Music/AutoEdit")      # shared music library for every project
PORT = int(os.environ.get("FILMCRAFT_CONTROL_PORT", 9876))

def _setup_path():
    extra = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        for d in [
            os.path.join(local, "AutoEdit", "bin"),
            os.path.join(local, "Microsoft", "WinGet", "Links"),
            os.path.join(local, "FilmCraft"),
            os.path.join(appdata, "npm"),
            os.path.join(userprofile, "scoop", "shims"),
            r"C:\ProgramData\chocolatey\bin",
            r"C:\Program Files\ffmpeg\bin",
        ]:
            if d and os.path.exists(d): extra.append(d)
    elif sys.platform == "darwin":
        extra = [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    else:
        extra = [os.path.expanduser("~/.local/bin"), "/usr/local/bin", "/usr/bin"]
    cur = os.environ.get("PATH", "")
    to_add = [d for d in extra if d not in cur]
    if to_add:
        os.environ["PATH"] = os.pathsep.join(to_add) + os.pathsep + cur

_setup_path()

def current_project():
    try:
        return autoedit.fc(["inspect", "project"], argparse.Namespace(project=TEST_PROJECT, bridge=f"127.0.0.1:{PORT}")).get("path") or "Unsaved project"
    except BaseException:
        return None

TEST_PROJECT = os.environ.get("AUTOEDIT_PROJECT")   # testing: run against a project file instead of the live app

def connected():
    if TEST_PROJECT: return True
    try:
        socket.create_connection(("127.0.0.1", PORT), 0.5).close(); return True
    except OSError:
        return False

def is_filmcraft_running():
    if sys.platform == "win32":
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq filmcraft.exe"], capture_output=True, text=True)
        return "filmcraft.exe" in r.stdout.lower()
    return subprocess.run(["pgrep", "-xi", "filmcraft"], capture_output=True).returncode == 0

def kill_filmcraft():
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'tell application "FilmCraft" to quit']); time.sleep(3)
    elif sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "filmcraft.exe"], capture_output=True); time.sleep(1)
    else:
        subprocess.run(["pkill", "-xi", "filmcraft"]); time.sleep(1)

def find_filmcraft_app():
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        prog = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            shutil.which("filmcraft.exe"),
            shutil.which("filmcraft"),
            os.path.join(local, "FilmCraft", "filmcraft.exe"),
            os.path.join(prog, "FilmCraft", "filmcraft.exe"),
            os.path.join(prog86, "FilmCraft", "filmcraft.exe"),
            os.path.expanduser("~/Projects/filmcraft/target/release/filmcraft.exe"),
            os.path.expanduser("~/Projects/filmcraft/target/debug/filmcraft.exe"),
        ]
        return next((c for c in candidates if c and os.path.exists(c)), None) or "filmcraft.exe"
    return shutil.which("filmcraft") or os.path.expanduser("~/.local/bin/filmcraft")

def launch():
    """Open FilmCraft with the control port; restart it if it is running without one."""
    if connected(): return "FilmCraft is already connected."
    if is_filmcraft_running():
        kill_filmcraft()
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "FilmCraft", "--env", f"FILMCRAFT_CONTROL_PORT={PORT}"])
    else:
        fc_bin = find_filmcraft_app()
        env = os.environ.copy()
        env["FILMCRAFT_CONTROL_PORT"] = str(PORT)
        if fc_bin and (shutil.which(fc_bin) or os.path.exists(fc_bin)):
            subprocess.Popen([fc_bin], env=env)
        else:
            hint = "in PATH, %LOCALAPPDATA%\\FilmCraft, or Program Files" if sys.platform == "win32" else "in PATH or ~/.local/bin"
            return f"FilmCraft not found {hint}. Launch FilmCraft with FILMCRAFT_CONTROL_PORT=9876."
    for _ in range(30):
        time.sleep(0.5)
        if connected(): return "FilmCraft opened and ready."
    return "FilmCraft did not start in time."

import features as F

# panel action -> (function, how to turn the form fields into its arguments)
ACTIONS = {
    "smooth":      (autoedit.smooth,     lambda o: dict(music=o.get("music") or None, frames=int(o["frames"]), music_db=float(o["db"]), mute_original=bool(o["mute"]))),
    "zoom":        (autoedit.zoom,       lambda o: dict(amount=float(o["amount"]))),
    "beatcuts":    (F.beat_cuts,         lambda o: {}),
    "beatzoom":    (F.beat_zoom,         lambda o: dict(every=int(o["every"]), amount=float(o["amount"]))),
    "beatmarkers": (F.beat_markers,      lambda o: dict(every=int(o.get("every", 1)))),
    "captions":    (F.captions,          lambda o: dict(style=o["style"], language=o["language"], force=False)),
    "pauses":      (F.remove_pauses,     lambda o: dict(min=float(o["min"]), keep=0.08, language=o["language"], force=False)),
    "fillers":     (F.remove_fillers,    lambda o: dict(language=o["language"], force=False)),
    "badtakes":    (F.remove_bad_takes,  lambda o: dict(language=o["language"], force=False)),
    "animcaptions":(lambda a: __import__("hf").animated_captions(a), lambda o: dict(style=o["style"], language=o["language"], force=False)),
    "title":       (lambda a: __import__("hf").title_card(a), lambda o: dict(title=o["title"].strip() or "Summer Edit", subtitle=o.get("subtitle", "").strip(),
                                                                         theme=o["theme"], position=o["position"], seconds=float(o.get("seconds", 3)))),
    "outro":       (lambda a: __import__("hf").outro(a), lambda o: dict(title=o["title"].strip() or "Follow for more", subtitle=o.get("subtitle", "").strip(),
                                                                    theme=o["theme"], position=o.get("position", "middle"), seconds=float(o.get("seconds", 3)))),
    "reel":        (F.reel,              lambda o: dict(music=o.get("music") or None, length=float(o["length"]), beats_per_shot=int(o["bps"]), name="AutoReel")),
}
LABELS = {"smooth": "Smooth transitions + music", "zoom": "Slow zoom", "beatcuts": "Snap cuts to the beat",
          "beatzoom": "Beat zooms", "beatmarkers": "Beat markers", "captions": "Captions", "pauses": "Remove pauses",
          "fillers": "Remove um/uh", "badtakes": "Remove bad takes", "reel": "AutoReel",
          "animcaptions": "Animated captions", "title": "Title card", "outro": "Outro"}

if sys.platform == "darwin":
    DATA_DIR = os.path.expanduser("~/Library/Application Support/AutoEdit")
    LOG_DIR = os.path.expanduser("~/Library/Logs")
    UNSAVED_DIR = os.path.expanduser("~/Movies/AutoEdit Projects")
elif sys.platform == "win32":
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
    DATA_DIR = os.path.join(app_data, "AutoEdit")
    LOG_DIR = os.path.join(local_app_data, "AutoEdit", "Logs")
    videos_dir = os.path.expanduser("~/Videos")
    UNSAVED_DIR = os.path.join(videos_dir, "AutoEdit Projects")
else:
    xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    DATA_DIR = os.path.join(xdg_data, "autoedit")
    xdg_state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    LOG_DIR = os.path.join(xdg_state, "autoedit")
    videos_dir = os.path.expanduser("~/Videos")
    movies_dir = os.path.expanduser("~/Movies")
    base_dir = movies_dir if os.path.exists(movies_dir) and not os.path.exists(videos_dir) else videos_dir
    UNSAVED_DIR = os.path.join(base_dir, "AutoEdit Projects")

HISTORY_DIR = os.environ.get("AUTOEDIT_HISTORY_DIR") or os.path.join(DATA_DIR, "history")
HISTORY = os.path.join(HISTORY_DIR, "history.json")
LOG = os.path.join(LOG_DIR, "AutoEdit.log")
hist_lock = threading.Lock()

def load_history():
    try:
        with open(HISTORY, encoding="utf-8") as f:
            return json.load(f)
    except Exception: return []

def save_history(h):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(h[-300:], f, indent=1)

def engine():
    return argparse.Namespace(project=TEST_PROJECT, bridge=f"127.0.0.1:{PORT}")

def project_path(a):
    return autoedit.fc(["inspect", "project"], a).get("path")

def open_folder(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        try:
            os.startfile(path)
        except (AttributeError, OSError):
            subprocess.run(["explorer", os.path.normpath(path)])
    else:
        subprocess.run(["xdg-open", path])

def snapshot(a, cmd):
    """Save a full copy of the project as it is right now (FilmCraft keeps working on the original)."""
    proj = project_path(a)
    if not proj or HISTORY_DIR in proj:
        # never-saved project (or one left on a snapshot): give it a real home first, so a revert restores it there
        os.makedirs(UNSAVED_DIR, exist_ok=True)
        proj = os.path.join(UNSAVED_DIR, time.strftime("Untitled %Y-%m-%d %H.%M.%S.fcproj"))
        autoedit.ex(a, "file.saveAs", path=proj)
        print(f"Your project wasn't saved yet, so AutoEdit saved it as {proj}")
    folder = os.path.join(HISTORY_DIR, re.sub(r"[^\w.-]+", "_", os.path.splitext(os.path.basename(proj))[0]))
    os.makedirs(folder, exist_ok=True)
    snap = os.path.join(folder, time.strftime("%Y%m%d-%H%M%S-") + cmd + ".fcproj")
    autoedit.ex(a, "file.saveCopy", path=snap)
    for old in sorted(os.listdir(folder))[:-60]:      # keep the 60 newest snapshots per project
        try: os.remove(os.path.join(folder, old))
        except OSError: pass
    return proj, snap

def restore(a, entry):
    """Put the project back exactly as it was in the entry's snapshot."""
    autoedit.ex(a, "file.open", path=entry["snap"])
    if entry["project"] != "unsaved":
        autoedit.ex(a, "file.saveAs", path=entry["project"])

def run(cmd, o):
    a = engine()
    buf = io.StringIO()
    entry = None
    try:
        with contextlib.redirect_stdout(buf):
            if cmd == "save":
                autoedit.ex(a, "file.save"); print("Saved.")
                return {"msg": buf.getvalue().strip(), "kind": "info"}
            fn, args = ACTIONS[cmd]
            vars(a).update(args(o))
            proj, snap = snapshot(a, cmd)
            entry = {"id": int(time.time() * 1000), "time": time.strftime("%H:%M"), "action": cmd,
                     "label": LABELS.get(cmd, cmd), "project": proj, "snap": snap, "reverted": False}
            try:
                fn(a)
            except BaseException as e:
                err = str(e) or type(e).__name__
                try:
                    restore(a, entry)
                    print(f"\nThat didn't work, so your project was put back exactly as it was.\n({err})")
                except BaseException as e2:
                    print(f"\nThat didn't work ({err}), and putting the project back also failed ({e2}).")
                return {"msg": buf.getvalue().strip(), "kind": "error"}
    except BaseException as e:
        return {"msg": (buf.getvalue() + f"\nError: {e}").strip(), "kind": "error"}
    entry["result"] = buf.getvalue().strip()
    with hist_lock:
        h = load_history(); h.append(entry); save_history(h)
    return {"msg": entry["result"] or "Done.", "kind": "ok", "entry": entry["id"], "label": entry["label"]}

def revert(entry_id=None):
    """Go back to just before an action (the latest one if no id). Actions after it are undone too."""
    a = engine()
    proj = project_path(a) or "unsaved"
    with hist_lock:
        h = load_history()
        live = [e for e in h if e["project"] == proj and not e["reverted"] and os.path.exists(e["snap"])]
        target = next((e for e in live if e["id"] == entry_id), None) if entry_id else (live[-1] if live else None)
        if not target:
            return {"msg": "Nothing left to undo. Only effects applied from this panel can be reverted here.", "kind": "info"}
        try:
            restore(a, target)
        except BaseException as e:
            return {"msg": f"Could not revert: {e}", "kind": "error"}
        undone = [e for e in live if e["id"] >= target["id"]]
        for e in undone: e["reverted"] = True
        save_history(h)
    names = ", ".join(e["label"] for e in undone)
    return {"msg": f"Reverted: {names}.\nYour project is back to how it was at {target['time']}.", "kind": "info"}

def history():
    a = engine()
    proj = project_path(a) or "unsaved"
    return [{"id": e["id"], "time": e["time"], "label": e["label"], "reverted": e["reverted"], "result": e.get("result", "")[:300]}
            for e in reversed(load_history()) if e["project"] == proj][:25]

AUDIO_EXT = (".wav", ".mp3", ".m4a", ".aiff", ".aif", ".flac", ".ogg", ".aac")

def add_songs(paths):
    """Copy chosen songs into the shared music library; returns the names added."""
    os.makedirs(AUDIO, exist_ok=True)
    added = []
    for p in paths:
        p = p.strip()
        if not p or not os.path.isfile(p) or not p.lower().endswith(AUDIO_EXT): continue
        dest = os.path.join(AUDIO, os.path.basename(p))
        if os.path.abspath(p) != os.path.abspath(dest): shutil.copy2(p, dest)
        added.append(os.path.basename(p))
    return added

PICK_SCRIPT = [
    "tell current application to activate",
    'set f to choose file with prompt "Choose songs for AutoEdit" of type {"public.audio"} with multiple selections allowed',
    'set out to ""',
    "repeat with x in f",
    "set out to out & POSIX path of x & linefeed",
    "end repeat",
    "return out",
]

def pick_songs():
    """Native file picker (PowerShell on Windows, osascript on macOS, zenity/kdialog on Linux)."""
    if sys.platform == "darwin":
        r = subprocess.run(["osascript"] + [x for line in PICK_SCRIPT for x in ("-e", line)], capture_output=True, text=True)
        if r.returncode:
            return "No song chosen." if "-128" in r.stderr or not r.stderr.strip() else f"Error: {r.stderr.strip()}"
        added = add_songs(r.stdout.splitlines())
        return ("Added " + ", ".join(added) + " to your music library.") if added else "Those files aren't songs AutoEdit can use."
    if sys.platform == "win32":
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            "$f.Multiselect = $true; "
            "$f.Filter = 'Audio files (*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.aac)|*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.aac|All files (*.*)|*.*'; "
            "$f.Title = 'Choose songs for AutoEdit'; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $f.FileNames }"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            added = add_songs(r.stdout.strip().splitlines())
            return ("Added " + ", ".join(added) + " to your music library.") if added else "Those files aren't songs AutoEdit can use."
        return "No song chosen."
    if shutil.which("zenity"):
        r = subprocess.run(["zenity", "--file-selection", "--multiple", "--separator=\n",
                            '--file-filter=Audio files | *.wav *.mp3 *.m4a *.aiff *.aif *.flac *.ogg *.aac',
                            '--title=Choose songs for AutoEdit'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            added = add_songs(r.stdout.strip().splitlines())
            return ("Added " + ", ".join(added) + " to your music library.") if added else "Those files aren't songs AutoEdit can use."
        return "No song chosen."
    elif shutil.which("kdialog"):
        r = subprocess.run(["kdialog", "--getopenfilename", os.path.expanduser("~"),
                            "*.wav *.mp3 *.m4a *.aiff *.aif *.flac *.ogg *.aac | Audio files",
                            "--multiple", "--separate-output"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            added = add_songs(r.stdout.strip().splitlines())
            return ("Added " + ", ".join(added) + " to your music library.") if added else "Those files aren't songs AutoEdit can use."
        return "No song chosen."
    open_folder(AUDIO)
    return f"Opened your music folder ({AUDIO}). Drop songs there, or upload via the web panel."

with open(os.path.join(os.path.dirname(__file__), "ui.html"), encoding="utf-8") as _f:
    PAGE = _f.read()

def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + line + "\n")
    except OSError:
        pass

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, ctype="application/json"):
        b = body.encode(); self.send_response(200); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")   # the panel must always get the current page
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/history":
            try: self.send(json.dumps(history()))
            except BaseException: self.send("[]")
            return
        if self.path == "/status":
            music = sorted(f for f in os.listdir(AUDIO) if f.lower().endswith(AUDIO_EXT)) if os.path.isdir(AUDIO) else []
            self.send(json.dumps({"connected": connected(), "project": current_project() if connected() else "", "music": music}))
        else:
            log(f"page loaded by {'panel' if 'AutoEdit' in self.headers.get('User-Agent', '') else 'browser'}")
            with open(os.path.join(os.path.dirname(__file__), "ui.html"), encoding="utf-8") as f:
                self.send(f.read(), "text/html; charset=utf-8")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n)
        if self.path == "/upload":
            os.makedirs(AUDIO, exist_ok=True)
            name = os.path.basename(urllib.parse.unquote(self.headers.get("X-Filename", "music.wav")))
            with open(os.path.join(AUDIO, name), "wb") as f:
                f.write(raw)
            self.send(json.dumps({"ok": True, "name": name}))
            return
        cmd = self.path.strip("/")
        o = json.loads(raw or b"{}")
        log(f"click {cmd} {json.dumps(o)}")
        res = None
        if cmd == "launch": msg = launch()
        elif cmd == "picksong": msg = pick_songs()
        elif cmd in ("revert", "undo"):
            res = revert(o.get("id")) if connected() else {"msg": "FilmCraft isn't connected.", "kind": "error"}
        elif cmd == "musicfolder":
            open_folder(AUDIO)
            msg = "Opened your music folder. Drop songs in it and they appear in the list within a few seconds."
        else:
            if o.get("music"): o["music"] = os.path.join(AUDIO, o["music"])
            res = run(cmd, o) if connected() else {"msg": "FilmCraft isn't connected. Click “Connect FilmCraft” first.", "kind": "error"}
        if res is None: res = {"msg": msg, "kind": "error" if msg.startswith("Error") else "info"}
        log(f"  -> {res['msg'][:300]}")
        self.send(json.dumps(res))

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("AUTOEDIT_PORT", 8765))), H)
    if not os.environ.get("AUTOEDIT_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    print("AutoEdit running at http://127.0.0.1:8765  (Ctrl+C to quit)")
    srv.serve_forever()
