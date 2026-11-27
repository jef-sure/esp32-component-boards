#pragma once
/* the touch part of include/esp_lcd_axs15231b.h of espressif/esp_lcd_axs15231b 2.1.1~1; its macro sets no speed */
#include "esp_idf_stubs.h"
int esp_lcd_touch_new_i2c_axs15231b(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *config, esp_lcd_touch_handle_t *tp);
#define ESP_LCD_TOUCH_IO_I2C_AXS15231B_CONFIG() {.dev_addr = 0x3B}
