#pragma once
#include "../dgx_screen.h"
dgx_screen_t *dgx_st7701_init(dgx_bus_protocols_t *bus, gpio_num_t rst, gpio_num_t backlight, uint8_t color_bits, dgx_color_order_t cbo, dgx_dsi_frames_t frames);
