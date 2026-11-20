#pragma once
#include "../dgx_screen.h"
typedef struct _dgx_rgb_pins_t {
    gpio_num_t pclk, hsync, vsync, de, disp;
    gpio_num_t data[16];
} dgx_rgb_pins_t;
dgx_bus_protocols_t *dgx_rgb_init(const dgx_rgb_pins_t *pins, uint32_t pclk_hz);
