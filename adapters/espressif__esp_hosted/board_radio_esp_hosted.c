/*
 * The radio beside the chip by esp_hosted: it starts before app_main, and here the program waits for it and learns
 * whether it runs the esp_hosted the program was built with. The two sides should run the same version: esp_hosted
 * says so, and a version apart is named in the log with the way to bring the radio to the program's.
 */
#include "board_radio_esp_hosted.h"

#include "esp_err.h"
#include "esp_hosted.h"
#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_radio_esp_hosted_start(const struct board_radio_entry *entry)
{
    int rc = esp_hosted_connect_to_slave();
    if (rc != 0) {
        ESP_LOGE(TAG, "esp_hosted_connect_to_slave: %d", rc);
        return false;
    }
    esp_hosted_coprocessor_fwver_t runs = {0};
    rc                                  = esp_hosted_get_coprocessor_fwversion(&runs);
    if (rc != 0) {
        ESP_LOGE(TAG, "esp_hosted_get_coprocessor_fwversion: %s", esp_err_to_name((esp_err_t)rc));
        return false;
    }
    if (runs.major1 == ESP_HOSTED_VERSION_MAJOR_1 && runs.minor1 == ESP_HOSTED_VERSION_MINOR_1 && runs.patch1 == ESP_HOSTED_VERSION_PATCH_1)
        return true;
    if (entry->update) {
        ESP_LOGW(TAG, "%s runs esp_hosted %u.%u.%u, the program %d.%d.%d: BOARD_RADIO_FORCE=1 idf.py flash brings it to the program's",
                 entry->name, (unsigned)runs.major1, (unsigned)runs.minor1, (unsigned)runs.patch1, ESP_HOSTED_VERSION_MAJOR_1,
                 ESP_HOSTED_VERSION_MINOR_1, ESP_HOSTED_VERSION_PATCH_1);
    } else {
        ESP_LOGW(TAG, "%s runs esp_hosted %u.%u.%u, the program %d.%d.%d: its firmware is its own, the component leaves it", entry->name,
                 (unsigned)runs.major1, (unsigned)runs.minor1, (unsigned)runs.patch1, ESP_HOSTED_VERSION_MAJOR_1, ESP_HOSTED_VERSION_MINOR_1,
                 ESP_HOSTED_VERSION_PATCH_1);
    }
    return true;
}
