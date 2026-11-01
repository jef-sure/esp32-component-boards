/*
 * What a board can say about itself, as one line of JSON for a report to the catalog: the chip, the flash, and the
 * addresses on an I2C bus when its pins are set in the menu. Nothing else is driven: the pins of an unknown board are
 * unknown. PSRAM is not asked: starting it takes the mode it is wired in, which is what a report would have to tell,
 * so a person adds it. The MAC address is left out, because a report is public.
 */
#include <stdio.h>

#include "driver/i2c_master.h"
#include "esp_chip_info.h"
#include "esp_err.h"
#include "esp_flash.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "board_report";

#define I2C_FIRST   0x08
#define I2C_LAST    0x77
#define I2C_PROBE_MS 20
#define MB          (1024 * 1024)

static void scan_i2c(void)
{
    printf(",\"i2c\":[");
    if (CONFIG_REPORT_I2C_SDA < 0 || CONFIG_REPORT_I2C_SCL < 0) {
        printf("]");
        return;
    }
    const i2c_master_bus_config_t config = {.i2c_port = -1, .sda_io_num = CONFIG_REPORT_I2C_SDA, .scl_io_num = CONFIG_REPORT_I2C_SCL, .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true};
    i2c_master_bus_handle_t bus;
    esp_err_t err = i2c_new_master_bus(&config, &bus);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_new_master_bus: %s", esp_err_to_name(err));
        printf("]");
        return;
    }
    bool first = true;
    for (int address = I2C_FIRST; address <= I2C_LAST; ++address) {
        if (i2c_master_probe(bus, address, I2C_PROBE_MS) == ESP_OK) {
            printf("%s\"0x%02x\"", first ? "" : ",", address);
            first = false;
        }
    }
    printf("]");
    i2c_del_master_bus(bus);
}

void app_main(void)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t flash = 0, id = 0;
    esp_err_t err = esp_flash_get_physical_size(NULL, &flash);
    if (err != ESP_OK) ESP_LOGE(TAG, "esp_flash_get_physical_size: %s", esp_err_to_name(err));
    err = esp_flash_read_id(NULL, &id);
    if (err != ESP_OK) ESP_LOGE(TAG, "esp_flash_read_id: %s", esp_err_to_name(err));
    printf("BOARD_REPORT {\"target\":\"%s\",\"revision\":\"%d.%d\",\"cores\":%d,\"idf\":\"%s\",\"flash_mb\":%lu,\"flash_id\":\"0x%06lx\"",
           CONFIG_IDF_TARGET, chip.revision / 100, chip.revision % 100, chip.cores, esp_get_idf_version(), (unsigned long)(flash / MB), (unsigned long)id);
    scan_i2c();
    printf("}\n");
}
