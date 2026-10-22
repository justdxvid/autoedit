#!/usr/bin/env python3
"""autoedit: one-command edits for FilmCraft.

  autoedit.py smooth  --music song.wav [--frames 15] [--music-db -14] [--mute-original]
  autoedit.py zoom    [--amount 8]
  autoedit.py beatcuts | beatzoom [--every 4 --amount 7] | beatmarkers [--every 1]
  autoedit.py transcribe | captions [--style pop|pastel|clean] [--language en|auto]
  autoedit.py pauses [--min 0.6] | fillers | badtakes
  autoedit.py reel [--music song] [--length 30] [--beats-per-shot 2]
  autoedit.py silences [--noise -35] [--min 0.5]     (report only)

Target: the live app (default, FilmCraft with its control port) or a project file
headless with --project p.fcproj (saved back when done).
"""
import argparse, json, os, re, shutil, subprocess, sys

def find_cli():
    """Stable link first, then the newest unpacked filmcraft-cli in the usual places."""
    import glob
    if os.environ.get("FILMCRAFT_CLI"): return os.environ["FILMCRAFT_CLI"]
    which = shutil.which("filmcraft-cli")
    if which: return which
    link = os.path.expanduser("~/.local/bin/filmcraft-cli")
    if os.path.exists(link): return link
    pats = ["~/tools/filmcraft-cli-*/filmcraft-cli", "~/Downloads/filmcraft-cli-*/filmcraft-cli",
            "~/Applications/filmcraft-cli-*/filmcraft-cli", "/Applications/filmcraft-cli-*/filmcraft-cli",
            "~/Library/Application Support/AutoEdit/filmcraft-cli-*/filmcraft-cli",
            "~/.local/share/autoedit/filmcraft-cli-*/filmcraft-cli",
            "~/Projects/filmcraft/target/release/filmcraft-cli",
            "~/Projects/filmcraft/target/debug/filmcraft-cli"]
    found = sorted(p for pat in pats for p in glob.glob(os.path.expanduser(pat)))
    return found[-1] if found else "filmcraft-cli"

CLI = find_cli()
TICKS = 254016000000

def fc(args, a):
    base = [CLI] + (["--project", a.project, "--save"] if a.project else ["--bridge", a.bridge])
    r = subprocess.run(base + args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"filmcraft-cli failed: {r.stderr.strip() or r.stdout.strip()}")
    return json.loads(r.stdout) if r.stdout.strip().startswith(("{", "[")) else r.stdout

READ_ONLY = {"file.mediaProperties", "transcript.inspect", "captions.list", "history.list", "file.save", "project.items", "transcript.models"}
STEPS = [0]   # edit commands sent so far (each is one FilmCraft undo step)

def ex(a, cid, **p):
    r = fc(["exec", cid, json.dumps(p)], a)
    if cid not in READ_ONLY: STEPS[0] += 1
    return r

def seq(a):
    return fc(["inspect", "sequence"], a)

def video_clips(s):
    t = next(t for t in s["video"] if t["items"])
    return t["items"]

def smooth(a):
    s = seq(a)
    vc = video_clips(s)
    existing = {tr["to"] for t in s["video"] for tr in t["transitions"]}
    added = 0
    for c in vc[1:]:
        if c["clip"] not in existing:
            added += 1
            ex(a, "sequence.applyVideoTransition", clip=c["clip"], effect="cross_dissolve", frames=a.frames, edge="in")
    if a.music:
        item = fc(["import", a.music], a); STEPS[0] += 1
        item = item["items"][0] if isinstance(item, dict) else None
        # an EMPTY audio track for the song, never one holding the clips' own sound (a new one if none is free)
        free = [t for t in s["audio"] if not t["items"]]
        if free:
            track = free[-1]["id"]
        else:
            before = {t["id"] for t in s["audio"]}
            ex(a, "sequence.addTracks", video=0, audio=1)
            track = next(t["id"] for t in seq(a)["audio"] if t["id"] not in before)
        end = s["duration"]
        placed = ex(a, "timeline.place", item=item, audioTrack=track, seconds=0, insert=False, video=False, duration=end)
        ex(a, "clip.audioGain", clips=placed["clips"], mode="set", db=a.music_db)
    if a.mute_original:
        for t in s["audio"][:-1]:
            if t["items"]:
                ex(a, "timeline.setTrack", track=t["id"], muted=True)
    print(f"smooth: {added} dissolves added ({len(vc)-1-added} cuts already had one)" + (", music added" if a.music else ""))

