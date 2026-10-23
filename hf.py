"""Motion graphics for AutoEdit, rendered with HyperFrames (HTML -> transparent video).

Each feature writes a small HyperFrames composition sized to the active sequence, renders it to
WebM with alpha (FilmCraft reads VP9 alpha; it is ~80x smaller than ProRes 4444), imports it and
lays it on a video track above the footage.
"""
import glob, html, json, os, re, shutil, subprocess, sys, tempfile, time
from autoedit import ex, fc, seq, TICKS, STEPS
import features as F

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
            r"C:\Program Files\nodejs",
        ]:
            if d and os.path.exists(d): extra.append(d)
    elif sys.platform == "darwin":
        extra = [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    else:
        extra = [os.path.expanduser("~/.local/bin"), "/usr/local/bin", "/usr/bin"]
    if sys.platform != "win32":
        for pat in [
            "~/.local/share/mise/shims",
            "~/.local/share/mise/installs/node/*/bin",
            "~/.nvm/versions/node/*/bin",
            "~/.volta/bin",
            "~/.bun/bin",
        ]:
            for p in sorted(glob.glob(os.path.expanduser(pat)), reverse=True):
                if os.path.isdir(p):
                    extra.append(p)
    cur = os.environ.get("PATH", "")
    to_add = [d for d in extra if d not in cur]
    if to_add:
        os.environ["PATH"] = os.pathsep.join(to_add) + os.pathsep + cur

_setup_path()

HERE = os.path.dirname(os.path.abspath(__file__))

def _find_hf_dir():
    candidates = [
        os.path.join(HERE, "hyperframes"),
        os.path.expanduser("~/.local/share/autoedit/hyperframes"),
        os.path.expanduser("~/Library/Application Support/AutoEdit/hyperframes"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "AutoEdit", "hyperframes"),
        os.path.expanduser("~/Projects/autoedit/hyperframes"),
    ]
    for d in candidates:
        if d and os.path.isdir(os.path.join(d, "node_modules")):
            return d
    for d in candidates:
        if d and os.path.isfile(os.path.join(d, "package.json")):
            return d
    return os.path.join(HERE, "hyperframes")

HF_DIR = _find_hf_dir()
GSAP = os.path.join(HF_DIR, "node_modules", "gsap", "dist", "gsap.min.js")

def find_hyperframes():
    hf_dir = _find_hf_dir()
    bin_name = "hyperframes.cmd" if sys.platform == "win32" else "hyperframes"
    hf_path = os.path.join(hf_dir, "node_modules", ".bin", bin_name)
    if os.path.exists(hf_path): return hf_path
    fallback = os.path.join(hf_dir, "node_modules", ".bin", "hyperframes")
    if os.path.exists(fallback): return fallback
    which = shutil.which(bin_name) or shutil.which("hyperframes")
    return which or hf_path

def _ensure_hyperframes():
    global HF_DIR, GSAP
    HF_DIR = _find_hf_dir()
    GSAP = os.path.join(HF_DIR, "node_modules", "gsap", "dist", "gsap.min.js")
    hf_bin = find_hyperframes()
    if (os.path.exists(hf_bin) or shutil.which(hf_bin)) and os.path.exists(GSAP):
        return hf_bin
    npm_bin = shutil.which("npm.cmd" if sys.platform == "win32" else "npm") or shutil.which("npm")
    if npm_bin and os.path.isfile(os.path.join(HF_DIR, "package.json")):
        subprocess.run([npm_bin, "install", "--no-audit", "--no-fund"], cwd=HF_DIR,
                       capture_output=True, text=True, shell=(sys.platform == "win32"))
        HF_DIR = _find_hf_dir()
        GSAP = os.path.join(HF_DIR, "node_modules", "gsap", "dist", "gsap.min.js")
        hf_bin = find_hyperframes()
    return hf_bin

HF = find_hyperframes()

if sys.platform == "darwin":
    OUT = os.path.expanduser("~/Movies/AutoEdit Overlays")
elif sys.platform == "win32":
    videos_dir = os.path.expanduser("~/Videos")
    OUT = os.path.join(videos_dir, "AutoEdit Overlays")
else:
    videos_dir = os.path.expanduser("~/Videos")
    movies_dir = os.path.expanduser("~/Movies")
    base_dir = movies_dir if os.path.exists(movies_dir) and not os.path.exists(videos_dir) else videos_dir
    OUT = os.path.join(base_dir, "AutoEdit Overlays")

# Colour themes shared by every overlay.
THEMES = {
    "pastel":    {"text": "#ffffff", "accent": "#e58bb8", "pill": "#c86fa0", "shadow": "rgba(90,30,70,.55)"},
    "bold":      {"text": "#ffffff", "accent": "#ffd23f", "pill": "#111111", "shadow": "rgba(0,0,0,.7)"},
    "clean":     {"text": "#ffffff", "accent": "#9ad0ff", "pill": "#00000099", "shadow": "rgba(0,0,0,.6)"},
    "editorial": {"text": "#ffffff", "accent": "#e58bb8", "pill": "#c86fa0", "shadow": "rgba(90,30,70,.55)"},
    "minimal":   {"text": "#ffffff", "accent": "#9ad0ff", "pill": "#00000099", "shadow": "rgba(0,0,0,.6)"},
}
FONT = '"Avenir Next","Helvetica Neue",system-ui,sans-serif'


# ---------------------------------------------------------------- rendering

def page(w, h, dur, css, body, js):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width={w}, height={h}">
<script src="gsap.min.js"></script>
<style>
body{{margin:0;background:transparent}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;font-family:{FONT}}}
{css}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{w}" data-height="{h}" data-duration="{dur:.3f}">
{body}
</div>
<script>
const tl = gsap.timeline({{paused: true}});
{js}
window.__timelines["main"] = tl;
</script></body></html>"""

def render(name, doc, fps):
    """Render a composition to a transparent WebM in AutoEdit Overlays and return its path."""
    hf_bin = _ensure_hyperframes()
    if not os.path.exists(hf_bin) and not shutil.which(hf_bin):
        raise SystemExit("HyperFrames isn't installed. Run the AutoEdit installer again (it sets up motion graphics).")
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.webm")
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)
        shutil.copy(GSAP, td)
        r = subprocess.run([hf_bin, "render", ".", "--format", "webm", "--fps", str(fps), "-o", out, "--quiet"],
                           cwd=td, capture_output=True, text=True, shell=(sys.platform == "win32"))
    if r.returncode or not os.path.exists(out):
        raise SystemExit("HyperFrames render failed: " + (r.stderr or r.stdout).strip()[-600:])
    return out

def seq_format(s):
    st = s["settings"]; fr = st["frame_rate"]
    fps = fr["num"] / fr["den"]
    return st["width"], st["height"], (round(fps) if abs(fps - round(fps)) < 0.01 else f"{fr['num']}/{fr['den']}")

def overlay_track(a, s, name, start, end):
    """A video track named `name` that is free between start and end (ticks); created if needed."""
    for t in s["video"]:
        if t["name"] == name and not any(c["start"] < end and c["end"] > start for c in t["items"]):
            return t["id"]
    before = {t["id"] for t in s["video"]}
    ex(a, "sequence.addTracks", video=1, audio=0)
    new = next(t for t in seq(a)["video"] if t["id"] not in before)
    ex(a, "timeline.setTrack", track=new["id"], name=name)
    return new["id"]

def place(a, path, start_ticks, track_name):
    s = seq(a)
    item = fc(["import", path], a)["items"][0]; STEPS[0] += 1
    dur = ex(a, "file.mediaProperties", items=[item])[0]["duration"]["ticks"]
    track = overlay_track(a, s, track_name, start_ticks, start_ticks + dur)
    ex(a, "timeline.place", item=item, track=track, time=start_ticks, insert=False, audio=False)
    return item


# ---------------------------------------------------------------- title card + outro

def card_doc(w, h, dur, title, sub, theme, position, exit_anim=True):
    t = THEMES.get(theme, THEMES["pastel"])
    k = w / 1080                                  # scale type with the frame width
    top = {"top": "18%", "middle": "42%", "bottom": "64%"}.get(position, "42%")
    css = f"""
