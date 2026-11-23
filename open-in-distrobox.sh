#!/usr/bin/env bash
# Open a folder in your terminal running `distrobox enter <container>`.
#
# Usage:
#   ./open-in-distrobox.sh [DIRECTORY]
#
# Terminal selection lives in nautilus_open_terminal_distrobox_any_where.py, so this
# script, the Nautilus menu and the dry-run all behave the same.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target="${1:-$PWD}"

if [[ ! -d "$target" ]]; then
  echo "open-in-distrobox: not a directory: $target" >&2
  exit 1
fi

exec python3 "$SCRIPT_DIR/nautilus_open_terminal_distrobox_any_where.py" --run "$target"
