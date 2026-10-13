---
name: autoedit
description: One-click FilmCraft edits with the user's AutoEdit tool - dissolves + music, beat-synced cuts and zooms, slow zooms, AutoCaptions, removing pauses/um/bad takes, AutoReel beat-cut reels. Use when the user asks to edit, smooth, add music to, zoom, or clean up a FilmCraft project/video, or mentions AutoEdit.
---

# AutoEdit (FilmCraft companion)

The user's own AutoCut-style tool for FilmCraft. Source: `{{AUTOEDIT_DIR}}/`.

## Pieces
- `autoedit.py`: engine. It drives FilmCraft through `filmcraft-cli`, which `install.sh` links at `~/.local/bin/filmcraft-cli`.
- `~/Applications/AutoEdit.app`: a floating panel with a scissors icon in the menu bar. It auto-shows when FilmCraft opens.
- `~/Music/AutoEdit/`: shared music library for every project.
- `install.sh`: re-run it after reinstalling FilmCraft or filmcraft-cli, or if anything stops connecting.
- FilmCraft listens on 127.0.0.1:9876. A login agent sets `FILMCRAFT_CONTROL_PORT`, so a normal Dock launch works.

## Running edits for the user
Prefer the `filmcraft-live` MCP tools for inspecting state. For the packaged edits, run the engine against the open project:

```
cd {{AUTOEDIT_DIR}}
python3 autoedit.py smooth --music ~/Music/AutoEdit/<song> --frames 15 --music-db -14 --mute-original
python3 autoedit.py zoom --amount 8
python3 autoedit.py beatcuts                 # move cuts onto the music's beat (needs music on timeline)
python3 autoedit.py beatzoom --every 4 --amount 7
python3 autoedit.py beatmarkers --every 4
python3 autoedit.py captions --style pop     # pop | pastel | clean; --language auto for non-English
python3 autoedit.py pauses --min 0.6 | fillers | badtakes
python3 autoedit.py reel --music <song> --length 30 --beats-per-shot 2   # new sequence "AutoReel"
python3 autoedit.py animcaptions --style karaoke|pastel|bounce   # HyperFrames word-by-word captions overlay
python3 autoedit.py title --title "Summer Edit" --subtitle "new collection" --theme pastel --position top
python3 autoedit.py outro --title "Follow for more" --subtitle "@handle"
python3 autoedit.py --project <file.fcproj> <cmd>   # headless on a file (saves back to it)
```

Speech features transcribe with whisper.cpp (`whisper-cli`, from Homebrew). Models live in
`~/Library/Application Support/AutoEdit/models` and download on first use. FilmCraft's own
transcription is disabled in this build, so transcripts go in with `transcript.set`.

Motion graphics (`hf.py`) are written as HyperFrames HTML and rendered with the local CLI in
`{{AUTOEDIT_DIR}}/hyperframes/` to transparent WebM (VP9 alpha; FilmCraft reads it, ~80x smaller
than ProRes 4444). Renders are saved in `~/Movies/AutoEdit Overlays/` and placed on named tracks
("Titles", "Animated captions"). The HyperFrames Claude Code plugin is also installed, for custom one-off animations.

## Rules
- Panel effects are snapshotted to `~/Library/Application Support/AutoEdit/history/<project>/` before running. To undo one for the user, restore its snapshot: `file.open` the snapshot, then `file.saveAs` the original path. The panel's History does the same thing.
- Work on the project open in FilmCraft. Never test on the user's live project; test on a copy with `--project`.
- `smooth` skips cuts that already have a transition. Adding music twice stacks two music clips, so check Audio tracks first.
- Mute the original audio rather than deleting it, unless the user asks for deletion.
- If live tools say "connection refused", FilmCraft was opened without the port. Ask the user to quit and reopen it, or run `install.sh`.
- No licensed music is bundled. Use songs the user drops into `~/Music/AutoEdit`, or synthesize one with ffmpeg.
