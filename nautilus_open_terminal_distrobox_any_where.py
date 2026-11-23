#!/usr/bin/env python3
"""Nautilus extension: open the current folder in any terminal running
``distrobox enter <container>``.

Inspired by Stunkymonkey/nautilus-open-any-terminal, but self-contained and
tuned for a distrobox workflow.

The extension runs inside the *host* Nautilus process, therefore the terminal
and ``distrobox`` must be installed on the host (not only inside the
container).

Configuration is done with environment variables read when Nautilus starts:

    NAUTILUS_DISTROBOX_CONTAINER   container name      (default: the running one, else archlinux-box)
    NAUTILUS_DISTROBOX_TERMINAL    terminal executable (default: $TERMINAL, else the one in use)
    NAUTILUS_DISTROBOX_BIN         distrobox path      (default: /usr/bin/distrobox)
    NAUTILUS_DISTROBOX_LABEL       context menu label  (default: "Open in Distrobox ({container})")
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

EXTENSION_NAME = "nautilus-open-terminal-distrobox-any-where"

# Nautilus is usually started by systemd/GNOME Shell and may have a smaller
# PATH than an interactive shell, so look in the common install locations too.
_COMMON_BIN_DIRS = (
    "/usr/bin",
    "/usr/local/bin",
    "/var/lib/flatpak/exports/bin",
    str(Path.home() / ".cargo/bin"),
    str(Path.home() / ".local/bin"),
)

# Arguments that make a terminal run the command given after them. Terminals
# missing from this table fall back to "-e".
_TERMINAL_ARGS = {
    "alacritty": ("-e",),
    "kitty": ("-e",),
    "foot": ("-e",),
    "st": ("-e",),
    "xterm": ("-e",),
    "urxvt": ("-e",),
    "rxvt": ("-e",),
    "konsole": ("-e",),
    "tilix": ("-e",),
    "ghostty": ("-e",),
    "xfce4-terminal": ("-x",),
    "terminator": ("-x",),
    "gnome-terminal": ("--",),
    "kgx": ("--",),
    "ptyxis": ("--",),
    "wezterm": ("start", "--"),
}

# Autodetection order when neither NAUTILUS_DISTROBOX_TERMINAL nor $TERMINAL is set.
_KNOWN_TERMINALS = (
    "alacritty", "kitty", "wezterm", "foot", "ghostty", "konsole",
    "gnome-terminal", "kgx", "ptyxis", "xfce4-terminal", "tilix",
    "terminator", "xterm", "urxvt", "st",
)


def _candidates(name: str) -> tuple[str, ...]:
    """Paths where *name* is commonly installed, ignoring its directory."""
    return tuple(os.path.join(d, os.path.basename(name)) for d in _COMMON_BIN_DIRS)


def _running_terminal() -> str | None:
    """A supported terminal that this user is already running, if any.

    Nautilus is started by systemd, so its process ancestry says nothing about
    the terminal in use; scan /proc instead.
    """
    try:
        pids = [p for p in Path("/proc").iterdir() if p.name.isdigit()]
    except OSError:
        return None
    uid = os.getuid()
    running = set()
    for pid in pids:
        try:
            if pid.stat().st_uid != uid:
                continue
            # comm is truncated to 15 chars, and e.g. wezterm runs as "wezterm-gui".
            running.add((pid / "comm").read_text().strip())
        except OSError:
            continue
    for name in _KNOWN_TERMINALS:
        for comm in running:
            if comm == name or comm.startswith(name + "-"):
                return name
    return None


def _detect_terminal() -> str:
    """Pick the terminal: explicit config, $TERMINAL, the one in use, any found."""
    for value in (
        os.environ.get("NAUTILUS_DISTROBOX_TERMINAL"),
        os.environ.get("TERMINAL"),
    ):
        value = (value or "").strip()
        if value:
            return value
    running = _running_terminal()
    if running:
        return running
    for name in _KNOWN_TERMINALS:
        if os.access(_resolve_executable(name, _candidates(name)), os.X_OK):
            return name
    return "alacritty"


DEFAULT_CONTAINER = "archlinux-box"
# Explicit choice wins over autodetection; see current_container().
CONTAINER = (os.environ.get("NAUTILUS_DISTROBOX_CONTAINER") or "").strip()
DISTROBOX_BIN = (os.environ.get("NAUTILUS_DISTROBOX_BIN") or "/usr/bin/distrobox").strip()
# "{container}" is replaced with the container that will actually be entered.
MENU_LABEL = (
    os.environ.get("NAUTILUS_DISTROBOX_LABEL") or "Open in Distrobox ({container})"
).strip()

_LOG_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / EXTENSION_NAME
)
_LOG_FILE = _LOG_DIR / "extension.log"


def _logger() -> logging.Logger:
    log = logging.getLogger(EXTENSION_NAME)
    if not log.handlers:
        log.setLevel(logging.INFO)
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
        except OSError:
            handler = logging.NullHandler()
        log.addHandler(handler)
    return log


def _resolve_executable(value: str, candidates: tuple[str, ...]) -> str:
    """Return an executable path for *value*, trying PATH and known locations."""
    if os.path.isabs(value):
        if os.access(value, os.X_OK):
            return value
        found = shutil.which(os.path.basename(value))
        if found:
            return found
    else:
        found = shutil.which(value)
        if found:
            return found

    for candidate in candidates:
        if os.access(candidate, os.X_OK):
            return candidate
    return value


TERMINAL = _detect_terminal()


def _running_container() -> str | None:
    """Name of a container that distrobox reports as running, if any."""
    distrobox = _resolve_executable(DISTROBOX_BIN, _candidates("distrobox"))
    try:
        # shortcut: shells out on every menu open (~100ms); cache if it hurts
        out = subprocess.run(
            [distrobox, "list", "--no-color"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines()[1:]:  # first line is the header
        cols = [col.strip() for col in line.split("|")]
        if len(cols) >= 3 and cols[2].lower().startswith("up"):
            return cols[1]
    return None


def current_container() -> str:
    """Configured container, else the running one, else the default name."""
    return CONTAINER or _running_container() or DEFAULT_CONTAINER


def _label(container: str) -> str:
    return MENU_LABEL.replace("{container}", container)


def build_command(
    directory: Path | None = None, container: str | None = None
) -> list[str]:
    """Build the argv used to open the terminal.

    ``directory`` is only used by :func:`launch` as the child working directory;
    it is accepted here so the dry-run mode has the same signature.
    """
    terminal = _resolve_executable(TERMINAL, _candidates(TERMINAL))
    distrobox = _resolve_executable(DISTROBOX_BIN, _candidates("distrobox"))
    run_args = _TERMINAL_ARGS.get(os.path.basename(TERMINAL), ("-e",))
    return [terminal, *run_args, distrobox, "enter", container or current_container()]


def launch(directory: Path, container: str | None = None) -> bool:
    """Spawn the terminal detached from Nautilus."""
    log = _logger()
    directory = Path(directory)
    cwd = str(directory) if directory.is_dir() else None
    argv = build_command(directory, container)

    env = os.environ.copy()
    # Not valid for a freshly spawned window.
    env.pop("XDG_ACTIVATION_TOKEN", None)

    log.info("launching %r (cwd=%s)", argv, cwd)
    try:
        subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        log.exception("could not launch %r", argv)
        return False
    return True


def _local_path(info) -> Path | None:
    """Return the local filesystem path of a Nautilus.FileInfo, if any."""
    if info is None:
        return None
    try:
        location = info.get_location()
    except Exception:
        return None
    if location is None:
        return None
    try:
        if location.get_uri_scheme() != "file":
            return None
        path = location.get_path()
    except Exception:
        return None
    return Path(path) if path else None


def _directory_for(files) -> Path | None:
    """Pick the directory to open from a list of Nautilus.FileInfo objects."""
    for info in files or ():
        path = _local_path(info)
        if path is None:
            continue
        try:
            return path if path.is_dir() else path.parent
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# Nautilus bindings
# ---------------------------------------------------------------------------

_NAUTILUS_IMPORT_ERROR: Exception | None = None

try:
    # nautilus-python loads the Nautilus namespace (4.0, 4.1, ...) before it
    # imports extensions, so do *not* pin a version here: calling
    # gi.require_version("Nautilus", "4.0") fails with
    # "Namespace Nautilus is already loaded with version 4.1".
    from gi.repository import GObject, Nautilus  # noqa: E402
except Exception as exc:  # pragma: no cover - depends on the host install
    _NAUTILUS_IMPORT_ERROR = exc
    GObject = None  # type: ignore[assignment]
    Nautilus = None  # type: ignore[assignment]

_EXTENSION_AVAILABLE = Nautilus is not None and hasattr(Nautilus, "MenuProvider")

if not _EXTENSION_AVAILABLE and __name__ != "__main__":
    print(
        f"[{EXTENSION_NAME}] Nautilus bindings unavailable: "
        f"{_NAUTILUS_IMPORT_ERROR or 'Nautilus.MenuProvider is missing (install nautilus-python)'}",
        file=sys.stderr,
    )


if _EXTENSION_AVAILABLE:

    def _new_menu_item(name: str, label: str, tip: str):
        """Create a MenuItem, tolerating API differences between versions."""
        # Nautilus 3.x/4.x expect an icon *name*; only some versions want a
        # GIcon. Try the common case first and fall back gracefully.
        attempts = (
            {"name": name, "label": label, "tip": tip, "icon": "utilities-terminal"},
            {"name": name, "label": label, "tip": tip},
            {"name": name, "label": label},
        )
        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                return Nautilus.MenuItem(**kwargs)
            except TypeError as exc:
                last_error = exc
        raise last_error  # type: ignore[misc]

    class OpenInDistroboxExtension(GObject.GObject, Nautilus.MenuProvider):
        """Adds "Open in Distrobox (<container>)" to the context menu."""

        def _menu_item(self, directory: Path):
            # Resolved per menu open, so a container started meanwhile is seen.
            container = current_container()
            item = _new_menu_item(
                f"{EXTENSION_NAME}::open-in-distrobox",
                _label(container),
                " ".join(build_command(container=container)),
            )
            item.connect("activate", lambda _item: launch(directory, container))
            return item

        # Nautilus 3.0: (window, files) / Nautilus 4.0: (files)
        def get_file_items(self, *args):
            files = args[-1] if args else ()
            directory = _directory_for(files)
            if directory is None:
                return []
            return [self._menu_item(directory)]

        # Nautilus 3.0: (window, current_folder) / Nautilus 4.0: (current_folder)
        def get_background_items(self, *args):
            current_folder = args[-1] if args else None
            directory = _directory_for([current_folder])
            if directory is None:
                return []
            return [self._menu_item(directory)]


def _main(argv: list[str]) -> int:
    """Dry-run helper (default) or launch the terminal with ``--run``."""
    paths = [arg for arg in argv[1:] if not arg.startswith("-")]
    directory = Path(paths[0]).expanduser() if paths else Path.cwd()
    if "--run" in argv[1:]:
        return 0 if launch(directory) else 1
    print(f"cwd:  {directory}")
    print(f"argv: {' '.join(build_command(directory))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
