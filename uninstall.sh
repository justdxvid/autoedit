#!/bin/bash
# Remove AutoEdit completely. Your FilmCraft projects, videos and ~/Music/AutoEdit songs are NOT touched.
OS="$(uname -s)"
echo "Removing AutoEdit ($OS)…"

pkill -f "python3.*app.py" 2>/dev/null || true
lsof -ti tcp:8765 2>/dev/null | xargs kill 2>/dev/null || true

if [ "$OS" = "Darwin" ]; then
  SUPPORT="$HOME/Library/Application Support/AutoEdit"
  launchctl bootout "gui/$(id -u)/local.autoedit.companion" 2>/dev/null || true
  launchctl unsetenv FILMCRAFT_CONTROL_PORT 2>/dev/null || true
  pkill -x AutoEdit 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/local.autoedit.companion.plist"
  rm -rf "$HOME/Applications/AutoEdit.app"
  rm -f "$HOME/Library/Logs/AutoEdit.log"
elif [ "$OS" = "Linux" ]; then
  SUPPORT="${XDG_DATA_HOME:-$HOME/.local/share}/autoedit"
  systemctl --user stop autoedit 2>/dev/null || true
  systemctl --user disable autoedit 2>/dev/null || true
  rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/autoedit.service"
  systemctl --user daemon-reload 2>/dev/null || true
  rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/autoedit.desktop"
  rm -f "$HOME/.local/bin/autoedit"
  rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/autoedit/AutoEdit.log"
fi

rm -rf "$SUPPORT"                       # app files, speech models, effect history snapshots
rm -f "$HOME/.local/bin/filmcraft-cli"
rm -rf "$HOME/.claude/skills/autoedit"

echo "Done. Kept: your projects, ~/Music/AutoEdit and ~/Videos/AutoEdit Overlays (delete those yourself if you want)."
