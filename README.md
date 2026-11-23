# Nautilus → Distrobox (any terminal)

A small Nautilus extension: right-click a folder (or empty space) → **Open in
Distrobox (your running container)** → your terminal opens and runs:

```bash
<terminal> <args> /usr/bin/distrobox enter <running container>
```

## Features

- Context menu entry for a selected folder/file, and for empty space.
- The selected folder becomes the terminal's `cwd` (`distrobox enter` keeps the
  current directory when it lives inside your home).
- Never blocks Nautilus: the terminal is spawned in its own session
  (`start_new_session`).
- Works with most terminals: `alacritty`, `kitty`, `wezterm`, `foot`, `ghostty`,
  `konsole`, `gnome-terminal`, `kgx`, `ptyxis`, `xfce4-terminal`, `tilix`,
  `terminator`, `xterm`, `urxvt`, `st`. Anything else falls back to `-e`.
- Terminal lookup order: `NAUTILUS_DISTROBOX_TERMINAL` → `$TERMINAL` → a terminal you
  are already running → the first supported terminal installed on the host.
- Container lookup order: `NAUTILUS_DISTROBOX_CONTAINER` → the container
  `distrobox list` reports as running → `archlinux-box`. The menu label and the
  command always show the container that will actually be entered, and the choice
  is re-evaluated on every menu open (no Nautilus restart needed after starting a
  container).
- Finds the terminal and `distrobox` through `PATH` and the usual install
  locations (`/usr/bin`, `/usr/local/bin`, `~/.cargo/bin`, `~/.local/bin`,
  `/var/lib/flatpak/exports/bin`).
- Errors are logged to `~/.cache/nautilus-open-terminal-distrobox-any-where/extension.log`.
- Compatible with the Nautilus 3.0, 4.0 and 4.1 APIs (GNOME 43+). It never calls
  `gi.require_version()` to avoid "Namespace Nautilus is already loaded with
  version 4.1".

## Requirements (on the **host**, not inside the container)

| Component | Notes |
|---|---|
| `nautilus-python` | Required, so Nautilus loads Python extensions |
| `nautilus` | Any current version |
| any terminal | Defaults to `$TERMINAL`, otherwise auto-detected |
| `distrobox` | Usually `/usr/bin/distrobox` |
| at least one container | Created with `distrobox create` |

Install `nautilus-python`:

```bash
# Arch
sudo pacman -S nautilus-python
# Fedora
sudo dnf install nautilus-python
# Debian/Ubuntu
sudo apt install nautilus-python
# openSUSE
sudo zypper install nautilus-python
```

> The extension runs inside the host's Nautilus process, so the terminal and
> `distrobox` must exist on the **host**. If they are only installed inside the
> container, the menu appears but no window can open.

## Install

Run it from this folder (works from inside distrobox too — the script writes to
the host home via `$DISTROBOX_HOST_HOME`):

```bash
chmod +x install.sh uninstall.sh open-in-distrobox.sh
./install.sh
```

Then restart Nautilus:

```bash
nautilus -q      # on the host; open windows will close
```

or let the script do it:

```bash
./install.sh --restart
```

Installed file:

```
~/.local/share/nautilus-python/extensions/nautilus_open_terminal_distrobox_any_where.py
```

Pick a terminal while installing:

```bash
NAUTILUS_DISTROBOX_TERMINAL=kitty ./install.sh
```

> When run from inside the container, `install.sh` tries to check host
> dependencies through `distrobox-host-exec`. If the container lacks
> `host-spawn`, the script says it cannot verify them — then check
> `command -v distrobox <terminal>` and the `nautilus-python` package on the host
> yourself.

## Configuration

Environment variables are read **when Nautilus starts**. Put them in
`~/.config/environment.d/*.conf` (systemd user) or in the desktop session, then
restart Nautilus:

```ini
# ~/.config/environment.d/nautilus-distrobox.conf
NAUTILUS_DISTROBOX_CONTAINER=archlinux-box   # optional: pin one container
NAUTILUS_DISTROBOX_TERMINAL=kitty
NAUTILUS_DISTROBOX_BIN=/usr/bin/distrobox
NAUTILUS_DISTROBOX_LABEL=Open in Distrobox (archlinux-box)
```

| Variable | Default |
|---|---|
| `NAUTILUS_DISTROBOX_CONTAINER` | the running container, else `archlinux-box` |
| `NAUTILUS_DISTROBOX_TERMINAL` | `$TERMINAL`, else the terminal in use, else auto-detected |
| `NAUTILUS_DISTROBOX_BIN` | `/usr/bin/distrobox` |
| `NAUTILUS_DISTROBOX_LABEL` | `Open in Distrobox (<container>)` |

Leaving `NAUTILUS_DISTROBOX_TERMINAL` unset is enough in most setups: the
extension uses the desktop session's `$TERMINAL` and, if that is unset as well,
opens the terminal you are already running (it looks for a supported terminal
process of yours in `/proc`). Only when none is running does it fall back to the
first supported terminal installed on the host.

To change something permanently without environment variables, edit the
`CONTAINER`, `DISTROBOX_BIN`, `MENU_LABEL` constants or the `_TERMINAL_ARGS` /
`_KNOWN_TERMINALS` tables at the top of `nautilus_open_terminal_distrobox_any_where.py`
and install again.

## Quick check

See the exact command the extension would run, without Nautilus:

```bash
python3 nautilus_open_terminal_distrobox_any_where.py ~/Downloads
# cwd:  /home/<user>/Downloads
# argv: kitty -e /usr/bin/distrobox enter archlinux-box

# Try a specific terminal:
NAUTILUS_DISTROBOX_TERMINAL=wezterm python3 nautilus_open_terminal_distrobox_any_where.py
# argv: wezterm start -- /usr/bin/distrobox enter archlinux-box

# Or actually open it:
./open-in-distrobox.sh ~/Downloads
```

Read the log:

```bash
tail -f ~/.cache/nautilus-open-terminal-distrobox-any-where/extension.log
```

Check whether Nautilus loaded the extension:

```bash
journalctl --user -b -o cat | grep -i -E 'nautilus|python' | tail -50
```

## Uninstall

```bash
./uninstall.sh
nautilus -q
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No entry in the context menu | Missing `nautilus-python`, or Nautilus was not restarted. Check `journalctl`. |
| Menu appears but no window | The terminal is missing on the host, or its name is wrong. Check the log, try `./open-in-distrobox.sh`, and set `NAUTILUS_DISTROBOX_TERMINAL`. |
| Window opens and closes at once | The terminal ran the command but `distrobox enter` failed; run `<terminal> <args> /usr/bin/distrobox enter archlinux-box` in a terminal to see the error. |
| Terminal opens but skips the command | That terminal needs a different syntax than `-e`; add it to `_TERMINAL_ARGS` in the extension file. |
| Container not found | Run `distrobox list` on the host; create it with `distrobox create --name archlinux-box --image archlinux:latest`, or pin one with `NAUTILUS_DISTROBOX_CONTAINER`. |
| Nautilus runs as a Flatpak | This extension does **not** work inside the Flatpak sandbox; use the distro's Nautilus. |

## Layout

```
nautilus_open_terminal_distrobox_any_where.py   # extension (Nautilus.MenuProvider) + terminal selection
open-in-distrobox.sh                   # run the command directly (testing / keyboard shortcut)
install.sh                             # install + check host dependencies
uninstall.sh                           # remove
```
