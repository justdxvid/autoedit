"""AutoEdit features beyond the basics: transcription, captions, speech clean-up, beat sync, AutoReel.

Everything drives FilmCraft through autoedit.fc / autoedit.ex, so it works on the live app or on a
project file (--project). Speech-to-text runs locally with whisper.cpp (FilmCraft's own build has
transcription switched off), and the result is imported with transcript.set so FilmCraft's caption
and text-based-editing commands can use it.
"""
import array, json, math, os, re, shutil, subprocess, sys, tempfile
from autoedit import ex, fc, seq, TICKS, STEPS

def autoedit_steps(n): STEPS[0] += n

os.environ["PATH"] = os.path.expanduser("~/.local/bin:") + "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")
if sys.platform == "darwin":
    MODELS = os.path.expanduser("~/Library/Application Support/AutoEdit/models")
else:
    xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    MODELS = os.path.join(xdg_data, "autoedit", "models")
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin"


# ---------------------------------------------------------------- helpers

def find_whisper():
    if os.environ.get("WHISPER_CLI"): return os.environ["WHISPER_CLI"]
    for name in ["whisper-cli", "whisper-cpp", "whisper", "main"]:
        p = shutil.which(name)
        if p: return p
    for p in [os.path.expanduser("~/.local/bin/whisper-cli"), os.path.expanduser("~/.local/bin/main"),
              os.path.expanduser("~/Library/Application Support/AutoEdit/whisper-cli"),
              os.path.expanduser("~/.local/share/autoedit/whisper-cli")]:
        if os.path.exists(p): return p
    return "whisper-cli"

def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def media_path(a, item):
    return ex(a, "file.mediaProperties", items=[item])[0]["path"]

def frame_ticks(s):
    fr = s["settings"]["frame_rate"]
    return TICKS * fr["den"] // fr["num"]

def all_clips(s, kind):
    return [c for t in s[kind] for c in t["items"]]

def say(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- speech to text

def model_file(lang):
    name = "base.en" if lang == "en" else "small"   # base is too weak for Hindi/Punjabi (wrong script)
    path = os.path.join(MODELS, f"ggml-{name}.bin")
    if not os.path.exists(path):
        os.makedirs(MODELS, exist_ok=True)
        say(f"Downloading speech model {name} (one time, {'~150' if name == 'base.en' else '~470'} MB)…")
        r = sh(["curl", "-sfL", "-o", path + ".part", MODEL_URL.format(name)])
        if r.returncode: raise SystemExit(f"model download failed: {r.stderr}")
        os.rename(path + ".part", path)
    return path

def speech_regions(wav, total):
    """Spans of non-silence, so each one can be transcribed with accurate timing."""
    r = sh(["ffmpeg", "-hide_banner", "-i", wav, "-af", "silencedetect=n=-38dB:d=0.35", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    regions, cur = [], 0.0
    for s0, e0 in zip(starts, ends + [total] * (len(starts) - len(ends))):
        if s0 - cur > 0.2: regions.append((max(0, cur - 0.15), min(total, s0 + 0.15)))
        cur = e0
    if total - cur > 0.2: regions.append((max(0, cur - 0.15), total))
    return regions

def whisper_words(wav, offset, model, lang):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "w")
        sh([find_whisper(), "-m", model, "-f", wav, "-l", lang, "-ojf", "-of", out, "-np"])
        if not os.path.exists(out + ".json"): return []
        d = json.load(open(out + ".json"))
    words = []
    for seg in d.get("transcription", []):
        for t in seg["tokens"]:
            tx = t["text"]
            if tx.startswith("[_") or not tx.strip(): continue
            a, b = offset + t["offsets"]["from"] / 1000, offset + t["offsets"]["to"] / 1000
            if tx.startswith(" ") or not words: words.append({"text": tx.strip(), "start": a, "end": b})
            else: words[-1]["text"] += tx; words[-1]["end"] = b
    return words

def transcribe_file(path, lang="en"):
    """Word list [{text,start,end}] in seconds of the media file."""
    model = model_file(lang)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        r = sh(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav])
        if r.returncode or not os.path.exists(wav): return []
        total = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]).stdout or 0)
        words = []
        for i, (s0, e0) in enumerate(speech_regions(wav, total)):
            part = os.path.join(td, f"r{i}.wav")
            sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{s0}", "-to", f"{e0}", "-i", wav, part])
            for w in whisper_words(part, s0, model, lang):
                w["start"], w["end"] = max(s0, min(w["start"], e0)), max(s0, min(w["end"], e0))
                words.append(w)
    return words

