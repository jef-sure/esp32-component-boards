#pragma once
#include "../dgx_screen.h"
dgx_screen_t *dgx_st77916_init(dgx_bus_protocols_t *bus, gpio_num_t rst, gpio_num_t bl, uint8_t bits, dgx_color_order_t order);
void dgx_st77916_orientation(dgx_screen_t *s, dgx_orientation_t x, dgx_orientation_t y, bool swap);
