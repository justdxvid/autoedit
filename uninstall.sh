#!/bin/bash
# Remove AutoEdit completely. Your FilmCraft projects, videos and ~/Music/AutoEdit songs are NOT touched.
SUPPORT="$HOME/Library/Application Support/AutoEdit"
echo "Removing AutoEdit…"
launchctl bootout "gui/$(id -u)/local.autoedit.companion" 2>/dev/null
launchctl unsetenv FILMCRAFT_CONTROL_PORT 2>/dev/null
pkill -x AutoEdit 2>/dev/null
lsof -ti tcp:8765 | xargs kill 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/local.autoedit.companion.plist"
rm -rf "$HOME/Applications/AutoEdit.app"
rm -rf "$SUPPORT"                       # app files, speech models, effect history snapshots
rm -f "$HOME/.local/bin/filmcraft-cli" "$HOME/Library/Logs/AutoEdit.log"
rm -rf "$HOME/.claude/skills/autoedit"
echo "Done. Kept: your projects, ~/Music/AutoEdit and ~/Movies/AutoEdit Overlays (delete those yourself if you want)."
echo "Homebrew tools (ffmpeg, whisper-cpp, node) were left installed: brew uninstall ffmpeg whisper-cpp node"
