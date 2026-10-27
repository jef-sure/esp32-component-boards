#pragma once
#include "../dgx_screen.h"
dgx_bus_protocols_t *dgx_spi_init(spi_host_device_t host, int dma, gpio_num_t mosi, gpio_num_t miso, gpio_num_t sclk, gpio_num_t cs, gpio_num_t dc, int hz, uint8_t mode);
