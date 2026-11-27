#pragma once
#include "esp_idf_stubs.h"
#define ESP_LCD_TOUCH_IO_I2C_CST816S_CONFIG() {.dev_addr = 0x15, .scl_speed_hz = 100000}
int esp_lcd_touch_new_i2c_cst816s(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *tp);
