#pragma once

/* A character display: the glue gives the geometry and the call that makes its bus. */
#include "board_glue.h"
#include "boards_hd44780.h"

struct board_character_panel {
    hd44780_geometry_t geometry;
    int                cols, rows;
    lcd_bus_hd44780_t *(*bus)(void);
};

bool board_glue_character_init(const struct board_character_panel *panel, struct board_character_display *out);
