#pragma once
#include "../dgx_screen.h"
dgx_bus_protocols_t *dgx_i2c_init_on_bus(i2c_master_bus_handle_t i2c_bus, uint8_t i2c_address, int clock_speed_hz);
