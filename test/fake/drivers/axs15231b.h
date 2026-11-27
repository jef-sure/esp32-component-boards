#pragma once
#include "../dgx_screen.h"
/* the shape of include/drivers/axs15231b.h of DGX 0.12.13 */
typedef enum dgx_axs15231b_resolution_t { DGX_AXS15231B_320X480 = 1 } dgx_axs15231b_resolution_t;
dgx_screen_t *dgx_axs15231b_init(dgx_bus_protocols_t *bus, gpio_num_t rst, gpio_num_t backlight, uint8_t color_bits, dgx_color_order_t cbo,
                                 dgx_axs15231b_resolution_t resolution);
