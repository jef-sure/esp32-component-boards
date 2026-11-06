/*
 * The level of a sound the person chose last, kept in NVS between starts: how loud a board should sound depends on the
 * room and on who is near, so the level of the data is only the first. NVS is set up here when the program has not; a
 * partition NVS cannot take as it is (ESP_ERR_NVS_NO_FREE_PAGES and the like) is the program's to erase, not this.
 */
#include <stdio.h>

#include "board_volume.h"
#include "boards.h"
#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "board";

enum { VOLUME_MIN = 1, VOLUME_MAX = 100, KEY_MAX = 16 };
#define VOLUME_NAMESPACE "boards"

/* NVS set up once; false when it cannot be, said once */
static bool volume_store(void)
{
    static int ready; /* 0 not tried, 1 ready, -1 not */
    if (!ready) {
        esp_err_t err = nvs_flash_init();
        ready         = err == ESP_OK ? 1 : -1;
        if (err != ESP_OK) ESP_LOGW(TAG, "nvs_flash_init: %s: the level of the sound is not kept", esp_err_to_name(err));
    }
    return ready > 0;
}

/* the key of a sound by its place: a board has few, and a key of NVS is 15 letters at most */
static void volume_key(int index, char *key)
{
    snprintf(key, KEY_MAX, "volume%u", (unsigned)(uint8_t)index);
}

int board_volume_kept(int index, int data_volume)
{
    nvs_handle_t nvs;
    char         key[KEY_MAX];
    uint8_t      kept = 0;
    volume_key(index, key);
    if (!volume_store() || nvs_open(VOLUME_NAMESPACE, NVS_READONLY, &nvs) != ESP_OK) return data_volume;
    const esp_err_t err = nvs_get_u8(nvs, key, &kept);
    nvs_close(nvs);
    return err == ESP_OK && kept >= VOLUME_MIN && kept <= VOLUME_MAX ? kept : data_volume;
}

bool board_sound_volume_keep_at(int index, int percent)
{
    if (index < 0 || index >= board_sound_count() || percent < VOLUME_MIN || percent > VOLUME_MAX || !volume_store()) return false;
    nvs_handle_t nvs;
    char         key[KEY_MAX];
    volume_key(index, key);
    esp_err_t err = nvs_open(VOLUME_NAMESPACE, NVS_READWRITE, &nvs);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_open: %s", esp_err_to_name(err));
        return false;
    }
    if ((err = nvs_set_u8(nvs, key, (uint8_t)percent)) == ESP_OK) err = nvs_commit(nvs);
    nvs_close(nvs);
    if (err != ESP_OK) ESP_LOGE(TAG, "nvs_set_u8: %s", esp_err_to_name(err));
    return err == ESP_OK;
}

bool board_sound_volume_keep(int percent)
{
    return board_sound_volume_keep_at(0, percent);
}
