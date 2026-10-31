/* A touch panel of esp_lcd_touch on SPI, such as an XPT2046. */
#include "board_touch_spi.h"
#include "esp_log.h"

static const char *TAG = "board";

enum { SPI_QUEUE_DEPTH = 3, CMD_BITS = 8, PARAM_BITS = 8 };

esp_lcd_touch_handle_t board_glue_touch_spi_new(const struct board_touch_spi *spi)
{
    const struct board_spi_bus *bus = board_spi_bus(spi->host);
    if (!bus || !board_glue_spi_host(bus)) return NULL;
    const struct board_touch_panel     *touch  = spi->panel;
    const esp_lcd_panel_io_spi_config_t config = {
        .cs_gpio_num = (gpio_num_t)spi->cs, .dc_gpio_num = GPIO_NUM_NC, .spi_mode = 0, .pclk_hz = spi->hz,
        .trans_queue_depth = SPI_QUEUE_DEPTH, .lcd_cmd_bits = CMD_BITS, .lcd_param_bits = PARAM_BITS,
    };
    esp_lcd_panel_io_handle_t io;
    esp_err_t                 err = esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)(intptr_t)bus->host, &config, &io);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_lcd_new_panel_io_spi: %s", esp_err_to_name(err));
        return NULL;
    }
    const esp_lcd_touch_config_t panel  = {.x_max = touch->x_max, .y_max = touch->y_max, .rst_gpio_num = (gpio_num_t)touch->rst, .int_gpio_num = (gpio_num_t)touch->irq};
    esp_lcd_touch_handle_t       handle = NULL;
    err                                 = spi->create(io, &panel, &handle);
    if (err != ESP_OK || !handle) {
        ESP_LOGE(TAG, "esp_lcd_touch_new_spi: %s: no touch panel answers on the board's SPI bus", esp_err_to_name(err));
        esp_lcd_panel_io_del(io);
        return NULL;
    }
    return handle;
}
