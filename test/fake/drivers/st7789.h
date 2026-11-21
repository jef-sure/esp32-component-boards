#pragma once
#include "../dgx_screen.h"
typedef enum dgx_st7789_resolution_t {
    DGX_ST7789_240X240 = 1,
    DGX_ST7789_240X320 = 2,
    DGX_ST7789_320X240 = 3,
    ST7789_RESOLUTION_240x240 DGX_DEPRECATED("use DGX_ST7789_240X240") = DGX_ST7789_240X240,
    ST7789_RESOLUTION_240x320 DGX_DEPRECATED("use DGX_ST7789_240X320") = DGX_ST7789_240X320,
    ST7789_RESOLUTION_320x240 DGX_DEPRECATED("use DGX_ST7789_320X240") = DGX_ST7789_320X240,
} dgx_st7789_resolution_t;
dgx_screen_t *dgx_st7789_init(dgx_bus_protocols_t *bus, gpio_num_t rst, gpio_num_t backlight, uint8_t bits, dgx_color_order_t cbo, dgx_st7789_resolution_t resolution);
DGX_DEPRECATED("use dgx_screen_orientation()") void dgx_st7789_orientation(dgx_screen_t *s, dgx_orientation_t x, dgx_orientation_t y, bool swap);
