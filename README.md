# ConsoleDeck V2 (macOS)

ConsoleDeck is a customizable macro deck that lets you configure buttons to launch websites, applications, or fire keyboard shortcuts.
It integrates with Arduino hardware for physical button presses, volume control, and media playback.

---

## Requirements

- macOS 10.15 or later
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Arduino (optional, for hardware buttons)

---

## Setup

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
cd cd_v2_script
uv sync
```

---

## Usage

### GUI Mode (configure buttons)

```bash
uv run python main.py --gui
```

Or use the shell script:

```bash
./consoledeck.sh
```

### Serial Mode (listen for Arduino)

```bash
uv run python main.py
```

Or:

```bash
./avvio_consoledeck.sh
```

### Auto-start on login (run in background)

To have ConsoleDeck start automatically on login and run silently in the background, create a LaunchAgent. This is the recommended way to use it daily — no terminal window needed, and it restarts automatically if it crashes.

**1. Create the plist file:**

```bash
cat > ~/Library/LaunchAgents/com.consoledeck.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.consoledeck</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/williamlac/Personal/Programming/cd_v2_script/.venv/bin/python</string>
        <string>/Users/williamlac/Personal/Programming/cd_v2_script/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/williamlac/Personal/Programming/cd_v2_script</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/consoledeck.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/consoledeck.log</string>
</dict>
</plist>
EOF
```

**2. Load it (starts immediately and on every login):**

```bash
launchctl load ~/Library/LaunchAgents/com.consoledeck.plist
```

**Manage the service:**

```bash
launchctl start com.consoledeck    # start manually
launchctl stop com.consoledeck     # stop
tail -f /tmp/consoledeck.log       # view live logs
```

**Remove from startup:**

```bash
launchctl unload ~/Library/LaunchAgents/com.consoledeck.plist
```

---

## Button Types

| Type | Description |
|------|-------------|
| **LINK** | Opens a URL in your default browser |
| **APP** | Launches a macOS application (.app bundle) or executable |
| **SHORTCUT** | Fires a keyboard shortcut (e.g. `cmd+shift+4` for screenshot) |
| **NONE** | No action |

### Shortcut Format

Shortcuts are written as modifier keys joined by `+`, followed by the key:

- `cmd+shift+4` — screenshot selection
- `cmd+space` — Spotlight
- `cmd+c` — copy
- `ctrl+alt+delete` — (example with multiple modifiers)

**Modifiers**: `cmd`, `shift`, `ctrl`, `alt` (or `option`)

**Special keys**: `space`, `return`, `tab`, `escape`, `delete`, `up`, `down`, `left`, `right`, `f1`-`f12`

---

## Configuration

Settings are stored in `config.json`. The number of buttons is configurable:

```json
{
  "settings": {
    "num_buttons": 9
  },
  "buttons": {
    "BUTTON_1": {"type": "link", "value": "https://www.youtube.com"},
    "BUTTON_2": {"type": "shortcut", "value": "cmd+shift+4"},
    "BUTTON_3": {"type": "exe", "value": "/Applications/Safari.app"},
    ...
  }
}
```

Change `num_buttons` to add more buttons (the GUI grid adjusts automatically).

---

## Arduino

The Arduino is auto-detected on macOS. It looks for devices matching common Arduino chipsets (Arduino, CH340, CP210x) or falls back to `/dev/cu.usbmodem*` ports.

The Arduino firmware sends these serial messages:
- `BUTTON_1` through `BUTTON_N` — trigger button actions
- `VOLUME_<number>` — adjust system volume
- `MUTE` — toggle mute
- `MEDIA` — play/pause (targets Spotify first, then Music)

---

## Permissions

The **Shortcut** button type requires Accessibility permissions:

1. Open **System Settings > Privacy & Security > Accessibility**
2. Add your terminal app (Terminal, iTerm2, etc.) to the allowed list

This is required because keyboard shortcuts are simulated via macOS System Events.

---

## Troubleshooting

**GUI doesn't open?**
Make sure you're using `--gui` flag: `uv run python main.py --gui`

**Arduino not detected?**
Check that the Arduino is connected and visible in `/dev/cu.usbmodem*`. You may need to install CH340 drivers for Arduino clones.

**Shortcuts don't work?**
Grant Accessibility permissions to your terminal app (see Permissions section above).

**`uv` not found?**
Install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Uninstall

Delete the project folder. To remove uv: `rm ~/.local/bin/uv`
