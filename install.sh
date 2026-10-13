#!/bin/bash
# Install (or repair) AutoEdit so it behaves like a FilmCraft plugin.
# Safe to run again any time, e.g. after reinstalling FilmCraft or filmcraft-cli.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
PORT=9876
SUPPORT="$HOME/Library/Application Support/AutoEdit"
APP="$HOME/Applications/AutoEdit.app"
AGENT="$HOME/Library/LaunchAgents/local.autoedit.companion.plist"
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
stop() { printf '\n  \033[31m✗ %s\033[0m\n\n' "$1"; exit 1; }

echo
echo "AutoEdit installer"
echo

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

# 1. Apple's command-line tools (to build the panel app) and Homebrew (for the media tools)
xcode-select -p >/dev/null 2>&1 || { xcode-select --install 2>/dev/null || true
  stop "Apple's command-line tools are needed. A window to install them just opened; finish it, then run this installer again."; }
command -v swiftc >/dev/null || stop "Swift compiler not found even though the command-line tools are installed. Run: xcode-select --install"
ok "Apple command-line tools"
BREW=$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1 || true)
[ -n "$BREW" ] || stop "Homebrew is needed. Install it from https://brew.sh (one command), then run this installer again."
eval "$("$BREW" shellenv)"
ok "Homebrew"

# 2. Media tools: ffmpeg (audio/beat analysis), whisper.cpp (speech to text), Node (HyperFrames renderer)
for pkg in ffmpeg whisper-cpp node; do
  if "$BREW" list --formula "$pkg" >/dev/null 2>&1; then ok "$pkg"
  else echo "  … installing $pkg (one time, can take a few minutes)"; "$BREW" install "$pkg" >/dev/null && ok "$pkg installed"; fi
done
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
[ "$NODE_MAJOR" -ge 22 ] || warn "Node $NODE_MAJOR found; motion graphics need Node 22+ (brew upgrade node)"

# 3. FilmCraft and its command-line tool
if [ -d /Applications/FilmCraft.app ] || [ -d "$HOME/Applications/FilmCraft.app" ]; then ok "FilmCraft app"
else warn "FilmCraft.app not found in Applications. Install FilmCraft, then run this installer again."; fi
CLI=$(ls -d "$SRC"/filmcraft-cli-*/filmcraft-cli "$HOME"/tools/filmcraft-cli-*/filmcraft-cli "$HOME"/Downloads/filmcraft-cli-*/filmcraft-cli \
        "$HOME"/Applications/filmcraft-cli-*/filmcraft-cli "$SUPPORT"/filmcraft-cli-*/filmcraft-cli 2>/dev/null | sort -V | tail -1 || true)
if [ -n "$CLI" ]; then
  case "$CLI" in "$SUPPORT"/*) ;; *)           # keep our own copy so cleaning Downloads doesn't break AutoEdit
    rm -rf "$SUPPORT/$(basename "$(dirname "$CLI")")"; cp -R "$(dirname "$CLI")" "$SUPPORT/"
    CLI="$SUPPORT/$(basename "$(dirname "$CLI")")/filmcraft-cli";; esac
  xattr -dr com.apple.quarantine "$(dirname "$CLI")" 2>/dev/null || true
  mkdir -p "$HOME/.local/bin"; ln -sf "$CLI" "$HOME/.local/bin/filmcraft-cli"
  ok "filmcraft-cli ($("$CLI" --version 2>/dev/null | head -1))"
else
  stop "filmcraft-cli not found. Download the filmcraft-cli zip for macOS from FilmCraft's releases, unzip it into Downloads, then run this installer again."
fi

# 4. HyperFrames renderer for motion graphics (pinned versions, installed next to AutoEdit)
mkdir -p "$HERE/hyperframes"
( cd "$HERE/hyperframes" && { [ -f package.json ] || npm init -y >/dev/null; } &&
  npm install --silent hyperframes@0.8.151 gsap@3.14.2 >/dev/null 2>&1 ) \
  && ok "HyperFrames renderer" || warn "HyperFrames install failed (motion graphics won't work; everything else will)"

# 5. Shared music library
mkdir -p "$HOME/Music/AutoEdit"; ok "music folder: ~/Music/AutoEdit"

# 6. Build the companion panel (built on this Mac, so it runs on Apple Silicon and Intel alike)
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

# 7. Login agent: lets FilmCraft (opened from the Dock) expose its control port, and keeps the panel running
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
lsof -ti tcp:8765 | xargs kill 2>/dev/null || true   # the panel's old server, so the new code is loaded
launchctl setenv FILMCRAFT_CONTROL_PORT $PORT
launchctl bootstrap "gui/$(id -u)" "$AGENT"
ok "starts at login (scissors icon in the menu bar)"

# 8. Optional: Claude Code integration (skill + FilmCraft MCP servers), only if Claude Code is installed
if command -v claude >/dev/null; then
  mkdir -p "$HOME/.claude/skills/autoedit"
  sed "s|{{AUTOEDIT_DIR}}|$HERE|g" "$HERE/claude-skill/SKILL.md" > "$HOME/.claude/skills/autoedit/SKILL.md"
  claude mcp remove filmcraft-live -s user >/dev/null 2>&1 || true
  claude mcp remove filmcraft-headless -s user >/dev/null 2>&1 || true
  claude mcp add filmcraft-live -s user -- "$HOME/.local/bin/filmcraft-cli" --bridge 127.0.0.1:$PORT mcp >/dev/null
  claude mcp add filmcraft-headless -s user -- "$HOME/.local/bin/filmcraft-cli" mcp --demo >/dev/null
  ok "Claude Code: autoedit skill + FilmCraft connection"
fi

if pgrep -x FilmCraft >/dev/null && ! nc -z 127.0.0.1 $PORT 2>/dev/null; then
  warn "FilmCraft is open without AutoEdit's connection. Quit FilmCraft and open it again."
fi
echo
echo "Done! Open FilmCraft normally; the AutoEdit panel appears next to it."
echo "Put songs for your edits in ~/Music/AutoEdit."
echo
