/*
 * SPI hosts set up by the component: the host of a touch panel, and a host a display shares
 * with other devices, which a display driver that sets its host up keeps for itself.
 */
#include "board_glue.h"

#include "driver/spi_common.h"
#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_spi_host(const struct board_spi_bus *bus)
{
    static unsigned hosts_up; /* a bit per host */
    if (hosts_up & (1u << bus->host)) return true;
    const spi_bus_config_t config = {.mosi_io_num = bus->mosi, .miso_io_num = bus->miso, .sclk_io_num = bus->sclk, .quadwp_io_num = GPIO_NUM_NC,
                                     .quadhd_io_num = GPIO_NUM_NC};
    /* a display on this host needs DMA, and a max_transfer_sz of 0 or at least 4092 */
    esp_err_t err = spi_bus_initialize((spi_host_device_t)bus->host, &config, SPI_DMA_CH_AUTO);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "spi_bus_initialize: %s", esp_err_to_name(err));
        return false;
    }
    hosts_up |= 1u << bus->host;
    return true;
}
