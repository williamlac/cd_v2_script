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

# Mute state (used by _handle_mute action)
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


PORTA_ARDUINO = os.environ.get("CONSOLEDECK_PORT") or detect_arduino_port()
if PORTA_ARDUINO is None:
    print("[WARNING] No Arduino detected. Serial features will not work.")
else:
    print(f"[DEBUG] Using serial port: {PORTA_ARDUINO}")


# --- Config ---

DEFAULT_NUM_BUTTONS = 9
MAX_MODES = 10
MAX_MODE_NAME_LEN = 12


def _default_mode(num_buttons):
    """Create a default mode with all-none buttons."""
    buttons = {}
    for i in range(1, num_buttons + 1):
        buttons[f"BUTTON_{i}"] = {"type": "none", "value": ""}
    return {"name": "Default", "buttons": buttons}


def _default_config():
    """Create a fresh default config."""
    config = {
        "settings": {"num_buttons": DEFAULT_NUM_BUTTONS},
        "modes": [],
        "current_mode_index": 0,
    }
    mode = _default_mode(DEFAULT_NUM_BUTTONS)
    mode["buttons"]["BUTTON_1"] = {"type": "link", "value": "https://www.youtube.com"}
    config["modes"].append(mode)
    return config


def load_config():
    """Load config from disk. Supports old flat, structured, and new modes format."""
    print(f"[DEBUG] Loading config from: {CONFIG_FILE}")
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            raw = json.load(f)

        if "modes" in raw:
            # New modes format — use directly
            config = raw
        elif "settings" in raw and "buttons" in raw:
            # Current structured format — wrap buttons into single mode
            config = {
                "settings": raw["settings"],
                "modes": [{"name": "Default", "buttons": raw["buttons"]}],
                "current_mode_index": 0,
            }
        else:
            # Old flat format (BUTTON_1..BUTTON_9 at top level) — migrate
            num = len([k for k in raw if k.startswith("BUTTON_")])
            buttons = {k: v for k, v in raw.items() if k.startswith("BUTTON_")}
            config = {
                "settings": {"num_buttons": max(num, DEFAULT_NUM_BUTTONS)},
                "modes": [{"name": "Default", "buttons": buttons}],
                "current_mode_index": 0,
            }

        # Ensure settings exists
        if "settings" not in config:
            config["settings"] = {"num_buttons": DEFAULT_NUM_BUTTONS}

        # Ensure at least one mode
        if not config.get("modes"):
            num_buttons = config["settings"].get("num_buttons", DEFAULT_NUM_BUTTONS)
            config["modes"] = [_default_mode(num_buttons)]

        # Ensure current_mode_index exists and is valid
        if "current_mode_index" not in config:
            config["current_mode_index"] = 0

        # Validate all modes have all buttons
        num_buttons = config["settings"].get("num_buttons", DEFAULT_NUM_BUTTONS)
        for mode in config["modes"]:
            if "name" not in mode:
                mode["name"] = "Default"
            if "buttons" not in mode:
                mode["buttons"] = {}
            for i in range(1, num_buttons + 1):
                key = f"BUTTON_{i}"
                if key not in mode["buttons"]:
                    mode["buttons"][key] = {"type": "none", "value": ""}

        # Clamp mode index
        idx = config["current_mode_index"]
        config["current_mode_index"] = max(0, min(idx, len(config["modes"]) - 1))

        print("[DEBUG] Config loaded:", json.dumps(config, indent=2))
        return config
    else:
        print("[DEBUG] Config file not found, creating default config.")
        return _default_config()


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# --- Mode helpers ---

def get_modes(config):
    """Get the list of modes."""
    return config.get("modes", [])


def get_current_mode(config):
    """Get the current mode dict from config."""
    modes = config.get("modes", [])
    idx = config.get("current_mode_index", 0)
    if not modes:
        return {"name": "Default", "buttons": {}}
    idx = max(0, min(idx, len(modes) - 1))
    return modes[idx]


def get_current_buttons(config):
    """Get the buttons dict for the currently active mode."""
    mode = get_current_mode(config)
    return mode.get("buttons", {})


def get_num_buttons(config):
    """Get the configured number of buttons."""
    return config.get("settings", {}).get("num_buttons", DEFAULT_NUM_BUTTONS)


def set_current_mode_index(config, index):
    """Set the active mode index."""
    modes = config.get("modes", [])
    if modes:
        config["current_mode_index"] = max(0, min(index, len(modes) - 1))


def build_app_triggers(config):
    """Return {app_name_lowercase: mode_index} for modes that have app_trigger set."""
    triggers = {}
    for i, mode in enumerate(config.get("modes", [])):
        trigger = mode.get("app_trigger", "").strip()
        if trigger:
            triggers[trigger.lower()] = i
    return triggers


