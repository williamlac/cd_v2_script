import argparse
import os
import sys
import subprocess
from logic import (
    load_config,
    save_config,
    ascolta_seriale,
    seleziona_pulsante,
    get_pulsante_selezionato,
    deseleziona_pulsante,
    get_current_buttons,
    get_num_buttons,
    get_modes,
    set_current_mode_index,
    MAX_MODE_NAME_LEN,
)
from gui import init_pygame, disegna_pulsanti, trova_pulsante_click
import pygame
import pyperclip

import gui

# macOS uses Cmd for copy/paste shortcuts
MOD_KEY = pygame.KMOD_META | pygame.KMOD_GUI


def main(gui_mode):
    config = load_config()

    if gui_mode:
        num_buttons = get_num_buttons(config)
        init_pygame(num_buttons)
        pygame.key.set_repeat(300, 30)

        running = True
        while running:
            selezionato = get_pulsante_selezionato()
            disegna_pulsanti(config, selezionato)
            buttons = get_current_buttons(config)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    selezionato = get_pulsante_selezionato()
                    click_consumed = False

                    # --- Mode bar clicks ---

                    # Left arrow (<) — previous mode
                    if not click_consumed and gui.mode_left_rect and gui.mode_left_rect.collidepoint(mx, my):
                        modes = get_modes(config)
                        if len(modes) > 1:
                            idx = config.get("current_mode_index", 0)
                            new_idx = (idx - 1) % len(modes)
                            set_current_mode_index(config, new_idx)
                            save_config(config)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False
                        deseleziona_pulsante()
                        click_consumed = True

                    # Right arrow (>) — next mode
                    if not click_consumed and gui.mode_right_rect and gui.mode_right_rect.collidepoint(mx, my):
                        modes = get_modes(config)
                        if len(modes) > 1:
                            idx = config.get("current_mode_index", 0)
                            new_idx = (idx + 1) % len(modes)
                            set_current_mode_index(config, new_idx)
                            save_config(config)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False
                        deseleziona_pulsante()
                        click_consumed = True

                    # Add mode (+)
                    if not click_consumed and gui.mode_add_rect and gui.mode_add_rect.collidepoint(mx, my):
                        modes = get_modes(config)
                        if len(modes) < 10:
                            new_mode = {
                                "name": f"Mode {len(modes) + 1}",
                                "buttons": {},
                            }
                            num_b = get_num_buttons(config)
                            for i in range(1, num_b + 1):
                                new_mode["buttons"][f"BUTTON_{i}"] = {"type": "none", "value": ""}
                            modes.append(new_mode)
                            set_current_mode_index(config, len(modes) - 1)
                            save_config(config)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False
                        deseleziona_pulsante()
                        click_consumed = True

                    # Delete mode (-)
                    if not click_consumed and gui.mode_delete_rect and gui.mode_delete_rect.collidepoint(mx, my):
                        modes = get_modes(config)
                        if len(modes) > 1:
                            idx = config.get("current_mode_index", 0)
                            modes.pop(idx)
                            set_current_mode_index(config, max(0, idx - 1))
                            save_config(config)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False
                        deseleziona_pulsante()
                        click_consumed = True

                    # Mode name click — enter rename mode
                    if not click_consumed and gui.mode_name_rect and gui.mode_name_rect.collidepoint(mx, my):
                        if not gui.mode_name_editing:
                            gui.mode_name_editing = True
                            modes = get_modes(config)
                            idx = config.get("current_mode_index", 0)
                            gui.temp_mode_name = modes[idx]["name"]
                            gui.input_active = False  # deactivate button config input
                        click_consumed = True

                    # --- Button config panel clicks ---

                    # Click inside URL/shortcut input field
                    if not click_consumed and selezionato and gui.input_rect and gui.input_rect.collidepoint(mx, my):
                        gui.input_active = True
                        gui.mode_name_editing = False
                        click_consumed = True
                    elif not click_consumed:
                        if not (gui.mode_name_editing and gui.mode_name_input_rect and gui.mode_name_input_rect.collidepoint(mx, my)):
                            gui.input_active = False

                    # Click on "Cancel"
                    if not click_consumed and selezionato and gui.cancel_button_rect and gui.cancel_button_rect.collidepoint(mx, my):
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False
                        deseleziona_pulsante()
                        click_consumed = True

                    # Click on "Save"
                    if (
                        not click_consumed
                        and selezionato
                        and hasattr(gui, "save_button_rect")
                        and gui.save_button_rect
                        and gui.save_button_rect.collidepoint(mx, my)
                    ):
                        modes = get_modes(config)
                        idx = config.get("current_mode_index", 0)
                        mode_buttons = modes[idx]["buttons"]
                        current = mode_buttons.get(selezionato, {"type": "none", "value": ""})
                        new_type = gui.temp_config_type if gui.temp_config_type is not None else current.get("type", "none")
                        new_value = gui.temp_config_value if gui.temp_config_value is not None else current.get("value", "")
                        if new_type == "none" or new_type in ("volume_up", "volume_down", "mute", "media"):
                            new_value = ""
                        mode_buttons[selezionato] = {
                            "type": new_type,
                            "value": new_value,
                        }
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = True
                        save_config(config)
                        gui.save_clicked = False
                        click_consumed = True

                    # Click on one of the type buttons (LINK, APP, SHORTCUT, NONE, VOL+, etc.)
                    if not click_consumed and selezionato and hasattr(gui, "tipo_button_rects"):
                        for nome, rect in gui.tipo_button_rects.items():
                            if rect.collidepoint(mx, my):
                                tipo = nome.lower()
                                gui.temp_config_type = tipo

                                if tipo in ("none", "volume_up", "volume_down", "mute", "media"):
                                    gui.temp_config_value = ""
                                else:
                                    if gui.temp_config_value is None:
                                        mode_buttons = get_current_buttons(config)
                                        gui.temp_config_value = mode_buttons.get(selezionato, {}).get("value", "")

                                gui.save_enabled = gui.is_dirty(selezionato, config)
                                gui.mode_name_editing = False
                                click_consumed = True
                                break

                    # Click on "Browse" (for app type)
                    current_type = gui.temp_config_type or (get_current_buttons(config).get(selezionato, {}).get("type") if selezionato else None)
                    if (
                        not click_consumed
                        and selezionato
                        and current_type == "exe"
                        and hasattr(gui, "browse_button_rect")
                        and gui.browse_button_rect
                        and gui.browse_button_rect.collidepoint(mx, my)
                    ):
                        # Use native macOS file picker via osascript
                        result = subprocess.run(
                            [
                                "osascript",
                                "-e",
                                'POSIX path of (choose file with prompt "Select Application or Executable")',
                            ],
                            capture_output=True,
                            text=True,
                        )
                        path = result.stdout.strip() if result.returncode == 0 else ""
                        if path:
                            gui.temp_config_value = path
                            gui.save_enabled = gui.is_dirty(selezionato, config)
                        click_consumed = True

                    if click_consumed:
                        continue

                    # Click on one of the buttons 1-N
                    btn = trova_pulsante_click(mx, my, num_buttons)
                    if btn:
                        seleziona_pulsante(btn)
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
                        gui.mode_name_editing = False

                # Keyboard input for mode name editing
                elif event.type == pygame.KEYDOWN and gui.mode_name_editing:
                    if event.key == pygame.K_RETURN:
                        # Commit rename
                        modes = get_modes(config)
                        idx = config.get("current_mode_index", 0)
                        new_name = (gui.temp_mode_name or "").strip()
                        if new_name and "," not in new_name:
                            modes[idx]["name"] = new_name[:MAX_MODE_NAME_LEN]
                        gui.mode_name_editing = False
                        gui.temp_mode_name = None
                        save_config(config)
                    elif event.key == pygame.K_ESCAPE:
                        gui.mode_name_editing = False
                        gui.temp_mode_name = None
                    elif event.key == pygame.K_BACKSPACE:
                        gui.temp_mode_name = (gui.temp_mode_name or "")[:-1]
                    elif event.key == pygame.K_v and (pygame.key.get_mods() & MOD_KEY):
                        clipboard_text = pyperclip.paste()
                        if clipboard_text:
                            text = (gui.temp_mode_name or "") + clipboard_text
                            gui.temp_mode_name = text[:MAX_MODE_NAME_LEN]
                    else:
                        char = event.unicode
                        if char.isprintable() and char != ",":
                            text = (gui.temp_mode_name or "") + char
                            gui.temp_mode_name = text[:MAX_MODE_NAME_LEN]

                # Text input for URL / shortcut fields
                elif event.type == pygame.KEYDOWN and gui.input_active:
                    selezionato = get_pulsante_selezionato()
                    if not selezionato:
                        gui.input_active = False
                        continue

                    active_type = gui.temp_config_type if gui.temp_config_type is not None else get_current_buttons(config).get(selezionato, {}).get("type", "none")
                    # Text input is active for "link" and "shortcut" types
                    if active_type not in ("link", "shortcut"):
                        gui.input_active = False
                        continue

                    if event.key == pygame.K_BACKSPACE:
                        gui.temp_config_value = (gui.temp_config_value or "")[:-1]
                    elif event.key == pygame.K_v and (pygame.key.get_mods() & MOD_KEY):
                        # Cmd+V: paste from clipboard
                        clipboard_text = pyperclip.paste()
                        if clipboard_text:
                            gui.temp_config_value = (gui.temp_config_value or "") + clipboard_text
                    elif event.key == pygame.K_a and (pygame.key.get_mods() & MOD_KEY):
                        # Cmd+A: select all (symbolic)
                        pass
                    elif event.key == pygame.K_c and (pygame.key.get_mods() & MOD_KEY):
                        # Cmd+C: copy
                        if gui.temp_config_value:
                            pyperclip.copy(gui.temp_config_value)
                    elif event.key == pygame.K_x and (pygame.key.get_mods() & MOD_KEY):
                        # Cmd+X: cut
                        if gui.temp_config_value:
                            pyperclip.copy(gui.temp_config_value)
                            gui.temp_config_value = ""
                            gui.save_enabled = gui.is_dirty(selezionato, config)
                    else:
                        char = event.unicode
                        if char.isprintable():
                            gui.temp_config_value = (gui.temp_config_value or "") + char

                    gui.save_enabled = gui.is_dirty(selezionato, config)

        pygame.quit()
    else:
        ascolta_seriale(config)


class _Tee:
    """Write to multiple streams simultaneously."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()


if __name__ == "__main__":
    # Clear and open log file; tee stdout+stderr to it for this session
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "consoledeck.log")
    _log_fh = open(_log_path, "w", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, _log_fh)
    sys.stderr = _Tee(sys.__stderr__, _log_fh)

    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Launch the configuration GUI")
    args = parser.parse_args()
    main(args.gui)
