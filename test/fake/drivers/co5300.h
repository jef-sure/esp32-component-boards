#pragma once
#include "../dgx_screen.h"
typedef enum dgx_co5300_resolution_t {
    DGX_CO5300_466X466 = 1,
    DGX_CO5300_480X480 = 2,
    DGX_CO5300_368X448 = 3,
    DGX_CO5300_280X456 = 4,
} dgx_co5300_resolution_t;
dgx_screen_t *dgx_co5300_init(dgx_bus_protocols_t *bus, gpio_num_t rst, uint8_t color_bits, dgx_color_order_t cbo, dgx_co5300_resolution_t resolution);
