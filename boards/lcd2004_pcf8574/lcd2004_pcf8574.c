/*
 * The glue of lcd2004_pcf8574, made by tools/boards_gen.py from catalog/modules/lcd2004_pcf8574/module.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * A module: not a board but a device the chosen board's bus carries. It gives the table of its
 * kind; the adapter of its library reads it, and the function of src/ that returns false is left out.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_character.h"

/* 2004 LCD on a PCF8574: A 20x4 character LCD sold with a PCF8574 backpack soldered on: I2C on four contacts, a trimmer for the contrast, a jumper for the backlight. */

/* The character display: a 20x4 hd44780 on i2c.i2c0. */
static lcd_bus_hd44780_t *character_bus(i2c_master_bus_handle_t i2c)
{
    return lcd_bus_pcf8574_i2c_create_on_bus(i2c, 0x27, 0);
}

const struct board_character_panel board_character_panel = {.geometry = HD44780_GEOMETRY_20X4, .cols = 20, .rows = 4, .i2c_port = I2C_NUM_0, .on_i2c = character_bus};

