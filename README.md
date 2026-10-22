# AutoEdit for FilmCraft

[![CI](https://github.com/justdxvid/autoedit/actions/workflows/ci.yml/badge.svg)](https://github.com/justdxvid/autoedit/actions/workflows/ci.yml)

One-click edits for FilmCraft: smooth transitions + music, beat sync, slow zooms, captions,
removing pauses / "um"s / bad takes, AutoReel, and animated titles, captions and outros (HyperFrames).
A floating panel appears next to FilmCraft whenever it's open, or in your browser on Linux.

Built on [FilmCraft](https://github.com/storytold/filmcraft)'s control API, with speech-to-text by
[whisper.cpp](https://github.com/ggml-org/whisper.cpp) and motion graphics by [HyperFrames](https://github.com/heygen-com/hyperframes).
Runs entirely on your local machine (Windows, macOS & Linux).

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

## Install

### Windows
1. **Install dependencies**:
   - Python 3 (from [python.org](https://python.org) or `winget install Python.Python.3.12`)
   - `ffmpeg` (e.g. `winget install Gyan.FFmpeg` or `choco install ffmpeg` / `scoop install ffmpeg`)
   - `node` & `npm` (e.g. `winget install OpenJS.NodeJS`)
   - `whisper.cpp` (`whisper-cli.exe` or `whisper.exe`, from [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases))
2. Ensure `filmcraft-cli.exe` or `filmcraft.exe` is in your `PATH` or in `%LOCALAPPDATA%\FilmCraft`.
3. Double-click **`Install AutoEdit.bat`** (or run `powershell -ExecutionPolicy Bypass -File install.ps1`).
4. Double-click **`Start AutoEdit.bat`** (or run `autoedit` in Terminal / PowerShell) to open the web panel at `http://127.0.0.1:8765`.

### macOS
1. **Install FilmCraft** and open it once.
2. **Install Homebrew** if you don't have it: https://brew.sh
3. Run `./install.sh` or double-click **`Install AutoEdit.command`**.
4. **Quit FilmCraft and open it again.** The AutoEdit panel appears next to it (scissors ✂ icon in the menu bar).

### Linux
1. **Install dependencies**:
   - Python 3
   - `ffmpeg` (e.g. `sudo apt install ffmpeg` / `sudo pacman -S ffmpeg` / `sudo dnf install ffmpeg`)
   - `node` & `npm` (Node 18+, Node 22 recommended for HyperFrames)
   - `whisper.cpp` (`whisper-cli`, e.g. `sudo pacman -S whisper-cpp` or build from [whisper.cpp](https://github.com/ggml-org/whisper.cpp))
2. Ensure `filmcraft-cli` is in your `PATH` or `~/.local/bin/filmcraft-cli`.
3. **Run `./install.sh`**:
   - Sets up the HyperFrames renderer and dependencies.
   - Installs the `autoedit` command in `~/.local/bin/autoedit`.
   - Creates a desktop application launcher in `~/.local/share/applications/autoedit.desktop`.
   - Creates an optional systemd user service in `~/.config/systemd/user/autoedit.service`.
4. Launch AutoEdit by running `autoedit` or selecting **AutoEdit** from your application launcher. It opens the web panel at `http://127.0.0.1:8765`.

Put songs you're allowed to use in **~/Music/AutoEdit** (or click *Add song…* in the panel).

## Good to know

- Every effect can be undone from the panel's **History** (or **↶ Undo last effect**).
- Captions and speech clean-up run locally on your machine; speech models (~150 MB, ~470 MB for Hindi/Punjabi) download the first time you use them into standard app data paths (`%LOCALAPPDATA%\AutoEdit\models` on Windows, `~/.local/share/autoedit/models` on Linux, `~/Library/Application Support/AutoEdit/models` on macOS).
- Motion graphics render with HyperFrames and transparent WebM (VP9 alpha).
- Something stopped working (e.g. after updating FilmCraft)? Just run the installer again.

## Command-Line Usage

The engine also works directly from the command line:

```bash
autoedit --help
autoedit --project myproject.fcproj zoom --amount 8
autoedit --project myproject.fcproj smooth --frames 15
```

## Running Tests

Run the test suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Uninstall

- **Windows**: Double-click **`Uninstall AutoEdit.bat`** (or run `powershell -ExecutionPolicy Bypass -File uninstall.ps1`).
- **macOS**: Double-click **`Uninstall AutoEdit.command`** or run `./uninstall.sh`.
- **Linux**: Run `./uninstall.sh`.
Your projects, videos and songs are kept.

## License

MIT. FilmCraft's command-line tool is MIT/Apache-2.0; HyperFrames is Apache-2.0;
whisper.cpp is MIT. No music is included: only use songs you have the rights to.
