import argparse
import subprocess
from logic import (
    load_config,
    save_config,
    ascolta_seriale,
    seleziona_pulsante,
    get_pulsante_selezionato,
    deseleziona_pulsante,
    get_buttons,
    get_num_buttons,
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
            buttons = get_buttons(config)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    selezionato = get_pulsante_selezionato()
                    click_consumed = False

                    # Click inside URL/shortcut input field
                    if selezionato and gui.input_rect and gui.input_rect.collidepoint(mx, my):
                        gui.input_active = True
                        click_consumed = True
                    else:
                        gui.input_active = False

                    # Click on "Cancel"
                    if selezionato and gui.cancel_button_rect and gui.cancel_button_rect.collidepoint(mx, my):
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = False
                        gui.input_active = False
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
                        current = buttons.get(selezionato, {"type": "none", "value": ""})
                        new_type = gui.temp_config_type if gui.temp_config_type is not None else current.get("type", "none")
                        new_value = gui.temp_config_value if gui.temp_config_value is not None else current.get("value", "")
                        if new_type == "none":
                            new_value = ""
                        buttons[selezionato] = {
                            "type": new_type,
                            "value": new_value,
                        }
                        gui.temp_config_type = None
                        gui.temp_config_value = None
                        gui.save_enabled = False
                        gui.save_clicked = True
                        save_config(config)
                        gui.save_clicked = False

                    # Click on one of the type buttons (LINK, APP, SHORTCUT, NONE)
                    if not click_consumed and selezionato and hasattr(gui, "tipo_button_rects"):
                        for nome, rect in gui.tipo_button_rects.items():
                            if rect.collidepoint(mx, my):
                                tipo = nome.lower()
                                gui.temp_config_type = tipo

                                if tipo == "none":
                                    gui.temp_config_value = ""
                                else:
                                    if gui.temp_config_value is None:
                                        gui.temp_config_value = buttons[selezionato].get("value", "")

                                gui.save_enabled = gui.is_dirty(selezionato, config)
                                click_consumed = True
                                break

                    # Click on "Browse" (for app type)
                    current_type = gui.temp_config_type or (buttons.get(selezionato, {}).get("type") if selezionato else None)
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

                # Text input for URL / shortcut fields
                elif event.type == pygame.KEYDOWN and gui.input_active:
                    selezionato = get_pulsante_selezionato()
                    if not selezionato:
                        gui.input_active = False
                        continue

                    active_type = gui.temp_config_type if gui.temp_config_type is not None else buttons[selezionato].get("type", "none")
                    # Text input is active for both "link" and "shortcut" types
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Launch the configuration GUI")
    args = parser.parse_args()
    main(args.gui)