def transcribe(a):
    """Transcribe every clip with sound in the active sequence and import the transcripts."""
    s = seq(a)
    have = {i["item"] for i in ex(a, "transcript.inspect").get("items", [])} if not a.force else set()
    mc = music_clip(a, s)
    music_item = mc[0]["item"] if mc and mc[0]["duration"] > 0.6 * s["duration"] else None
    # muted tracks still hold speech (e.g. the voice muted under music), so only the music bed is skipped
    items = sorted({c["item"] for t in s["audio"] for c in t["items"]} - {music_item})
    done = 0
    for item in items:
        if item in have: continue
        props = ex(a, "file.mediaProperties", items=[item])[0]
        if props.get("type") not in ("Movie", "Audio", "AudioOnly") or not props.get("audio"): continue
        say(f"Transcribing {props['name']}…")
        words = transcribe_file(props["path"], a.language)
        if not words: say(f"  no speech found in {props['name']}"); continue
        tw = [{"text": w["text"], "start": int(w["start"] * TICKS), "end": int(w["end"] * TICKS)} for w in words]
        lang = a.language if a.language != "auto" else "en"
        ex(a, "transcript.set", item=item, transcript={"language": lang, "speakers": [{"name": "Speaker 1"}], "words": tw})
        say(f"  {len(words)} words"); done += 1
    say(f"transcribe: {done} clip(s) transcribed, {len(have & set(items))} already had a transcript")


# ---------------------------------------------------------------- captions

CAPTION_STYLES = {
    # name: (createCaptions params, setStyle params)
    "pop":      ({"maxChars": 12, "lines": 1, "minSeconds": 0.4, "maxSeconds": 1.6},
                 {"size": 72, "color": "#ffffff", "background": False, "outline": 6, "outlineColor": "#000000", "align": "center", "anchor": "bottom", "margin": 0.22}),
    "clean":    ({"maxChars": 28, "lines": 2, "minSeconds": 1.0, "maxSeconds": 3.5},
                 {"size": 52, "color": "#ffffff", "background": True, "backgroundColor": "#000000a0", "align": "center", "anchor": "bottom", "margin": 0.12}),
    "pastel":   ({"maxChars": 18, "lines": 1, "minSeconds": 0.5, "maxSeconds": 2.0},
                 {"size": 66, "color": "#fff4fa", "background": True, "backgroundColor": "#c86fa0c8", "align": "center", "anchor": "bottom", "margin": 0.2}),
}

SCRIPT_FONTS = [((0x0900, 0x097F), "Kohinoor Devanagari"),   # Hindi, Marathi
                ((0x0A00, 0x0A7F), "Mukta Mahee"),           # Punjabi (Gurmukhi)
                ((0x0600, 0x06FF), "Noto Nastaliq Urdu")]    # Urdu / Shahmukhi

def script_font(text):
    """A system font that has the letters of the transcript's script (FilmCraft's default is Latin-only)."""
    counts = {font: sum(lo <= ord(ch) <= hi for ch in text) for (lo, hi), font in SCRIPT_FONTS}
    font, n = max(counts.items(), key=lambda kv: kv[1])
    return font if n > len(text) * 0.2 else None

def captions(a):
    transcribe(a)
    make, style = CAPTION_STYLES[a.style]
    r = ex(a, "transcript.createCaptions", name=f"AutoCaptions ({a.style})", **make)
    track = r.get("track") if isinstance(r, dict) else None
    if track is None:
        tracks = seq(a).get("captions") or []
        track = tracks[-1]["id"] if tracks else "C1"
    font = script_font(" ".join(w["text"] for w in ex(a, "transcript.inspect").get("words", [])[:200]))
    ex(a, "captions.setStyle", track=track, **style, **({"font": font} if font else {}))
    n = sum(len(t["captions"]) for t in ex(a, "captions.list", track=track).get("tracks", []))
    say(f"captions: {n} captions on a new '{a.style}' caption track")