def get_frontmost_app():
    """Return the name of the frontmost macOS application, or '' on failure."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def send_modes_to_arduino(ser, config):
    """Send the mode name list to Arduino over serial."""
    modes = config.get("modes", [])
    names = [m["name"] for m in modes]
    message = "MODES:" + ",".join(names) + "\n"
    ser.write(message.encode("utf-8"))
    ser.flush()
    print(f"[DEBUG] Sent to Arduino: {message.strip()}")


def send_set_mode_to_arduino(ser, index):
    """Tell Arduino to display a specific mode."""
    message = f"SET_MODE:{index}\n"
    ser.write(message.encode("utf-8"))
    ser.flush()
    print(f"[DEBUG] Sent to Arduino: {message.strip()}")


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


def _handle_volume_up(value):
    """Increase system volume by ~6%."""
    script = (
        "set curVol to output volume of (get volume settings)\n"
        "set newVol to curVol + 6\n"
        "if newVol > 100 then set newVol to 100\n"
        "set volume output volume newVol"
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)
    print("[DEBUG] Volume up")


def _handle_volume_down(value):
    """Decrease system volume by ~6%."""
    script = (
        "set curVol to output volume of (get volume settings)\n"
        "set newVol to curVol - 6\n"
        "if newVol < 0 then set newVol to 0\n"
        "set volume output volume newVol"
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)
    print("[DEBUG] Volume down")


def _handle_mute(value):
    """Toggle mute with save/restore volume."""
    global is_muted, _saved_volume
    if not is_muted:
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
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {_saved_volume}"],
            capture_output=True,
        )
    is_muted = not is_muted
    print(f"[DEBUG] Mute toggled -> {'ON' if is_muted else 'OFF'}")


def _handle_media(value):
    """Play/pause media — tries Spotify first, then Music."""
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


def _handle_screenshot(value):
    """Interactive area screenshot, copied to clipboard (like cmd+ctrl+shift+4)."""
    subprocess.Popen(["screencapture", "-i", "-c"])
    print("[DEBUG] Screenshot interactive mode started -> clipboard")


def _handle_none(value):
    print("[DEBUG] No action defined")


# Action type registry — add new types here
ACTION_HANDLERS = {
    "link": _handle_link,
    "exe": _handle_app,
    "shortcut": _handle_shortcut,
    "screenshot": _handle_screenshot,
    "volume_up": _handle_volume_up,
    "volume_down": _handle_volume_down,
    "mute": _handle_mute,
    "media": _handle_media,
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

    try:
        with serial.Serial(PORTA_ARDUINO, BAUDRATE, timeout=1) as ser:
            print(f"Connected to {PORTA_ARDUINO}")

            # Wait for Arduino to finish booting and send READY
            print("[DEBUG] Waiting for Arduino READY signal...")
            ready = False
            for _ in range(15):  # up to 15 seconds
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    print(f"[DEBUG] Arduino boot: {line}")
                if line == "READY":
                    ready = True
                    break
            if not ready:
                print("[WARNING] No READY signal received, sending config anyway")

            # Send mode list and current mode to Arduino
            send_modes_to_arduino(ser, config)
            idx = config.get("current_mode_index", 0)
            send_set_mode_to_arduino(ser, idx)

            last_config_mtime = os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else 0
            app_triggers = build_app_triggers(config)
            last_frontmost_app = ""
            auto_switched = False
            pre_auto_mode_idx = config.get("current_mode_index", 0)
            last_app_check = 0.0

            while True:
                # Hot-reload: resend config if file changed on disk
                try:
                    mtime = os.path.getmtime(CONFIG_FILE)
                    if mtime != last_config_mtime:
                        last_config_mtime = mtime
                        new_config = load_config()
                        config.clear()
                        config.update(new_config)
                        app_triggers = build_app_triggers(config)
                        print("[DEBUG] Config changed on disk — reloading")
                        send_modes_to_arduino(ser, config)
                        send_set_mode_to_arduino(ser, config.get("current_mode_index", 0))
                except (OSError, json.JSONDecodeError) as e:
                    print(f"[WARNING] Config reload skipped: {e}")

                # App trigger: auto-switch mode based on frontmost app (check once per second)
                now = time.time()
                if now - last_app_check >= 1.0:
                    last_app_check = now
                    frontmost = get_frontmost_app()
                    if frontmost != last_frontmost_app:
                        last_frontmost_app = frontmost
                        fl = frontmost.lower()
                        triggered_idx = next(
                            (idx for trigger, idx in app_triggers.items() if trigger in fl),
                            None,
                        )
                        if triggered_idx is not None and not auto_switched:
                            pre_auto_mode_idx = config.get("current_mode_index", 0)
                            auto_switched = True
                            set_current_mode_index(config, triggered_idx)
                            send_set_mode_to_arduino(ser, triggered_idx)
                            print(f"[DEBUG] App trigger: '{frontmost}' → mode {triggered_idx}")
                        elif triggered_idx is None and auto_switched:
                            auto_switched = False
                            set_current_mode_index(config, pre_auto_mode_idx)
                            send_set_mode_to_arduino(ser, pre_auto_mode_idx)
                            print(f"[DEBUG] App trigger: left app → restored mode {pre_auto_mode_idx}")

                linea = ser.readline().decode("utf-8").strip()
                if not linea:
                    continue

                print("Received:", linea)

                if linea.startswith("MODE:"):
                    # Encoder turned — switch mode
                    try:
                        new_index = int(linea.split(":")[1])
                        set_current_mode_index(config, new_index)
                        save_config(config)
                        mode_name = get_current_mode(config)["name"]
                        print(f"[DEBUG] Mode switched to: {mode_name}")
                    except (ValueError, IndexError):
                        print(f"[ERROR] Invalid mode message: {linea}")

                elif linea == "MODE_PRESS":
                    # Encoder press — no-op for now
                    print("[DEBUG] Encoder press (MODE_PRESS)")

                elif linea.startswith("BUTTON_"):
                    buttons = get_current_buttons(config)
                    if linea in buttons:
                        esegui_azione(buttons[linea])
                    else:
                        mode_name = get_current_mode(config)["name"]
                        print(f"[WARNING] {linea} not configured in mode '{mode_name}'")

    except Exception as e:
        print(f"[ERROR] Serial port: {e}")
        time.sleep(5)
        ascolta_seriale(config)


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
