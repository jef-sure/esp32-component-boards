#pragma once

/* Any driver of esp_lcd_touch on SPI: the data names its component, the glue gives its constructor. */
#include "board_glue.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch.h"

struct board_touch_spi {
    const struct board_touch_panel *panel;
    int                             host, cs, hz;
    esp_err_t (*create)(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *handle);
};

esp_lcd_touch_handle_t board_glue_touch_spi_new(const struct board_touch_spi *spi);