# ---------------------------------------------------------------- speech clean-up


import contextlib

@contextlib.contextmanager
def music_protected(a):
    """Lock audio-only (music) tracks while speech is cut, then trim the song to the new video end.
    Without this, ripple cuts chop the music into pieces that jump around the song."""
    s = seq(a)
    tracks = [t["id"] for t in s["audio"] if not t["locked"] and t["items"] and
              all(ex(a, "file.mediaProperties", items=[c["item"]])[0].get("type") in ("Audio", "AudioOnly") for c in t["items"])]
    for t in tracks: ex(a, "timeline.setTrack", track=t, locked=True)
    try:
        yield
    finally:
        for t in tracks: ex(a, "timeline.setTrack", track=t, locked=False)
        s2 = seq(a)
        vend = max((c["end"] for t in s2["video"] for c in t["items"]), default=0)
        for t in s2["audio"]:
            if t["id"] in tracks:
                for c in t["items"]:
                    if c["end"] > vend > c["start"]:
                        ex(a, "timeline.trim", clip=c["clip"], edge="out", mode="regular", delta=vend - c["end"])

def remove_pauses(a):
    transcribe(a)
    with music_protected(a):
        r = ex(a, "transcript.removePauses", minSeconds=a.min, keepSeconds=a.keep)
    say(f"pauses: removed pauses longer than {a.min}s (kept {a.keep}s of breathing room) {short(r)}")

def remove_fillers(a):
    transcribe(a)
    with music_protected(a):
        r = ex(a, "transcript.removeFillers")
    say(f"fillers: removed um/uh-type filler words {short(r)}")

def norm(w):
    return re.sub(r"[^\w']", "", w.lower())

def find_retake(words):
    """First restart: words i.. are repeated (>=3 words) starting at j within the next 15 words."""
    t = [norm(w["text"]) for w in words]
    for i in range(len(t) - 3):
        for j in range(i + 2, min(i + 16, len(t) - 2)):
            n = 0
            while j + n < len(t) and i + n < j and t[i + n] == t[j + n] and t[i + n]: n += 1
            if n >= 3: return i, j
    return None

def remove_bad_takes(a):
    transcribe(a)
    removed = []
    for _ in range(100):
        words = ex(a, "transcript.inspect").get("words", [])
        hit = find_retake(words)
        if not hit: break
        i, j = hit
        removed.append(" ".join(w["text"] for w in words[i:j]))
        with music_protected(a):
            ex(a, "transcript.extract", **{"from": words[i]["i"], "to": words[j - 1]["i"]})
    for r in removed: say(f"  cut bad take: “{r}”")
    say(f"bad takes: {len(removed)} restarted sentence(s) removed")

def short(r):
    return "" if r in (None, "", {}) else "(" + json.dumps(r)[:160] + ")"


# ---------------------------------------------------------------- beat detection