.card{{position:absolute;left:0;right:0;top:{top};display:flex;flex-direction:column;align-items:center;gap:{22*k:.0f}px;padding:0 {60*k:.0f}px}}
.title{{font-size:{128*k:.0f}px;font-weight:800;line-height:1.05;text-align:center;color:{t['text']};letter-spacing:-1px;
 -webkit-text-stroke:{2.5*k:.1f}px rgba(40,10,30,.35);paint-order:stroke fill;
 text-shadow:0 {4*k:.0f}px {28*k:.0f}px {t['shadow']},0 {2*k:.0f}px {8*k:.0f}px rgba(0,0,0,.45)}}
.sub{{font-size:{46*k:.0f}px;font-weight:700;color:#fff;background:{t['pill']};padding:{12*k:.0f}px {32*k:.0f}px;border-radius:999px}}
.line{{width:{160*k:.0f}px;height:{8*k:.0f}px;border-radius:9px;background:{t['accent']}}}"""
    body = f"""<section class="clip" data-start="0" data-duration="{dur:.3f}" style="position:absolute;inset:0">
 <div class="card"><div class="title" id="t">{html.escape(title)}</div><div class="line" id="l"></div>""" + \
        (f'<div class="sub" id="s">{html.escape(sub)}</div>' if sub else "") + "</div></section>"
    js = """tl.fromTo("#t",{y:70,opacity:0},{y:0,opacity:1,duration:.7,ease:"power3.out"},.1)
  .fromTo("#l",{scaleX:0},{scaleX:1,duration:.5,ease:"power2.out"},.45)"""
    if sub: js += """\n  .fromTo("#s",{scale:.6,opacity:0},{scale:1,opacity:1,duration:.5,ease:"back.out(2)"},.6)"""
    if exit_anim: js += f"""\n  .to(".card",{{opacity:0,y:-40,duration:.45,ease:"power2.in"}},{dur - .55:.2f})"""
    return page(w, h, dur, css, body, js + ";")

def title_card(a):
    s = seq(a)
    w, h, fps = seq_format(s)
    path = render("title", card_doc(w, h, a.seconds, a.title, a.subtitle, a.theme, a.position), fps)
    place(a, path, 0, "Titles")
    print(f"title: “{a.title}” added at the start ({a.seconds:g}s, {a.theme})")

def outro(a):
    s = seq(a)
    w, h, fps = seq_format(s)
    end = max((c["end"] for t in s["video"] for c in t["items"]), default=s.get("duration", 0))
    start = max(0, end - int(a.seconds * TICKS))
    path = render("outro", card_doc(w, h, a.seconds, a.title, a.subtitle, a.theme, getattr(a, "position", "middle"), exit_anim=False), fps)
    place(a, path, start, "Titles")
    print(f"outro: “{a.title}” added over the last {a.seconds:g}s")


# ---------------------------------------------------------------- animated captions

def phrases(words, max_words=3, max_chars=18, gap=0.45):
    """Group words into short on-screen phrases, breaking at pauses and sentence ends."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or sum(len(x["text"]) + 1 for x in cur) + len(w["text"]) > max_chars
                    or w["start"] - cur[-1]["end"] > gap or re.search(r"[.!?,]$", cur[-1]["text"])):
            out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return out

CAPTION_STYLES = {
    # highlight: how the spoken word is marked; enter: how each phrase appears
    "karaoke": {"theme": "bold",   "highlight": "color", "enter": "pop"},
    "pastel":  {"theme": "pastel", "highlight": "pill",  "enter": "rise"},
    "bounce":  {"theme": "bold",   "highlight": "scale", "enter": "word"},
    "pop":     {"theme": "bold",   "highlight": "color", "enter": "pop"},
    "clean":   {"theme": "clean",  "highlight": "pill",  "enter": "rise"},
}

def captions_doc(w, h, dur, groups, style):
    st = CAPTION_STYLES.get(style, CAPTION_STYLES["karaoke"]); t = THEMES[st["theme"]]
    k = w / 1080
    css = f"""
.cap{{position:absolute;left:{50*k:.0f}px;right:{50*k:.0f}px;bottom:22%;display:flex;flex-wrap:wrap;justify-content:center;gap:0 {16*k:.0f}px}}
.w{{display:inline-block;font-size:{84*k:.0f}px;font-weight:800;color:{t['text']};line-height:1.15;padding:{2*k:.0f}px {10*k:.0f}px;border-radius:{16*k:.0f}px;
 -webkit-text-stroke:{5*k:.1f}px rgba(0,0,0,.85);paint-order:stroke fill;text-shadow:0 {4*k:.0f}px {18*k:.0f}px {t['shadow']}}}"""
    body, js = [], []
    for gi, g in enumerate(groups):
        g0, g1 = g[0]["start"], max(g[-1]["end"], g[0]["start"] + 0.35)
        nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else dur
        g1 = min(max(g1, g[-1]["end"] + 0.25), nxt, dur)          # linger a moment, never overlap the next phrase
        spans = "".join(f'<span class="w" id="w{gi}_{i}">{html.escape(x["text"])}</span>' for i, x in enumerate(g))
        body.append(f'<section class="clip" data-start="{g0:.3f}" data-duration="{g1 - g0:.3f}" style="position:absolute;inset:0">'
                    f'<div class="cap" id="g{gi}">{spans}</div></section>')
        if st["enter"] == "pop":
            js.append(f'tl.fromTo("#g{gi}",{{scale:.7,opacity:0}},{{scale:1,opacity:1,duration:.18,ease:"back.out(3)"}},{g0:.3f});')
        elif st["enter"] == "rise":
            js.append(f'tl.fromTo("#g{gi}",{{y:40,opacity:0}},{{y:0,opacity:1,duration:.25,ease:"power3.out"}},{g0:.3f});')
        for i, x in enumerate(g):
            sel, ws, we = f"#w{gi}_{i}", x["start"], max(x["end"], x["start"] + 0.12)
            if st["enter"] == "word":
                js.append(f'tl.fromTo("{sel}",{{y:30,opacity:0}},{{y:0,opacity:1,duration:.16,ease:"back.out(3)"}},{ws:.3f});')
            if st["highlight"] == "color":
                js.append(f'tl.fromTo("{sel}",{{color:"{t["text"]}"}},{{color:"{t["accent"]}",duration:.06}},{ws:.3f})'
                          f'.to("{sel}",{{color:"{t["text"]}",duration:.06}},{we:.3f});')
            elif st["highlight"] == "pill":
                js.append(f'tl.fromTo("{sel}",{{backgroundColor:"rgba(0,0,0,0)"}},{{backgroundColor:"{t["pill"]}",duration:.08}},{ws:.3f})'
                          f'.to("{sel}",{{backgroundColor:"rgba(0,0,0,0)",duration:.08}},{we:.3f});')
            elif st["highlight"] == "scale":
                js.append(f'tl.fromTo("{sel}",{{scale:1}},{{scale:1.18,color:"{t["accent"]}",duration:.1,ease:"power2.out"}},{ws:.3f})'
                          f'.to("{sel}",{{scale:1,color:"{t["text"]}",duration:.12}},{we:.3f});')
    return page(w, h, dur, css, "\n".join(body), "\n".join(js))

def animated_captions(a):
    F.transcribe(a)
    s = seq(a)
    words = [{"text": x["text"], "start": x["start"] / TICKS, "end": x["end"] / TICKS}
             for x in ex(a, "transcript.inspect").get("words", [])]
    if not words: raise SystemExit("No speech found to caption.")
    w, h, fps = seq_format(s)
    groups = phrases(words)
    # Skip phrases spoken over full-screen cutaways (the "Explainer" track): those carry their own on-screen text
    busy = [(c["start"] / TICKS, c["end"] / TICKS) for t in s["video"] if t["name"] == "Explainer" for c in t["items"]]
    if busy:
        kept = [g for g in groups if not any(a0 <= (g[0]["start"] + g[-1]["end"]) / 2 < a1 for a0, a1 in busy)]
        print(f"Skipping {len(groups) - len(kept)} phrases that play over explainer animations")
        groups = kept
        if not groups: raise SystemExit("Every phrase is covered by explainer animations; nothing to caption.")
    first, last = groups[0][0]["start"], groups[-1][-1]["end"] + 0.6
    for g in groups:                                   # render only the span with speech
        for x in g: x["start"] -= first; x["end"] -= first
    dur = last - first
    print(f"Rendering {len(groups)} caption phrases ({dur:.0f}s of video)…")
    path = render("captions", captions_doc(w, h, dur, groups, a.style), fps)
    place(a, path, int(round(first * TICKS)), "Animated captions")
    print(f"animated captions: {sum(len(g) for g in groups)} words in {len(groups)} phrases, '{a.style}' style")
