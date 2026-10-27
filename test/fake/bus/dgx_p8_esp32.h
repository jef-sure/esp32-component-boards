#pragma once
#include "../dgx_screen.h"
dgx_bus_protocols_t *dgx_p8_init(gpio_num_t d0, gpio_num_t d1, gpio_num_t d2, gpio_num_t d3, gpio_num_t d4, gpio_num_t d5, gpio_num_t d6, gpio_num_t d7, gpio_num_t wr, gpio_num_t rd, gpio_num_t cs, gpio_num_t dc, int hz);
