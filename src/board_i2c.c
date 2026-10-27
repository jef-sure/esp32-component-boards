/*
 * The I2C master of the board, made once from the pins its data names and shared by whoever
 * asks: the touch panel and the codec of a board are often on one bus. NULL when the board
 * has no I2C or the master cannot be made.
 */
#include "board_glue.h"

#include "sdkconfig.h"

#include "esp_log.h"

static const char *TAG = "board";

i2c_master_bus_handle_t board_glue_i2c(void)
{
    static i2c_master_bus_handle_t kept;
    if (kept) return kept;
    const struct board_i2c_pins *pins = board_i2c_pins();
    if (!pins) {
        ESP_LOGE(TAG, "this board has no I2C bus in its data");
        return NULL;
    }
    const i2c_master_bus_config_t config = {.i2c_port = pins->port, .sda_io_num = (gpio_num_t)pins->sda, .scl_io_num = (gpio_num_t)pins->scl,
                                            .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true};
    i2c_master_bus_handle_t     bus;
    if (i2c_new_master_bus(&config, &bus) != ESP_OK) {
        ESP_LOGE(TAG, "no I2C bus at SDA %d SCL %d", pins->sda, pins->scl);
        return NULL;
    }
    kept = bus;
    return kept;
}
