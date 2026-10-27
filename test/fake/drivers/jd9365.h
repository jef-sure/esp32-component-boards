#pragma once
#include "../dgx_screen.h"
dgx_screen_t *dgx_jd9365_init(dgx_bus_protocols_t *bus, gpio_num_t rst, uint8_t bits, dgx_color_order_t cbo, dgx_dsi_frames_t frames);
void dgx_jd9365_orientation(dgx_screen_t *s, dgx_orientation_t x, dgx_orientation_t y, bool swap);
