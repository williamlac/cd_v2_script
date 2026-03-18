import pygame
import math
from logic import get_num_buttons

# Constants
FONT = None
SMALL_FONT = None
SCREEN = None

BTN_SIZE = 100
SPACING_X = 140
SPACING_Y = 120
MARGIN_Y = 60  # shifted down to make room for mode bar
SCREEN_WIDTH = 640
COLS = 3

# Global UI state — button config panel
cancel_button_rect = None
browse_button_rect = None
save_button_rect = None
tipo_button_rects = {}

temp_config_type = None
temp_config_value = None

save_enabled = False
save_clicked = False

input_active = False
input_rect = None

# Global UI state — mode selector bar
mode_left_rect = None
mode_right_rect = None
mode_add_rect = None
mode_delete_rect = None
mode_name_rect = None
mode_name_editing = False
temp_mode_name = None
mode_name_input_rect = None

# Action type definitions: (internal_key, display_label)
# Row 1: original types. Row 2: hardware replacement types.
ACTION_TYPES = [
    ("link", "LINK"),
    ("exe", "APP"),
    ("shortcut", "SHORTCUT"),
    ("none", "NONE"),
    ("volume_up", "VOL+"),
    ("volume_down", "VOL-"),
    ("mute", "MUTE"),
    ("media", "MEDIA"),
    ("script", "SCRIPT"),
]

# Types that need a text input field
INPUT_TYPES = {"link", "shortcut", "script"}

# Types that need a browse button
BROWSE_TYPES = {"exe", "script"}


def _compute_screen_height(num_buttons):
    """Compute screen height based on number of buttons."""
    rows = math.ceil(num_buttons / COLS)
    mode_bar_height = 40
    grid_height = mode_bar_height + MARGIN_Y + rows * SPACING_Y + 5
    config_panel_height = 300  # space for config panel below grid (two rows of types)
    return grid_height + config_panel_height


def init_pygame(num_buttons=9):
    global FONT, SMALL_FONT, SCREEN, SCREEN_WIDTH
    pygame.init()
    FONT = pygame.font.SysFont(None, 24)
    SMALL_FONT = pygame.font.SysFont(None, 16)
    screen_height = _compute_screen_height(num_buttons)
    SCREEN = pygame.display.set_mode((SCREEN_WIDTH, screen_height))
    pygame.display.set_caption("ConsoleDeck V2")


