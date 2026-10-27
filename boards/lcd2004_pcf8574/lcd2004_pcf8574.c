/*
 * The glue of lcd2004_pcf8574, made by tools/boards_gen.py from boards-data/lcd2004_pcf8574/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * A module: not a board but a device the chosen board's bus carries; it gives the function of
 * its kind, and the board's glue leaves that one out (CONFIG_BOARD_MODULE_CHARACTER_DISPLAY).
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "esp_log.h"
#include "hd44780.h"
#include <stdlib.h>
#include <string.h>

/* 2004 character LCD on a PCF8574 backpack: A 20x4 HD44780 on the common I2C backpack (P0 RS, P1 RW, P2 E, P3 backlight, P4-P7 D4-D7): not a board of its own, a display any board's I2C bus can carry. */

/* The character display: a 20x4 hd44780 on the board's I2C bus (jef-sure/hd44780). */
static hd44780_t *character_lcd;

bool board_character_display_init(struct board_character_display *out)
{
    if (!out) return false;
    if (!character_lcd) {
        i2c_master_bus_handle_t bus = board_glue_i2c();
        if (!bus) return false;
        lcd_bus_hd44780_t *backpack = lcd_bus_pcf8574_i2c_create_on_bus(bus, 0x27, 0);
        if (!backpack) {
            ESP_LOGE("board", "no PCF8574 backpack at the address of the data");
            return false;
        }
        character_lcd = lcd_init(backpack, HD44780_GEOMETRY_20X4, true); /* the controller owns the backpack: gone with a failed init */
        if (!character_lcd) {
            ESP_LOGE("board", "the character LCD did not take its init sequence");
            return false;
        }
        lcd_clear_screen(character_lcd);
        lcd_backlight_on(character_lcd);
    }
    out->lcd = character_lcd;
    out->cols = 20, out->rows = 4;
    return true;
}

