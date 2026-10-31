/* A character display of jef-sure/hd44780: set up once, cleared, its light on. */
#include "board_character.h"
#include "esp_log.h"

static const char *TAG = "board";

static hd44780_t *character_lcd;

bool board_glue_character_init(const struct board_character_panel *panel, struct board_character_display *out)
{
    if (!out) return false;
    if (!character_lcd) {
        lcd_bus_hd44780_t *bus = panel->bus();
        if (!bus) {
            ESP_LOGE(TAG, "lcd_bus: no bus for the character LCD");
            return false;
        }
        character_lcd = lcd_init(bus, panel->geometry, true); /* it owns the bus: gone with a failed init */
        if (!character_lcd) {
            ESP_LOGE(TAG, "lcd_init: the character LCD did not take its init sequence");
            return false;
        }
        lcd_clear_screen(character_lcd);
        lcd_backlight_on(character_lcd);
    }
    out->cols = panel->cols;
    out->rows = panel->rows;
    return true;
}

hd44780_t *board_hd44780(const struct board_character_display *display)
{
    (void)display; /* a board has one yet */
    return character_lcd;
}