def detect_beats(path, start=0.0, dur=None):
    """Return (bpm, [beat times in seconds]) for an audio file, using only ffmpeg + stdlib."""
    sr, hop = 11025, 256
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start)] + (["-t", str(dur)] if dur else []) + \
          ["-i", path, "-ac", "1", "-ar", str(sr), "-af", "highpass=f=40,lowpass=f=3000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    x = array.array("h"); x.frombytes(raw[: len(raw) // 2 * 2])
    fps = sr / hop
    env = [math.log1p(sum(v * v for v in x[i:i + hop]) / hop) for i in range(0, len(x) - hop, hop)]
    on = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    if len(on) < fps * 4: return 0, []
    m = sum(on) / len(on); on = [v - m for v in on]
    best, lag = -1e18, 0
    for L in range(int(fps * 60 / 180), int(fps * 60 / 60) + 1):      # 60-180 bpm
        bpm = 60 * fps / L
        prior = math.exp(-0.5 * (math.log2(bpm / 115)) ** 2 / 0.5 ** 2)
        sc = sum(on[i] * on[i + L] for i in range(len(on) - L)) / (len(on) - L) * prior
        if sc > best: best, lag = sc, L
    period = lag
    # refine the period with the best grid score near it, then the phase
    def grid(p, off):
        k, t, s = 0, off, 0.0
        while t < len(on): s += on[int(t)]; t += p; k += 1
        return s / max(k, 1)
    cands = [lag + d / 10 for d in range(-10, 11)]
    period, phase = max(((p, o) for p in cands for o in range(int(p))), key=lambda po: grid(*po))
    beats, t = [], float(phase)
    while t < len(on): beats.append(start + (t + 1) / fps); t += period
    return round(60 * fps / period, 1), beats

def music_clip(a, s):
    """The sequence's music: the longest clip on any audio track whose item is audio-only."""
    best = None
    for c in all_clips(s, "audio"):
        p = ex(a, "file.mediaProperties", items=[c["item"]])[0]
        if p.get("type") in ("Audio", "AudioOnly") and (best is None or c["duration"] > best[0]["duration"]):
            best = (c, p["path"])
    return best

def sequence_beats(a, s):
    mc = music_clip(a, s)
    if not mc: raise SystemExit("No music clip found on the timeline. Add music first (Smooth + music).")
    c, path = mc
    bpm, beats = detect_beats(path, c["sourceIn"] / TICKS, c["duration"] / TICKS)
    seqbeats = [c["start"] / TICKS + (b - c["sourceIn"] / TICKS) for b in beats]
    return bpm, [b for b in seqbeats if 0 <= b <= s["duration"] / TICKS]

def beat_markers(a):
    s = seq(a)
    bpm, beats = sequence_beats(a, s)
    for k, b in enumerate(beats):
        if k % a.every == 0:
            ex(a, "markers.add", target="program", time=int(b * TICKS), name=f"Beat {k // a.every + 1}", color="Rose" if k % (a.every * 4) == 0 else "Mango")
    say(f"beats: {bpm} BPM, {len(beats[::a.every])} markers added")

def beat_cuts(a):
    """Move each cut on the main video track to the nearest beat (ripple trims; dissolves are rebuilt)."""
    s = seq(a)
    bpm, beats = sequence_beats(a, s)
    vt = next(t for t in s["video"] if t["items"])
    trans = [(tr["to"], tr["effect"], round(tr["duration"] / frame_ticks(s))) for tr in vt["transitions"] if tr["from"]]
    if vt["transitions"]: ex(a, "sequence.removeTransition", transitions=[tr["id"] for tr in vt["transitions"]])
    # Lock tracks holding audio-only clips (the music) so ripple trims don't drag the song along.
    music_tracks = [t["id"] for t in s["audio"] if not t["locked"] and t["items"] and
                    all(ex(a, "file.mediaProperties", items=[c["item"]])[0].get("type") in ("Audio", "AudioOnly") for c in t["items"])]
    for t in music_tracks: ex(a, "timeline.setTrack", track=t, locked=True)
    ft = frame_ticks(s); moved = 0
    try:
        moved = _snap_cuts(a, vt, beats, ft)
    finally:
        for t in music_tracks: ex(a, "timeline.setTrack", track=t, locked=False)
        s2 = seq(a)
        vend = max(c["end"] for t in s2["video"] for c in t["items"])
        for t in s2["audio"]:
            if t["id"] in music_tracks:
                for c in t["items"]:
                    if c["end"] > vend > c["start"]:
                        ex(a, "timeline.trim", clip=c["clip"], edge="out", mode="regular", delta=vend - c["end"])
        for to, eff, frames in trans:
            ex(a, "sequence.applyVideoTransition", clip=to, effect=eff, frames=frames, edge="in")
    say(f"beat cuts: {bpm} BPM, {moved} cut(s) moved onto the beat" + (f", {len(trans)} transition(s) re-applied" if trans else ""))

def _snap_cuts(a, vt, beats, ft):
    moved = 0
    for idx in range(len(vt["items"]) - 1):
        clips = next(t for t in seq(a)["video"] if t["id"] == vt["id"])["items"]
        c = clips[idx]
        media = ex(a, "file.mediaProperties", items=[c["item"]])[0]["duration"]["ticks"]
        handle = media - c["sourceOut"]
        best = None
        for b in beats:
            bt = int(round(b * TICKS / ft)) * ft
            delta = bt - c["end"]
            if bt - c["start"] < TICKS // 2 or delta > handle: continue
            if best is None or abs(delta) < abs(best): best = delta
        if best:
            ex(a, "timeline.trim", clip=c["clip"], edge="out", mode="ripple", delta=best); moved += 1
    return moved

def beat_zoom(a):
    """Quick zoom punch on every Nth beat: jump in on the beat, ease back out over a few frames."""
    s = seq(a)
    bpm, beats = sequence_beats(a, s)
    ft = frame_ticks(s); n = 0
    clips = next(t for t in s["video"] if t["items"])["items"]
    for b in beats[:: a.every]:
        t = int(round(b * TICKS / ft)) * ft
        c = next((c for c in clips if c["start"] + ft <= t < c["end"] - 8 * ft), None)
        if not c: continue
        base = float(next(e for e in c["effects"] if e["effect"] == "motion")["params"]["scale"]["value"][6:-1])
        for tt, v in ((t - ft, base), (t, base * (1 + a.amount / 100)), (t + 8 * ft, base)):
            ex(a, "effects.setParam", clip=c["clip"], effect="motion", param="scale", value=v, time=tt, keyframe=True)
        n += 1
    say(f"beat zoom: {n} punch-ins at {bpm} BPM (every {a.every} beats)")


# ---------------------------------------------------------------- AutoReel

def reel(a):
    """Build a new beat-cut vertical reel from the clips on the current timeline plus a song."""
    s = seq(a)
    src = next(t for t in s["video"] if t["items"])["items"]
    music = a.music
    if not music:
        mc = music_clip(a, s)
        if not mc: raise SystemExit("Pick a song for the reel.")
        music = mc[1]
    bpm, beats = detect_beats(music, 0, a.length + 5)
    if len(beats) < 4: raise SystemExit("Could not find a beat in that song.")
    st = s["settings"]; fr = st["frame_rate"]
    r = ex(a, "file.newSequence", name=a.name, width=st["width"], height=st["height"], fps=fr["num"] / fr["den"], sampleRate=48000, video=2, audio=2)
    newseq = seq(a)
    ft = frame_ticks(newseq)
    v1 = newseq["video"][0]["id"]
    slot = a.beats_per_shot
    first = beats[0]                                            # the reel starts on the first beat
    cuts = [int(round((b - first) * TICKS / ft)) * ft for b in beats[::slot] if b - first <= a.length]
    cursor = {c["clip"]: c["sourceIn"] + min(TICKS, (c["sourceOut"] - c["sourceIn"]) // 10) for c in src}  # skip the shaky start
    shots = 0
    for k in range(len(cuts) - 1):
        c = src[k % len(src)]
        dur = cuts[k + 1] - cuts[k]
        si = cursor[c["clip"]]
        if si + dur > c["sourceOut"]: si = c["sourceIn"]        # wrap around inside the clip
        if si + dur > c["sourceOut"]: dur = c["sourceOut"] - si  # clip shorter than the slot
        ex(a, "timeline.place", item=c["item"], track=v1, time=cuts[k], insert=False, sourceIn=si, duration=dur, audio=False)
        cursor[c["clip"]] = si + dur + 2 * TICKS              # next time, use a later moment of this clip
        shots += 1
    end = cuts[-1]
    imp = fc(["import", music], a); autoedit_steps(1)
    item = imp["items"][0]
    placed = ex(a, "timeline.place", item=item, audioTrack=newseq["audio"][0]["id"], time=0, insert=False, video=False,
                sourceIn=int(first * TICKS), duration=end)
    ex(a, "clip.audioGain", clips=placed["clips"], mode="set", db=-6)
    say(f"reel: new sequence '{a.name}', {shots} shots cut on the beat ({bpm} BPM, {slot} beats per shot), {end / TICKS:.1f}s long")
