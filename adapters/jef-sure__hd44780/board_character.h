#pragma once

/* A character display: the glue gives the geometry and the call that makes its bus, on I2C or on GPIO. */
#include "board_glue.h"
#include "boards_hd44780.h"

struct board_character_panel {
    hd44780_geometry_t geometry;
    int                cols, rows;
    int                i2c_port; /* the port of its I2C bus; -1 for one on GPIO */
    lcd_bus_hd44780_t *(*on_i2c)(i2c_master_bus_handle_t i2c);
    lcd_bus_hd44780_t *(*on_gpio)(void);
};
extern const struct board_character_panel board_character_panel;
