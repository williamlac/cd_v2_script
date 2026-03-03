import os
import json
import subprocess
import webbrowser
import serial
import serial.tools.list_ports
import glob
import time
import math

BAUDRATE = 9600

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Selected button state
pulsante_selezionato = None

# Internal state for volume
last_volume_value = 0
is_muted = False
_saved_volume = 50

# Key code map for special keys (macOS key codes for AppleScript)
KEY_CODE_MAP = {
    "space": 49,
    "return": 36,
    "enter": 36,
    "tab": 48,
    "escape": 53,
    "esc": 53,
    "delete": 51,
    "backspace": 51,
    "forwarddelete": 117,
    "up": 126,
    "down": 125,
    "left": 123,
    "right": 124,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pagedown": 121,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
}

# Modifier map for AppleScript
MODIFIER_MAP = {
    "cmd": "command down",
    "command": "command down",
    "shift": "shift down",
    "ctrl": "control down",
    "control": "control down",
    "alt": "option down",
    "option": "option down",
}


def detect_arduino_port():
    """Auto-detect the Arduino serial port on macOS."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").lower()
        mfr = (port.manufacturer or "").lower()
        if any(k in desc or k in mfr for k in ["arduino", "ch340", "cp210"]):
            print(f"[DEBUG] Arduino detected on {port.device} ({port.description})")
            return port.device
    # Fallback: look for common macOS USB serial devices
    candidates = glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
    if candidates:
        print(f"[DEBUG] Serial device found: {candidates[0]}")
        return candidates[0]
    return None


PORTA_ARDUINO = detect_arduino_port()
if PORTA_ARDUINO is None:
    print("[WARNING] No Arduino detected. Serial features will not work.")


# --- Config ---

DEFAULT_NUM_BUTTONS = 9


def load_config():
    """Load config from disk. Supports both old flat format and new structured format."""
    print(f"[DEBUG] Loading config from: {CONFIG_FILE}")
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            raw = json.load(f)

        # New structured format
        if "settings" in raw and "buttons" in raw:
            config = raw
        else:
            # Old flat format (BUTTON_1..BUTTON_9 at top level) — migrate
            num = len([k for k in raw if k.startswith("BUTTON_")])
            config = {
                "settings": {"num_buttons": max(num, DEFAULT_NUM_BUTTONS)},
                "buttons": {k: v for k, v in raw.items() if k.startswith("BUTTON_")},
            }

        # Ensure all buttons exist up to num_buttons
        num_buttons = config["settings"].get("num_buttons", DEFAULT_NUM_BUTTONS)
        for i in range(1, num_buttons + 1):
            key = f"BUTTON_{i}"
            if key not in config["buttons"]:
                config["buttons"][key] = {"type": "none", "value": ""}

        print("[DEBUG] Config loaded:", json.dumps(config, indent=2))
        return config
    else:
        print("[DEBUG] Config file not found, creating default config.")
        config = {
            "settings": {"num_buttons": DEFAULT_NUM_BUTTONS},
            "buttons": {},
        }
        for i in range(1, DEFAULT_NUM_BUTTONS + 1):
            config["buttons"][f"BUTTON_{i}"] = {"type": "none", "value": ""}
        config["buttons"]["BUTTON_1"] = {"type": "link", "value": "https://www.youtube.com"}
        return config


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_buttons(config):
    """Get the buttons dict from config."""
    return config.get("buttons", config)


def get_num_buttons(config):
    """Get the configured number of buttons."""
    return config.get("settings", {}).get("num_buttons", DEFAULT_NUM_BUTTONS)


# --- Action Handlers ---

def _handle_link(value):
    if value:
        webbrowser.open(value)
    else:
        print("[WARNING] No URL defined")


def _handle_app(value):
    if value:
        try:
            subprocess.Popen(["open", value])
        except Exception as e:
            print(f"[ERROR] Opening application: {e}")
    else:
        print("[WARNING] No application path defined")


def _handle_shortcut(value):
    """Fire a keyboard shortcut. Format: 'cmd+shift+4', 'ctrl+c', 'cmd+space'"""
    if not value:
        print("[WARNING] No shortcut defined")
        return

    parts = [p.strip().lower() for p in value.split("+")]
    if len(parts) < 2:
        print(f"[ERROR] Invalid shortcut format: {value}")
        return

    key = parts[-1]
    modifiers = parts[:-1]

    applescript_mods = []
    for m in modifiers:
        if m in MODIFIER_MAP:
            applescript_mods.append(MODIFIER_MAP[m])
        else:
            print(f"[WARNING] Unknown modifier: {m}")

    mods_str = ", ".join(applescript_mods)

    if len(key) == 1:
        # Single character key
        script = f'tell application "System Events" to keystroke "{key}" using {{{mods_str}}}'
    elif key in KEY_CODE_MAP:
        # Special key
        code = KEY_CODE_MAP[key]
        script = f'tell application "System Events" to key code {code} using {{{mods_str}}}'
    else:
        print(f"[ERROR] Unknown key: {key}")
        return

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] AppleScript error: {result.stderr.strip()}")
    else:
        print(f"[DEBUG] Shortcut fired: {value}")


def _handle_none(value):
    print("[DEBUG] No action defined")


# Action type registry — add new types here
ACTION_HANDLERS = {
    "link": _handle_link,
    "exe": _handle_app,
    "shortcut": _handle_shortcut,
    "none": _handle_none,
}


def esegui_azione(azione):
    """Execute a button action using the action registry."""
    action_type = azione.get("type", "none")
    handler = ACTION_HANDLERS.get(action_type)
    if handler:
        handler(azione.get("value", ""))
    else:
        print(f"[WARNING] Unknown action type: {action_type}")


# --- Serial ---

def ascolta_seriale(config):
    if PORTA_ARDUINO is None:
        print("[ERROR] No Arduino port detected. Cannot start serial listener.")
        print("[INFO] Connect an Arduino and restart the application.")
        return

    buttons = get_buttons(config)
    try:
        with serial.Serial(PORTA_ARDUINO, BAUDRATE, timeout=1) as ser:
            print(f"Connected to {PORTA_ARDUINO}")
            while True:
                linea = ser.readline().decode("utf-8").strip()
                if linea:
                    print("Received:", linea)
                    if linea.startswith("VOLUME_"):
                        valore = linea.replace("VOLUME_", "")
                        gestisci_volume(valore)
                    elif linea == "MUTE":
                        gestisci_mute()
                    elif linea == "MEDIA":
                        gestisci_media()
                    elif linea in buttons:
                        esegui_azione(buttons[linea])
    except Exception as e:
        print(f"[ERROR] Serial port: {e}")
        time.sleep(5)
        ascolta_seriale(config)


# --- Volume / Mute / Media (macOS via AppleScript) ---

def gestisci_volume(value):
    global last_volume_value
    try:
        valore = int(value)
        delta = valore - last_volume_value
        if delta != 0:
            step = 6.25 * delta
            script = (
                f"set curVol to output volume of (get volume settings)\n"
                f"set newVol to curVol + {step}\n"
                f"if newVol > 100 then set newVol to 100\n"
                f"if newVol < 0 then set newVol to 0\n"
                f"set volume output volume newVol"
            )
            subprocess.run(["osascript", "-e", script], capture_output=True)
            print(f"[DEBUG] Volume adjusted by {delta}")
        last_volume_value = valore
    except ValueError:
        print("[ERROR] Invalid volume value:", value)


def gestisci_mute():
    global is_muted, _saved_volume
    if not is_muted:
        # Save current volume then mute
        result = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True,
            text=True,
        )
        try:
            _saved_volume = int(result.stdout.strip())
        except ValueError:
            _saved_volume = 50
        subprocess.run(["osascript", "-e", "set volume output volume 0"], capture_output=True)
    else:
        # Restore saved volume
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {_saved_volume}"],
            capture_output=True,
        )
    is_muted = not is_muted
    print(f"[DEBUG] Mute toggled -> {'ON' if is_muted else 'OFF'}")


def gestisci_media():
    script = """
    try
        tell application "System Events"
            if (name of processes) contains "Spotify" then
                tell application "Spotify" to playpause
                return
            end if
        end tell
    end try
    try
        tell application "Music" to playpause
    end try
    """
    subprocess.run(["osascript", "-e", script], capture_output=True)
    print("[DEBUG] Media play/pause triggered")


# --- Button selection ---

def seleziona_pulsante(btn):
    global pulsante_selezionato
    pulsante_selezionato = btn
    print(f"[DEBUG] Button selected: {btn}")


def deseleziona_pulsante():
    global pulsante_selezionato
    pulsante_selezionato = None


def get_pulsante_selezionato():
    return pulsante_selezionato
