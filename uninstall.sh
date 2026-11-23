#!/usr/bin/env bash
# Remove the Nautilus extension installed by install.sh.
set -euo pipefail

HOST_HOME="${DISTROBOX_HOST_HOME:-$HOME}"
DATA_HOME="${NAUTILUS_EXTENSION_DATA_HOME:-$HOST_HOME/.local/share}"
DEST="$DATA_HOME/nautilus-python/extensions/nautilus_open_terminal_distrobox_any_where.py"
# Names used by older versions of this repo; removed so two never load at once.
LEGACY_NAMES=(nautilus_terminal_distrobox_any_where.py nautilus_open_distrobox_any_where.py nautilus_distrobox_alacritty.py)

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

if [[ -f "$DEST" ]]; then
  rm -f "$DEST"
  info "Removed $DEST"
else
  info "Nothing to remove ($DEST does not exist)"
fi

for name in "${LEGACY_NAMES[@]}"; do
  if [[ -f "$DATA_HOME/nautilus-python/extensions/$name" ]]; then
    rm -f "$DATA_HOME/nautilus-python/extensions/$name"
    info "Removed the legacy copy $DATA_HOME/nautilus-python/extensions/$name"
  fi
done

if [[ "${1:-}" == "--restart" ]]; then
  if command -v distrobox-host-exec >/dev/null 2>&1 \
     && distrobox-host-exec true >/dev/null 2>&1; then
    distrobox-host-exec nautilus -q >/dev/null 2>&1 || true
    info "Nautilus stopped on the host; open it again to apply"
  else
    warn "Run manually on the host: nautilus -q"
  fi
fi
