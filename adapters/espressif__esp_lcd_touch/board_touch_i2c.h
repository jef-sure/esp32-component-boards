#pragma once

/* Any driver of esp_lcd_touch on I2C, as a device of DGX-DI: the data names its component, the glue gives its constructor
 * and the I2C settings of the driver's own macro. */
#include "board_glue.h"
#include "board_touch_lcd.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch.h"

struct board_touch_i2c {
    const struct board_touch_panel       *panel;
    const struct board_touch_calibration *calibrated;
    dgx_di_esp_lcd_touch_t               *device; /* given by the glue */
    esp_lcd_panel_io_i2c_config_t         io;      /* the driver's own macro */
    uint8_t                               address; /* of the data, put in io at start */
    int                                   hz;      /* put in io when the macro sets no speed, as some drivers' do not */
    esp_err_t (*create)(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *handle);
};

esp_lcd_touch_handle_t board_glue_touch_i2c_new(const struct board_touch_i2c *i2c);

/* The start of a board_touch_entry of the kind esp_lcd_touch_i2c. */
bool board_glue_touch_i2c_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out);
