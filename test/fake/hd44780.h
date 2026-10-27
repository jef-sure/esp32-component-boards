#pragma once
#include "esp_idf_stubs.h"
typedef struct hd44780_s hd44780_t;
typedef enum { HD44780_GEOMETRY_8X2, HD44780_GEOMETRY_16X2, HD44780_GEOMETRY_16X4, HD44780_GEOMETRY_20X2, HD44780_GEOMETRY_20X4, HD44780_GEOMETRY_40X2 } hd44780_geometry_t;
hd44780_t *lcd_init(lcd_bus_hd44780_t *bus, hd44780_geometry_t geometry, bool owns_bus);
void lcd_clear_screen(hd44780_t *lcd);
void lcd_backlight_on(hd44780_t *lcd);
void lcd_set_cursor(hd44780_t *lcd, uint8_t col, uint8_t row);
void lcd_write_str(hd44780_t *lcd, const char *str);
lcd_bus_hd44780_t *lcd_bus_gpio4_create(gpio_num_t rs, gpio_num_t en, gpio_num_t d4, gpio_num_t d5, gpio_num_t d6, gpio_num_t d7);
lcd_bus_hd44780_t *lcd_bus_gpio8_create(gpio_num_t rs, gpio_num_t en, gpio_num_t d0, gpio_num_t d1, gpio_num_t d2, gpio_num_t d3, gpio_num_t d4, gpio_num_t d5, gpio_num_t d6, gpio_num_t d7);
