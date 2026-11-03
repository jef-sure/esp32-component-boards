/*
 * The I2C masters of the board, one on each port its data names, made on the first ask and shared:
 * the touch panel and the codec of a board are often on one bus, and ESP-IDF takes one master on a
 * port. NULL when the board has no I2C there or the master cannot be made.
 */
#include "board_glue.h"

#include <sys/lock.h>

#include "sdkconfig.h"

#include "esp_err.h"
#include "esp_log.h"
#include "soc/soc_caps.h"

static const char *TAG = "board";

#define I2C_GLITCH_IGNORE 7 /* clock cycles a glitch may last, as the examples of ESP-IDF set it */

static i2c_master_bus_handle_t kept[SOC_I2C_NUM];
static _lock_t                 kept_lock; /* two tasks asking at once get one master, as i2c_common.c of ESP-IDF locks */

const struct board_i2c_pins *board_i2c_pins(int port)
{
    for (size_t i = 0; i < board_i2c_table.count; ++i)
        if (board_i2c_table.buses[i].port == port) return &board_i2c_table.buses[i];
    return NULL;
}

static i2c_master_bus_handle_t made(int port)
{
    const struct board_i2c_pins *pins = board_i2c_pins(port);
    if (!pins) {
        ESP_LOGE(TAG, "this board has no I2C bus on port %d in its data", port);
        return NULL;
    }
    const i2c_master_bus_config_t config = {.i2c_port = pins->port, .sda_io_num = (gpio_num_t)pins->sda, .scl_io_num = (gpio_num_t)pins->scl,
                                            .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = I2C_GLITCH_IGNORE, .flags.enable_internal_pullup = true};
    i2c_master_bus_handle_t     bus;
    esp_err_t                   err = i2c_new_master_bus(&config, &bus);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_new_master_bus: %s (port %d, SDA %d, SCL %d)", esp_err_to_name(err), port, pins->sda, pins->scl);
        return NULL;
    }
    return bus;
}

i2c_master_bus_handle_t board_glue_i2c(int port)
{
    if (port < 0 || port >= SOC_I2C_NUM) {
        ESP_LOGE(TAG, "I2C port %d: the chip has %d", port, SOC_I2C_NUM);
        return NULL;
    }
    _lock_acquire(&kept_lock);
    if (!kept[port]) kept[port] = made(port);
    i2c_master_bus_handle_t bus = kept[port];
    _lock_release(&kept_lock);
    return bus;
}

struct i2c_master_bus_t *board_i2c(int port)
{
    return board_glue_i2c(port);
}

bool board_i2c_taken(int port)
{
    return board_i2c_pins(port) != NULL;
}
