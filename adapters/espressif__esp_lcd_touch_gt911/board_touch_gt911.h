#pragma once

/* A GT911 on the board's I2C bus, through esp_lcd_touch. */
#include "board_glue.h"
#include "esp_lcd_touch.h"

struct board_touch_gt911 {
    const struct board_touch_panel *panel;
    const uint8_t                  *addresses; /* tried in order */
    int                             address_count;
    int                             i2c_hz;
};

esp_lcd_touch_handle_t board_glue_touch_gt911_new(const struct board_touch_gt911 *gt911);
