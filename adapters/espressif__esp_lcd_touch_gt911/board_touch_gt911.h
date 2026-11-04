#pragma once

/* A GT911 on the board's I2C bus, through esp_lcd_touch, as a device of DGX-DI. */
#include "board_glue.h"
#include "board_touch_lcd.h"
#include "esp_lcd_touch.h"

struct board_touch_gt911 {
    const struct board_touch_panel       *panel;
    const struct board_touch_calibration *calibrated;
    dgx_di_esp_lcd_touch_t               *device;    /* given by the glue */
    const uint8_t                        *addresses; /* tried in order */
    int                                   address_count;
    int                                   i2c_hz;
};

esp_lcd_touch_handle_t board_glue_touch_gt911_new(const struct board_touch_gt911 *gt911);

/* The start of a board_touch_entry of the kind gt911. */
bool board_glue_touch_gt911_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out);
