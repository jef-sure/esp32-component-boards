#pragma once

/* Any driver of esp_lcd_touch on SPI, as a device of DGX-DI: the data names its component, the glue gives its constructor. */
#include "board_glue.h"
#include "board_touch_lcd.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch.h"

struct board_touch_spi {
    const struct board_touch_panel       *panel;
    const struct board_touch_calibration *calibrated;
    dgx_di_esp_lcd_touch_t               *device; /* given by the glue */
    int                                   host, cs, hz;
    bool                                  numbered; /* the panel numbers its fingers: false for a resistive one */
    esp_err_t (*create)(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *handle);
};

esp_lcd_touch_handle_t board_glue_touch_spi_new(const struct board_touch_spi *spi);

/* The start of a board_touch_entry of the kind esp_lcd_touch. */
bool board_glue_touch_spi_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out);