def disegna_mode_selector(config):
    """Draw the mode selector bar at the top of the screen."""
    global mode_left_rect, mode_right_rect, mode_add_rect, mode_delete_rect
    global mode_name_rect, mode_name_input_rect

    modes = config.get("modes", [])
    current_idx = config.get("current_mode_index", 0)
    current_name = modes[current_idx]["name"] if modes else "Default"

    bar_y = 8
    bar_height = 30

    small_font = pygame.font.SysFont(None, 16)

    # Delete button (-)
    mode_delete_rect = pygame.Rect(20, bar_y, 30, bar_height)
    color = (120, 60, 60) if len(modes) > 1 else (60, 60, 60)
    pygame.draw.rect(SCREEN, color, mode_delete_rect, border_radius=5)
    minus_text = FONT.render("-", True, (255, 255, 255))
    SCREEN.blit(minus_text, minus_text.get_rect(center=mode_delete_rect.center))

    # Left arrow (<)
    mode_left_rect = pygame.Rect(70, bar_y, 30, bar_height)
    pygame.draw.rect(SCREEN, (80, 80, 80), mode_left_rect, border_radius=5)
    arrow_l = FONT.render("<", True, (255, 255, 255))
    SCREEN.blit(arrow_l, arrow_l.get_rect(center=mode_left_rect.center))

    # Mode name (centered) — clickable to rename
    if mode_name_editing:
        display_name = temp_mode_name if temp_mode_name is not None else current_name
        # Draw editable text field
        mode_name_input_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, bar_y, 200, bar_height)
        pygame.draw.rect(SCREEN, (255, 255, 255), mode_name_input_rect, border_radius=4)
        name_text = FONT.render(display_name, True, (0, 0, 0))
        SCREEN.blit(name_text, name_text.get_rect(center=mode_name_input_rect.center))
        mode_name_rect = mode_name_input_rect
    else:
        mode_name_input_rect = None
        name_text = FONT.render(current_name, True, (200, 120, 40))
        mode_name_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, bar_y, 200, bar_height)
        SCREEN.blit(name_text, name_text.get_rect(center=mode_name_rect.center))

    # Right arrow (>)
    mode_right_rect = pygame.Rect(SCREEN_WIDTH - 100, bar_y, 30, bar_height)
    pygame.draw.rect(SCREEN, (80, 80, 80), mode_right_rect, border_radius=5)
    arrow_r = FONT.render(">", True, (255, 255, 255))
    SCREEN.blit(arrow_r, arrow_r.get_rect(center=mode_right_rect.center))

    # Add button (+)
    mode_add_rect = pygame.Rect(SCREEN_WIDTH - 50, bar_y, 30, bar_height)
    pygame.draw.rect(SCREEN, (60, 120, 60), mode_add_rect, border_radius=5)
    plus_text = FONT.render("+", True, (255, 255, 255))
    SCREEN.blit(plus_text, plus_text.get_rect(center=mode_add_rect.center))

    # Mode indicator: "1/3"
    indicator = small_font.render(
        f"{current_idx + 1}/{len(modes)}", True, (150, 150, 150)
    )
    SCREEN.blit(
        indicator,
        (SCREEN_WIDTH // 2 - indicator.get_width() // 2, bar_y + bar_height + 2),
    )


def disegna_pulsanti(config, selezionato=None):
    num_buttons = get_num_buttons(config)
    modes = config.get("modes", [])
    current_idx = config.get("current_mode_index", 0)
    buttons = modes[current_idx]["buttons"] if modes else {}
    rows = math.ceil(num_buttons / COLS)

    SCREEN.fill((30, 30, 30))

    # Draw mode selector bar at top
    disegna_mode_selector(config)

    total_width = COLS * BTN_SIZE + (COLS - 1) * (SPACING_X - BTN_SIZE)
    start_x = (SCREEN_WIDTH - total_width) // 2

    for i in range(num_buttons):
        key = f"BUTTON_{i + 1}"
        col = i % COLS
        row = i // COLS
        x = start_x + col * SPACING_X
        y = MARGIN_Y + row * SPACING_Y

        # Button background
        pygame.draw.rect(SCREEN, (50, 50, 50), (x, y, BTN_SIZE, BTN_SIZE), border_radius=8)

        # Border
        if selezionato == key:
            border_color = (200, 120, 40)
        else:
            border_color = (200, 200, 200)

        pygame.draw.rect(SCREEN, border_color, (x, y, BTN_SIZE, BTN_SIZE), width=3, border_radius=8)

        # Button number
        num_text = FONT.render(str(i + 1), True, (255, 255, 255))
        num_x = x + (BTN_SIZE - num_text.get_width()) // 2
        num_y = y + (BTN_SIZE - num_text.get_height()) // 2
        SCREEN.blit(num_text, (num_x, num_y))

    # Separator line below grid
    linea_y = MARGIN_Y + rows * SPACING_Y + 5
    pygame.draw.line(SCREEN, (180, 180, 180), (start_x, linea_y), (start_x + total_width, linea_y), 2)

    font_18 = pygame.font.SysFont(None, 18)

    if selezionato:
        btn_num = selezionato.split("_")[-1]
        testo = f"Program button {btn_num}"
    else:
        testo = "Click on a button to program it"

    testo_render = font_18.render(testo, True, (255, 255, 255))
    area_testo_y = linea_y + 10
    area_testo_height = BTN_SIZE

    testo_x = (SCREEN_WIDTH - testo_render.get_width()) // 2
    testo_y = area_testo_y + (area_testo_height - testo_render.get_height()) // 2

    SCREEN.blit(testo_render, (testo_x, testo_y))

    if selezionato:
        disegna_configuratore_avanzato(selezionato, config)

    pygame.display.flip()


def disegna_configuratore_avanzato(selezionato, config):
    global tipo_button_rects, cancel_button_rect, input_rect, browse_button_rect

    modes = config.get("modes", [])
    current_idx = config.get("current_mode_index", 0)
    buttons = modes[current_idx]["buttons"] if modes else {}
    num_buttons = get_num_buttons(config)
    rows = math.ceil(num_buttons / COLS)

    small_font = pygame.font.SysFont(None, 16)

    data = buttons.get(selezionato, {"type": "none", "value": ""})

    global temp_config_type, temp_config_value

    tipo = temp_config_type if temp_config_type is not None else data.get("type", "none")
    valore = temp_config_value if temp_config_value is not None else data.get("value", "")

    # Dynamic base_y based on grid height
    base_y = MARGIN_Y + rows * SPACING_Y + 5 + 10 + BTN_SIZE + 10

    # Two rows of action type buttons
    btn_width = 80
    btn_height = 35
    spazio = 10
    types_per_row = 4

    tipo_button_rects = {}
    input_rect = None
    browse_button_rect = None

    for row_num in range(2):
        row_types = ACTION_TYPES[row_num * types_per_row : (row_num + 1) * types_per_row]
        total_width = len(row_types) * btn_width + (len(row_types) - 1) * spazio
        start_x = (SCREEN_WIDTH - total_width) // 2

        for i, (key, label) in enumerate(row_types):
            x = start_x + i * (btn_width + spazio)
            y = base_y + row_num * (btn_height + 8)
            attivo = (key == tipo)
            colore = (200, 120, 40) if attivo else (80, 80, 80)

            rect = pygame.Rect(x, y, btn_width, btn_height)
            tipo_button_rects[key.upper()] = rect

            pygame.draw.rect(SCREEN, colore, rect, border_radius=6)
            testo = small_font.render(label, True, (255, 255, 255))
            SCREEN.blit(testo, testo.get_rect(center=rect.center))

    base_y += 2 * (btn_height + 8) + 10

    if tipo in INPUT_TYPES:
        if tipo == "link":
            label_text = "ENTER URL:"
        elif tipo == "shortcut":
            label_text = "ENTER SHORTCUT (e.g. cmd+shift+4):"
        else:
            label_text = "ENTER VALUE:"

        label = small_font.render(label_text, True, (200, 200, 200))
        SCREEN.blit(label, (50, base_y))

        base_y += label.get_height() + 5

        input_rect = pygame.Rect(50, base_y, 540, 30)
        pygame.draw.rect(SCREEN, (255, 255, 255), input_rect, border_radius=4)

        testo_input = valore if valore else ""
        render_text = small_font.render(testo_input, True, (0, 0, 0))
        SCREEN.blit(render_text, (input_rect.x + 5, input_rect.y + 7))

        base_y += 40

    elif tipo in BROWSE_TYPES:
        label = small_font.render("SELECT APPLICATION:", True, (200, 200, 200))
        SCREEN.blit(label, (50, base_y))

        base_y += label.get_height() + 5
        browse_rect = pygame.Rect(50, base_y, 100, 30)
        pygame.draw.rect(SCREEN, (200, 120, 40), browse_rect, border_radius=5)
        btn_text = small_font.render("BROWSE", True, (255, 255, 255))
        SCREEN.blit(btn_text, btn_text.get_rect(center=browse_rect.center))
        browse_button_rect = browse_rect

        # Show selected path
        if valore:
            path_text = small_font.render(valore, True, (180, 180, 180))
            SCREEN.blit(path_text, (160, base_y + 7))

        base_y += 40

    else:
        # none, volume_up, volume_down, mute, media — no input needed
        base_y += 10

    # Cancel and Save buttons
    button_y = base_y + 20
    total_button_width = 80 + 20 + 80
    start_x = (SCREEN_WIDTH - total_button_width) // 2

    cancel_text = small_font.render("Cancel", True, (200, 120, 40))
    cancel_rect = cancel_text.get_rect()
    SCREEN.blit(cancel_text, (start_x, button_y + (30 - cancel_rect.height) // 2))
    cancel_button_rect = pygame.Rect(start_x, button_y, 60, 30)

    save_rect = pygame.Rect(start_x + 100, button_y, 80, 30)

    if save_clicked:
        colore_save = (200, 120, 40)
    elif save_enabled:
        colore_save = (200, 120, 40)
    else:
        colore_save = (100, 100, 100)

    pygame.draw.rect(SCREEN, colore_save, save_rect, border_radius=5)

    save_text = small_font.render("Save", True, (255, 255, 255))
    text_rect = save_text.get_rect(center=save_rect.center)
    SCREEN.blit(save_text, text_rect)

    global save_button_rect
    save_button_rect = save_rect


def is_dirty(selezionato, config):
    global temp_config_type, temp_config_value
    if not selezionato:
        return False

    modes = config.get("modes", [])
    current_idx = config.get("current_mode_index", 0)
    buttons = modes[current_idx]["buttons"] if modes else {}
    current = buttons.get(selezionato, {"type": "none", "value": ""})
    tipo = temp_config_type if temp_config_type is not None else current["type"]
    valore = temp_config_value if temp_config_value is not None else current["value"]

    return tipo != current["type"] or valore != current["value"]


def trova_pulsante_click(mx, my, num_buttons=9):
    total_width = COLS * BTN_SIZE + (COLS - 1) * (SPACING_X - BTN_SIZE)
    start_x = (SCREEN_WIDTH - total_width) // 2

    for i in range(num_buttons):
        col = i % COLS
        row = i // COLS
        x = start_x + col * SPACING_X
        y = MARGIN_Y + row * SPACING_Y
        if x <= mx <= x + BTN_SIZE and y <= my <= y + BTN_SIZE:
            return f"BUTTON_{i + 1}"
    return None
