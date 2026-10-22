#!/bin/bash
# Install (or repair) AutoEdit so it behaves like a FilmCraft plugin.
# Safe to run again any time, e.g. after reinstalling FilmCraft or filmcraft-cli.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
PORT=9876
OS="$(uname -s)"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
stop() { printf '\n  \033[31m✗ %s\033[0m\n\n' "$1"; exit 1; }

echo
echo "AutoEdit installer ($OS)"
echo

if [ "$OS" = "Darwin" ]; then
  SUPPORT="$HOME/Library/Application Support/AutoEdit"
  APP="$HOME/Applications/AutoEdit.app"
  AGENT="$HOME/Library/LaunchAgents/local.autoedit.companion.plist"
elif [ "$OS" = "Linux" ]; then
  SUPPORT="${XDG_DATA_HOME:-$HOME/.local/share}/autoedit"
  BIN_DIR="$HOME/.local/bin"
  DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
else
  stop "Unsupported operating system: $OS"
fi

# 0. Where AutoEdit lives. A downloaded copy is moved into Application Support, so the download can be deleted.
#    A development folder marked with .keep-in-place is used where it is.
if [ -f "$SRC/.keep-in-place" ]; then
  HERE="$SRC"
else
  HERE="$SUPPORT/app"
  if [ "$SRC" != "$HERE" ]; then
    mkdir -p "$HERE"
    rsync -a --delete --exclude hyperframes/node_modules --exclude __pycache__ "$SRC/" "$HERE/"
  fi
fi
ok "AutoEdit files: $HERE"

# 1. Platform-specific system build tools & package manager
if [ "$OS" = "Darwin" ]; then
  xcode-select -p >/dev/null 2>&1 || { xcode-select --install 2>/dev/null || true
    stop "Apple's command-line tools are needed. A window to install them just opened; finish it, then run this installer again."; }
  command -v swiftc >/dev/null || stop "Swift compiler not found even though the command-line tools are installed. Run: xcode-select --install"
  ok "Apple command-line tools"
  BREW=$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1 || true)
  [ -n "$BREW" ] || stop "Homebrew is needed. Install it from https://brew.sh (one command), then run this installer again."
  eval "$("$BREW" shellenv)"
  ok "Homebrew"

  # Media tools via Homebrew
  for pkg in ffmpeg whisper-cpp node; do
    if "$BREW" list --formula "$pkg" >/dev/null 2>&1; then ok "$pkg"
    else echo "  … installing $pkg (one time, can take a few minutes)"; "$BREW" install "$pkg" >/dev/null && ok "$pkg installed"; fi
  done
elif [ "$OS" = "Linux" ]; then
  command -v python3 >/dev/null || stop "Python 3 is required. Please install python3 via your package manager."
  ok "Python 3 ($(python3 --version 2>&1 | head -1))"

  # Check ffmpeg
  if command -v ffmpeg >/dev/null; then
    ok "ffmpeg"
  else
    warn "ffmpeg not found. Install it with your package manager (e.g. sudo apt install ffmpeg, sudo pacman -S ffmpeg, or sudo dnf install ffmpeg)"
  fi

  # Check node
  if command -v node >/dev/null; then
    ok "node ($(node --version 2>/dev/null))"
  else
    warn "Node.js not found. Motion graphics need Node 22+. Install via your package manager or nvm/mise."
  fi

  # Check whisper.cpp
  if command -v whisper-cli >/dev/null || command -v whisper-cpp >/dev/null || command -v whisper >/dev/null; then
    ok "whisper.cpp"
  else
    warn "whisper-cli not found. Speech transcription needs whisper.cpp (e.g. sudo pacman -S whisper-cpp, or build from https://github.com/ggml-org/whisper.cpp)"
  fi
fi

NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
[ "$NODE_MAJOR" -ge 18 ] || warn "Node $NODE_MAJOR found; motion graphics recommend Node 22+ (or 18+)"

# 2. FilmCraft and its command-line tool
if [ "$OS" = "Darwin" ]; then
  if [ -d /Applications/FilmCraft.app ] || [ -d "$HOME/Applications/FilmCraft.app" ]; then ok "FilmCraft app"
  else warn "FilmCraft.app not found in Applications. Install FilmCraft, then run this installer again."; fi
