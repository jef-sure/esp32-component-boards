/* A character display of jef-sure/hd44780: set up once, cleared, its light on. */
#include "board_character.h"
#include "esp_log.h"

static const char *TAG = "board";

static hd44780_t *character_lcd;

/* The bus of the display: on the board's I2C master of its port, or on its own GPIOs. */
static lcd_bus_hd44780_t *character_bus(const struct board_character_panel *panel)
{
    if (panel->i2c_port < 0) return panel->on_gpio();
    i2c_master_bus_handle_t i2c = board_glue_i2c(panel->i2c_port);
    if (!i2c) {
        ESP_LOGE(TAG, "board_glue_i2c: no I2C bus on port %d for the character LCD", panel->i2c_port);
        return NULL;
    }
    return panel->on_i2c(i2c);
}

bool board_character_display_init(struct board_character_display *out)
{
    const struct board_character_panel *panel = &board_character_panel;
    if (!out) return false;
    if (!character_lcd) {
        lcd_bus_hd44780_t *bus = character_bus(panel);
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