def zoom(a):
    s = seq(a)
    for i, c in enumerate(video_clips(s)):
        base = next(e for e in c["effects"] if e["effect"] == "motion")["params"]["scale"]["value"]
        m = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(base))
        v0 = float(m.group(0)) if m else 100.0
        v1 = v0 * (1 + a.amount / 100) if i % 2 == 0 else v0
        v0 = v0 if i % 2 == 0 else v0 * (1 + a.amount / 100)   # alternate push-in / pull-out
        frame = TICKS * 1001 // 30000 if False else c["duration"] // c["durationFrames"]
        for t, v in ((c["start"], v0), (c["end"] - frame, v1)):
            ex(a, "effects.setParam", clip=c["clip"], effect="motion", param="scale", value=v, time=t, keyframe=True)
    print(f"zoom: {len(video_clips(s))} clips animated (±{a.amount}%)")

def silences(a):
    s = seq(a)
    pf = a.project or fc(["inspect", "project"], a)["path"]
    with open(pf, "r", encoding="utf-8") as f:
        doc = json.load(f)
    paths = {}
    def walk(o):
        if isinstance(o, dict):
            if "path" in o and isinstance(o["path"], str) and o["path"].endswith((".mov", ".mp4", ".MOV", ".MP4")):
                paths[os.path.basename(o["path"])] = o["path"]
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(doc)
    for c in video_clips(s):
        path = paths.get(c["name"])
        if not path or not os.path.exists(path):
            print(f"{c['name']}: media file not found, skipping"); continue
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=n={a.noise}dB:d={a.min}", "-f", "null", "-"], capture_output=True, text=True)
        spans = [l.split("silence_start:")[1].strip() for l in r.stderr.splitlines() if "silence_start" in l]
        print(f"{c['name']}: {len(spans)} silent spans >= {a.min}s")

def normalize_args(args):
    """Allow --project and --bridge to be passed either before or after subcommands."""
    global_flags = {"--project", "--bridge"}
    pulled, rest, i = [], [], 0
    while i < len(args):
        a = args[i]
        if any(a.startswith(f + "=") for f in global_flags):
            pulled.append(a); i += 1
        elif a in global_flags and i + 1 < len(args):
            pulled.extend([a, args[i+1]]); i += 2
        else:
            rest.append(a); i += 1
    return pulled + rest

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project"); p.add_argument("--bridge", default="127.0.0.1:9876")
    sp = p.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("smooth"); m.add_argument("--music"); m.add_argument("--frames", type=int, default=15)
    m.add_argument("--music-db", type=float, default=-14); m.add_argument("--mute-original", action="store_true")
    z = sp.add_parser("zoom"); z.add_argument("--amount", type=float, default=8)
    q = sp.add_parser("silences"); q.add_argument("--noise", type=float, default=-35); q.add_argument("--min", type=float, default=0.5)
    def lang(x): x.add_argument("--language", default="en", help="en, or auto for other languages"); x.add_argument("--force", action="store_true", help="re-transcribe")
    lang(sp.add_parser("transcribe"))
    c = sp.add_parser("captions"); lang(c); c.add_argument("--style", default="pop", choices=["pop", "clean", "pastel"])
    c = sp.add_parser("pauses"); lang(c); c.add_argument("--min", type=float, default=0.6); c.add_argument("--keep", type=float, default=0.15)
    lang(sp.add_parser("fillers")); lang(sp.add_parser("badtakes"))
    c = sp.add_parser("beatmarkers"); c.add_argument("--every", type=int, default=1)
    sp.add_parser("beatcuts")
    c = sp.add_parser("beatzoom"); c.add_argument("--every", type=int, default=4); c.add_argument("--amount", type=float, default=7)
    c = sp.add_parser("reel"); c.add_argument("--music"); c.add_argument("--length", type=float, default=30)
    c.add_argument("--beats-per-shot", type=int, default=2); c.add_argument("--name", default="AutoReel")
    c = sp.add_parser("animcaptions"); lang(c); c.add_argument("--style", default="karaoke", choices=["karaoke", "pastel", "bounce"])
    for name, default in (("title", "Summer Edit"), ("outro", "Follow for more")):
        c = sp.add_parser(name); c.add_argument("--title", default=default); c.add_argument("--subtitle", default="")
        c.add_argument("--theme", default="pastel", choices=["pastel", "bold", "clean"])
        c.add_argument("--position", default="middle", choices=["top", "middle", "bottom"]); c.add_argument("--seconds", type=float, default=3)
    a = p.parse_args(normalize_args(sys.argv[1:]))
    import features as F
    {"smooth": smooth, "zoom": zoom, "silences": silences, "transcribe": F.transcribe, "captions": F.captions,
     "pauses": F.remove_pauses, "fillers": F.remove_fillers, "badtakes": F.remove_bad_takes,
     "beatmarkers": F.beat_markers, "beatcuts": F.beat_cuts, "beatzoom": F.beat_zoom, "reel": F.reel,
     "animcaptions": lambda a: __import__("hf").animated_captions(a),
     "title": lambda a: __import__("hf").title_card(a), "outro": lambda a: __import__("hf").outro(a)}[a.cmd](a)