elif [ "$OS" = "Linux" ]; then
  if command -v filmcraft >/dev/null || [ -f "$HOME/.local/bin/filmcraft" ] || [ -f "/usr/bin/filmcraft" ]; then
    ok "FilmCraft app"
  else
    warn "FilmCraft binary not found in PATH or ~/.local/bin. Make sure FilmCraft is installed."
  fi
fi

CLI=$(ls -d "$SRC"/filmcraft-cli-*/filmcraft-cli "$HOME"/tools/filmcraft-cli-*/filmcraft-cli "$HOME"/Downloads/filmcraft-cli-*/filmcraft-cli \
        "$HOME"/Applications/filmcraft-cli-*/filmcraft-cli "$SUPPORT"/filmcraft-cli-*/filmcraft-cli \
        "$HOME"/Projects/filmcraft/target/release/filmcraft-cli \
        "$HOME"/.local/bin/filmcraft-cli /usr/local/bin/filmcraft-cli /usr/bin/filmcraft-cli 2>/dev/null | sort -V | tail -1 || true)
if [ -n "$CLI" ]; then
  case "$CLI" in "$SUPPORT"/*|/usr/*|"$HOME/.local/bin"/*) ;; *)
    mkdir -p "$SUPPORT"
    rm -rf "$SUPPORT/$(basename "$(dirname "$CLI")")"
    cp -R "$(dirname "$CLI")" "$SUPPORT/"
    CLI="$SUPPORT/$(basename "$(dirname "$CLI")")/filmcraft-cli";; esac
  [ "$OS" = "Darwin" ] && (xattr -dr com.apple.quarantine "$(dirname "$CLI")" 2>/dev/null || true)
  mkdir -p "$HOME/.local/bin"
  if [ "$CLI" != "$HOME/.local/bin/filmcraft-cli" ]; then
    ln -sf "$CLI" "$HOME/.local/bin/filmcraft-cli"
  fi
  ok "filmcraft-cli ($("$CLI" --version 2>/dev/null | head -1))"
else
  stop "filmcraft-cli not found. Download filmcraft-cli from FilmCraft's releases or build it with cargo build -p filmcraft-cli, then re-run."
fi

# 3. HyperFrames renderer for motion graphics (pinned versions, installed next to AutoEdit)
mkdir -p "$HERE/hyperframes"
( cd "$HERE/hyperframes" && { [ -f package.json ] || npm init -y >/dev/null 2>&1; } &&
  npm install --silent hyperframes@0.8.151 gsap@3.14.2 >/dev/null 2>&1 ) \
  && ok "HyperFrames renderer" || warn "HyperFrames install failed (motion graphics won't work; everything else will)"

# 4. Shared music library and native FilmCraft plugin
mkdir -p "$HOME/Music/AutoEdit"; ok "music folder: ~/Music/AutoEdit"
if PLUGIN_DEST=$(python3 "$HERE/plugin_runner.py" install 2>/dev/null); then
  ok "FilmCraft native plugin: Window ▸ Extensions ▸ AutoEdit"
fi

# 5. Build/Install companion panel and launcher
if [ "$OS" = "Darwin" ]; then
  mkdir -p "$APP/Contents/MacOS"
  swiftc -O "$HERE/src/main.swift" -o "$APP/Contents/MacOS/AutoEdit"
  cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>AutoEdit</string><key>CFBundleExecutable</key><string>AutoEdit</string>
<key>CFBundleIdentifier</key><string>local.autoedit.panel</string><key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>3</string><key>LSUIElement</key><true/><key>NSHighResolutionCapable</key><true/>
<key>LSEnvironment</key><dict><key>AUTOEDIT_DIR</key><string>$HERE</string></dict>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
EOF
  codesign --force -s - "$APP" >/dev/null 2>&1
  ok "panel app: ~/Applications/AutoEdit.app"

  # Login agent (macOS)
  mkdir -p "$(dirname "$AGENT")"
  cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>local.autoedit.companion</string>
<key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string>
<string>launchctl setenv FILMCRAFT_CONTROL_PORT $PORT; exec "$APP/Contents/MacOS/AutoEdit"</string></array>
<key>EnvironmentVariables</key><dict><key>AUTOEDIT_DIR</key><string>$HERE</string><key>FILMCRAFT_CONTROL_PORT</key><string>$PORT</string>
<key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
<key>RunAtLoad</key><true/><key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
</dict></plist>
EOF
  launchctl bootout "gui/$(id -u)/local.autoedit.companion" 2>/dev/null || true
  pkill -x AutoEdit 2>/dev/null || true
  lsof -ti tcp:8765 | xargs kill 2>/dev/null || true
  launchctl setenv FILMCRAFT_CONTROL_PORT $PORT
  launchctl bootstrap "gui/$(id -u)" "$AGENT"
  ok "starts at login (scissors icon in the menu bar)"
elif [ "$OS" = "Linux" ]; then
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/autoedit" <<EOF
#!/bin/sh
export AUTOEDIT_DIR="\${AUTOEDIT_DIR:-$HERE}"
export FILMCRAFT_CONTROL_PORT="\${FILMCRAFT_CONTROL_PORT:-$PORT}"
if [ "\$#" -gt 0 ] && [ "\$1" != "serve" ] && [ "\$1" != "panel" ]; then
  exec python3 "\$AUTOEDIT_DIR/autoedit.py" "\$@"
else
  exec python3 "\$AUTOEDIT_DIR/app.py" "\$@"
fi
EOF
  chmod +x "$BIN_DIR/autoedit"
  ok "command launcher: ~/.local/bin/autoedit"

  mkdir -p "$DESKTOP_DIR"
  cat > "$DESKTOP_DIR/autoedit.desktop" <<EOF
[Desktop Entry]
Name=AutoEdit
GenericName=Video Editing Companion
Comment=One-click editing panel for FilmCraft
Exec=$BIN_DIR/autoedit
Icon=video-x-generic
Terminal=false
Type=Application
Categories=AudioVideo;Video;AudioVideoEditing;
Keywords=filmcraft;video;edit;autocut;
EOF
  ok "desktop entry: ~/.local/share/applications/autoedit.desktop"

  mkdir -p "$SYSTEMD_DIR"
  cat > "$SYSTEMD_DIR/autoedit.service" <<EOF
[Unit]
Description=AutoEdit companion for FilmCraft
After=network.target

[Service]
Type=simple
Environment=AUTOEDIT_DIR=$HERE
Environment=AUTOEDIT_NO_BROWSER=1
Environment=FILMCRAFT_CONTROL_PORT=$PORT
ExecStart=/usr/bin/env python3 $HERE/app.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload 2>/dev/null || true
  ok "systemd service: ~/.config/systemd/user/autoedit.service"
fi

# 6. Optional: Claude Code integration (skill + FilmCraft MCP servers)
if command -v claude >/dev/null; then
  mkdir -p "$HOME/.claude/skills/autoedit"
  sed "s|{{AUTOEDIT_DIR}}|$HERE|g" "$HERE/claude-skill/SKILL.md" > "$HOME/.claude/skills/autoedit/SKILL.md"
  claude mcp remove filmcraft-live -s user >/dev/null 2>&1 || true
  claude mcp remove filmcraft-headless -s user >/dev/null 2>&1 || true
  claude mcp add filmcraft-live -s user -- "$HOME/.local/bin/filmcraft-cli" --bridge 127.0.0.1:$PORT mcp >/dev/null
  claude mcp add filmcraft-headless -s user -- "$HOME/.local/bin/filmcraft-cli" mcp --demo >/dev/null
  ok "Claude Code: autoedit skill + FilmCraft connection"
fi

if pgrep -xi FilmCraft >/dev/null && ! nc -z 127.0.0.1 $PORT 2>/dev/null; then
  warn "FilmCraft is open without AutoEdit's connection. Quit FilmCraft and open it again with FILMCRAFT_CONTROL_PORT=$PORT."
fi
echo
echo "Done! Open FilmCraft with control port $PORT; the AutoEdit panel is ready at http://127.0.0.1:8765"
echo "Put songs for your edits in ~/Music/AutoEdit."
echo
