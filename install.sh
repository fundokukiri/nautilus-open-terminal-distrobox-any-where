#!/usr/bin/env bash
# Install the Nautilus extension into the *host* user's data directory.
#
# Safe to run from inside the distrobox container: the host home is used when
# DISTROBOX_HOST_HOME is set (distrobox exports it).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/nautilus_open_terminal_distrobox_any_where.py"

HOST_HOME="${DISTROBOX_HOST_HOME:-$HOME}"
DATA_HOME="${NAUTILUS_EXTENSION_DATA_HOME:-$HOST_HOME/.local/share}"
DEST_DIR="$DATA_HOME/nautilus-python/extensions"
DEST="$DEST_DIR/nautilus_open_terminal_distrobox_any_where.py"

CONTAINER="${NAUTILUS_DISTROBOX_CONTAINER:-}"
DEFAULT_CONTAINER=archlinux-box

# Same order as the extension: explicit config, $TERMINAL, then autodetection.
TERMINAL="${NAUTILUS_DISTROBOX_TERMINAL:-${TERMINAL:-}}"
TERMINALS=(alacritty kitty wezterm foot ghostty konsole gnome-terminal
  kgx ptyxis xfce4-terminal tilix terminator xterm urxvt st)

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }

# distrobox-host-exec needs host-spawn and does not always work; only trust it
# after a successful smoke test, otherwise the dependency checks would produce
# false negatives.
HOST_EXEC_OK=0
if [[ -n "${DISTROBOX_HOST_HOME:-}" ]] && command -v distrobox-host-exec >/dev/null 2>&1; then
  if distrobox-host-exec true >/dev/null 2>&1; then
    HOST_EXEC_OK=1
  fi
fi

host_exec() {
  if [[ "$HOST_EXEC_OK" -eq 1 ]]; then
    distrobox-host-exec "$@"
  else
    "$@"
  fi
}

host_has() {
  [[ "$HOST_EXEC_OK" -eq 1 ]] || return 1
  host_exec sh -c "command -v $1 >/dev/null 2>&1"
}

host_pkg_manager() {
  [[ "$HOST_EXEC_OK" -eq 1 ]] || return 1
  host_exec sh -c '. /etc/os-release 2>/dev/null && printf %s "$ID"' 2>/dev/null || true
}

[[ -f "$SOURCE" ]] || { err "Cannot find $SOURCE"; exit 1; }

info "Checking Python syntax"
python3 -m py_compile "$SOURCE"
ok "nautilus_open_terminal_distrobox_any_where.py is valid"

info "Installing extension into $DEST_DIR"
mkdir -p "$DEST_DIR"
install -m 0644 "$SOURCE" "$DEST"
ok "Installed $DEST"

# ---------------------------------------------------------------------------
# Host-side checks
# ---------------------------------------------------------------------------
if [[ "$HOST_EXEC_OK" -eq 1 ]]; then
  info "Checking host dependencies"

  if host_exec sh -c 'ls /usr/lib/nautilus/extensions-*/libnautilus-python.so >/dev/null 2>&1 \
    || ls /usr/lib64/nautilus/extensions-*/libnautilus-python.so >/dev/null 2>&1'; then
    ok "nautilus-python is installed"
  else
    warn "nautilus-python not found on the host — the extension will not load."
    case "$(host_pkg_manager)" in
      arch|manjaro|endeavouros)
        warn "  Install with: sudo pacman -S nautilus-python" ;;
      fedora)
        warn "  Install with: sudo dnf install nautilus-python" ;;
      debian|ubuntu|linuxmint|pop)
        warn "  Install with: sudo apt install nautilus-python   (or python3-nautilus)" ;;
      opensuse*|suse)
        warn "  Install with: sudo zypper install nautilus-python" ;;
      *)
        warn "  Install the host distro's nautilus-python package (Arch: sudo pacman -S nautilus-python)." ;;
    esac
  fi

  if [[ -z "$TERMINAL" ]]; then
    # Same preference as the extension: a terminal already running for this user.
    for candidate in "${TERMINALS[@]}"; do
      if host_exec pgrep -x "$candidate" >/dev/null 2>&1; then
        TERMINAL="$candidate"
        break
      fi
    done
  fi

  if [[ -z "$TERMINAL" ]]; then
    for candidate in "${TERMINALS[@]}"; do
      if host_has "$candidate"; then
        TERMINAL="$candidate"
        break
      fi
    done
  fi

  if [[ -z "$TERMINAL" ]]; then
    warn "No supported terminal found on the host. Install one, or set"
    warn "NAUTILUS_DISTROBOX_TERMINAL=<terminal>."
  elif host_has "$TERMINAL"; then
    ok "terminal '$TERMINAL' is on the host"
  else
    warn "terminal '$TERMINAL' not found on the host. Install it, or set"
    warn "NAUTILUS_DISTROBOX_TERMINAL=<another terminal>."
  fi

  if host_has distrobox; then
    ok "distrobox is on the host"
    if [[ -z "$CONTAINER" ]]; then
      CONTAINER="$(host_exec distrobox list --no-color 2>/dev/null \
        | awk -F'|' '$3 ~ /^ *(Up|up)/ {gsub(/ /, "", $2); print $2; exit}')"
      if [[ -n "$CONTAINER" ]]; then
        ok "running container: '$CONTAINER' (entered by default)"
      else
        warn "No container is running; the extension falls back to '$DEFAULT_CONTAINER'."
        warn "Start one with: distrobox enter $DEFAULT_CONTAINER"
        CONTAINER="$DEFAULT_CONTAINER"
      fi
    fi
    if host_exec distrobox list 2>/dev/null | grep -qE "(^|[[:space:]])${CONTAINER}([[:space:]]|$)"; then
      ok "container '$CONTAINER' exists"
    else
      warn "container '$CONTAINER' not found in 'distrobox list'."
      warn "Create it with: distrobox create --name $CONTAINER --image archlinux:latest"
    fi
  else
    warn "distrobox is not on the host — cannot 'distrobox enter'."
  fi
else
  warn "'distrobox-host-exec' does not work (usually a missing host-spawn),"
  warn "so host checks were skipped. Verify on the host yourself:"
  warn "  command -v distrobox alacritty   # or whichever terminal you use"
  warn "  the nautilus-python package (Arch: sudo pacman -S nautilus-python)"
fi

# ---------------------------------------------------------------------------
# Restart Nautilus (optional)
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--restart" ]]; then
  if [[ "$HOST_EXEC_OK" -eq 1 ]]; then
    info "Restarting Nautilus on the host (open windows will close)"
    host_exec nautilus -q >/dev/null 2>&1 || true
    ok "Nautilus stopped; open it again to load the extension"
  else
    warn "Cannot run 'nautilus -q' on the host from here. Run it manually on the host:"
    printf '    nautilus -q\n'
  fi
else
  info "Done. To load the extension, run on the host:"
  printf '    nautilus -q   # then open Nautilus again\n'
  printf '  or run this script again with --restart\n'
fi

info "Error log: $HOST_HOME/.cache/nautilus-open-terminal-distrobox-any-where/extension.log"
