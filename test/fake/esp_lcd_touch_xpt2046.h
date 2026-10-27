#pragma once
#include "esp_idf_stubs.h"
int esp_lcd_touch_new_spi_xpt2046(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *out);
