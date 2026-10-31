/*
 * The glue of lcd2004_pcf8574, made by tools/boards_gen.py from catalog/modules/lcd2004_pcf8574/module.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * A module: not a board but a device the chosen board's bus carries; it gives the function of
 * its kind, and the board's glue leaves that one out (CONFIG_BOARD_MODULE_CHARACTER_DISPLAY).
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_character.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* 2004 character LCD on a PCF8574 backpack: A 20x4 HD44780 on the common I2C backpack (P0 RS, P1 RW, P2 E, P3 backlight, P4-P7 D4-D7): not a board of its own, a display any board's I2C bus can carry. */

/* The character display: a 20x4 hd44780 on i2c.i2c0. */
static lcd_bus_hd44780_t *character_bus(void)
{
    i2c_master_bus_handle_t bus = board_glue_i2c();
    return bus ? lcd_bus_pcf8574_i2c_create_on_bus(bus, 0x27, 0) : NULL;
}

static const struct board_character_panel character_panel = {.geometry = HD44780_GEOMETRY_20X4, .cols = 20, .rows = 4, .bus = character_bus};

bool board_character_display_init(struct board_character_display *out)
{
    return board_glue_character_init(&character_panel, out);
}

