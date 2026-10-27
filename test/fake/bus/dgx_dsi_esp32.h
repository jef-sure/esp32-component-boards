#pragma once
#include "../dgx_screen.h"
dgx_bus_protocols_t *dgx_dsi_init(int bus_id, uint8_t lanes, uint32_t mbps, int ldo_chan, int ldo_mv);
