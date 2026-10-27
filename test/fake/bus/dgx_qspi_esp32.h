#pragma once
#include "../dgx_screen.h"
dgx_bus_protocols_t *dgx_qspi_init(spi_host_device_t host, int dma, gpio_num_t d0, gpio_num_t d1, gpio_num_t d2, gpio_num_t d3, gpio_num_t sclk, gpio_num_t cs, int hz, uint8_t mode);
