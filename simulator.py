#!/usr/bin/env python3
"""
ConsoleDeck V2 — Arduino Simulator
====================================
Simulates the Arduino over a virtual serial port so you can test
without physical hardware.

Usage:
    1.  In one terminal:   uv run python simulator.py
    2.  Copy the "/dev/ttys..." device path it prints.
    3.  In another terminal:
          CONSOLEDECK_PORT=/dev/ttys... uv run python main.py
        Or GUI mode:
          CONSOLEDECK_PORT=/dev/ttys... uv run python main.py --gui

Controls (in the simulator terminal):
    1-9      →  BUTTON_1 … BUTTON_9
    0        →  BUTTON_10
    [ or ,   →  Encoder turn left  (mode index - 1)
    ] or .   →  Encoder turn right (mode index + 1)
    p        →  Encoder press (MODE_PRESS)
    q        →  Quit
"""

import os
import pty
import sys
import tty
import termios
import threading

# ── virtual pty pair ──────────────────────────────────────────────────────────
master_fd, slave_fd = pty.openpty()
slave_name = os.ttyname(slave_fd)

# ── thread-safe raw-mode print ────────────────────────────────────────────────
_print_lock = threading.Lock()

def rprint(*args, **kwargs):
    """Print with \\r\\n so output is correct in raw terminal mode."""
    text = " ".join(str(a) for a in args)
    with _print_lock:
        sys.stdout.write(text + "\r\n")
        sys.stdout.flush()

def rprint_header():
    rprint("=" * 56)
    rprint("ConsoleDeck Arduino Simulator")
    rprint("=" * 56)
    rprint(f"  Virtual port : {slave_name}")
    rprint()
    rprint("  Start the app in another terminal:")
    rprint(f"    CONSOLEDECK_PORT={slave_name} uv run python main.py")
    rprint(f"    CONSOLEDECK_PORT={slave_name} uv run python main.py --gui")
    rprint()
    rprint("  Controls:")
    rprint("    1-9    →  BUTTON_1 … BUTTON_9")
    rprint("    0      →  BUTTON_10")
    rprint("    [ or , →  Encoder left  (mode - 1)")
    rprint("    ] or . →  Encoder right (mode + 1)")
    rprint("    p      →  Encoder press (MODE_PRESS)")
    rprint("    q      →  Quit")
    rprint("=" * 56)
    rprint()

# ── state ─────────────────────────────────────────────────────────────────────
mode_names: list[str] = ["Default"]
current_mode: int = 0
running = True


def send(message: str):
    """Write a line to master_fd (Python reads it from slave_fd)."""
    data = (message.strip() + "\n").encode()
    os.write(master_fd, data)
    rprint(f"  [SIM → PY]  {message.strip()}")


def show_display():
    """Print a rough ASCII representation of what the OLED would show."""
    rprint()
    rprint("  ┌──────────────────────┐  OLED")
    for i, name in enumerate(mode_names):
        marker = "▶" if i == current_mode else " "
        rprint(f"  │  {marker} {name:<18} │")
    rprint("  └──────────────────────┘")
    rprint()


# ── reader thread: display messages arriving from Python ──────────────────────
def reader():
    global mode_names, current_mode
    buf = b""
    while running:
        try:
            chunk = os.read(master_fd, 256)
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                rprint(f"  [PY → SIM]  {line}")
                if line.startswith("MODES:"):
                    names_str = line[len("MODES:"):]
                    mode_names = [n for n in names_str.split(",") if n]
                    rprint(f"  [SIM] {len(mode_names)} mode(s) received: {mode_names}")
                    show_display()
                elif line.startswith("SET_MODE:"):
                    try:
                        current_mode = int(line.split(":")[1])
                        label = mode_names[current_mode] if mode_names else "?"
                        rprint(f"  [SIM] Active mode → {current_mode} ({label})")
                        show_display()
                    except (ValueError, IndexError):
                        pass
        except OSError:
            break


reader_thread = threading.Thread(target=reader, daemon=True)
reader_thread.start()

# ── keyboard input (raw mode) ─────────────────────────────────────────────────
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)

try:
    tty.setraw(fd)
    rprint_header()

    # Send READY signal like the real Arduino does after boot
    send("READY")

    rprint("Waiting for app to connect…  (press a key once connected)")
    rprint()

    while True:
        ch = sys.stdin.read(1)

        if ch == "q":
            running = False
            rprint()
            rprint("Simulator stopped.")
            break

        elif ch in "123456789":
            send(f"BUTTON_{ch}")

        elif ch == "0":
            send("BUTTON_10")

        elif ch in "[,":
            current_mode = (current_mode - 1) % max(len(mode_names), 1)
            send(f"MODE:{current_mode}")
            show_display()

        elif ch in "].":
            current_mode = (current_mode + 1) % max(len(mode_names), 1)
            send(f"MODE:{current_mode}")
            show_display()

        elif ch == "p":
            send("MODE_PRESS")

        elif ch in ("\x03", "\x04"):   # Ctrl-C / Ctrl-D
            running = False
            rprint()
            rprint("Simulator stopped.")
            break

finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    os.close(master_fd)
    os.close(slave_fd)
