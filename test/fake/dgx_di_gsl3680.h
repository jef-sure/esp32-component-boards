#pragma once
#include "dgx_di.h"
typedef struct { dgx_di_device_t device; void *dev; } dgx_di_gsl3680_t;
bool dgx_di_gsl3680_init(dgx_di_gsl3680_t *t, i2c_master_bus_handle_t bus, int rst, int int_pin, int scl_hz, const uint8_t *fw, size_t fw_size);
