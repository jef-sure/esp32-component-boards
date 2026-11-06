#pragma once
/* The declarations of nvs.h of ESP-IDF 6.1 that the component calls. */
#include "esp_idf_stubs.h"
typedef uint32_t nvs_handle_t;
typedef enum { NVS_READONLY, NVS_READWRITE, NVS_READWRITE_PURGE } nvs_open_mode_t;
esp_err_t nvs_open(const char *namespace_name, nvs_open_mode_t open_mode, nvs_handle_t *out_handle);
esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, uint8_t value);
esp_err_t nvs_get_u8(nvs_handle_t handle, const char *key, uint8_t *out_value);
esp_err_t nvs_commit(nvs_handle_t handle);
void      nvs_close(nvs_handle_t handle);
