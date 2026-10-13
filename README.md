# AutoEdit for FilmCraft

One-click edits for FilmCraft: smooth transitions + music, beat sync, slow zooms, captions,
removing pauses / "um"s / bad takes, AutoReel, and animated titles, captions and outros (HyperFrames).
A floating panel appears next to FilmCraft whenever it's open.

Built on [FilmCraft](https://github.com/storytold/filmcraft)'s control API, with speech-to-text by
[whisper.cpp](https://github.com/ggml-org/whisper.cpp) and motion graphics by [HyperFrames](https://github.com/heygen-com/hyperframes).
Everything runs on your Mac. macOS only.

| Panel section | What it does |
|---|---|
| 🎵 Smooth transitions + music | Dissolve on every cut, background song at a set level |
| 🥁 Beat sync | Move cuts onto the music's beat, beat zoom punches, beat markers |
| 🔍 Slow zoom | Gentle push-in / pull-out per clip |
| 💬 AutoCaptions | Speech → caption track (English, Hindi, Punjabi, other) |
| ✂️ Clean up speech | Remove long pauses, "um"/"uh", restarted sentences |
| ✨ Motion graphics | Animated word-by-word captions, title cards, outros (transparent overlays) |
| ⚡ AutoReel | New beat-cut vertical reel from your clips and a song |
| 🕘 History | Every effect is snapshotted first: revert any step |

## Install (about 10 minutes the first time)

**Download `AutoEdit-for-FilmCraft.zip` from the [latest release](../../releases/latest)** (it includes FilmCraft's
command-line tool), unzip it, then:

1. **Install FilmCraft** and open it once.
2. **Install Homebrew** if you don't have it: go to https://brew.sh, copy the one command into Terminal, press Enter.
3. **Double-click `Install AutoEdit.command`** in this folder.
   - macOS may say it "can't be opened". Then **right-click it → Open → Open**. (Only needed once.)
   - If a window asks to install Apple's *command line developer tools*, click **Install**, wait, then double-click the installer again.
   - The first run downloads ffmpeg, whisper.cpp and Node through Homebrew; that's the slow part.
4. **Quit FilmCraft and open it again.** The AutoEdit panel appears next to it (scissors ✂ icon in the menu bar).

Put songs you're allowed to use in **~/Music/AutoEdit** (or use *Add song…* in the panel).

## Good to know

- Every effect can be undone from the panel's **History** (or **↶ Undo last effect**).
- Captions and speech clean-up run on your Mac; the speech model (~150 MB, ~470 MB for Hindi/Punjabi) downloads the first time you use them.
- Motion graphics render with HyperFrames and need an internet connection while rendering.
- You can move or delete this folder after installing; AutoEdit keeps its own copy.
- Something stopped working (e.g. after updating FilmCraft)? Just run the installer again.

## From source

`git clone` this repo, put an unzipped `filmcraft-cli-*-macos-*` folder in `~/Downloads` (from FilmCraft's
releases), then run `./install.sh`. `./make-package.sh` builds the release zip.

The engine also works from the command line: `python3 autoedit.py --help`.

## Uninstall

Double-click **`Uninstall AutoEdit.command`**. Your projects, videos and songs are kept.

## License

MIT. FilmCraft's command-line tool (bundled in release zips) is MIT/Apache-2.0; HyperFrames is Apache-2.0;
whisper.cpp is MIT. No music is included: only use songs you have the rights to.
