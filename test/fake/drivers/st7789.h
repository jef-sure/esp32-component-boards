#pragma once
#include "../dgx_screen.h"
typedef enum { ST7789_RESOLUTION_240x240, ST7789_RESOLUTION_240x320, ST7789_RESOLUTION_320x240 } st7789_resolution_t;
dgx_screen_t *dgx_st7789_init(dgx_bus_protocols_t *bus, gpio_num_t rst, uint8_t bits, dgx_color_order_t cbo, st7789_resolution_t resolution);
void dgx_st7789_orientation(dgx_screen_t *s, dgx_orientation_t x, dgx_orientation_t y, bool swap);
