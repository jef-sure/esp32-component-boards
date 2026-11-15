#pragma once
/* The calls of esp_hosted 3.0.10 the adapter makes, as host/compat/include/esp_hosted.h and esp_hosted_host_fw_ver.h declare them. */
#include <stdint.h>

typedef struct {
    uint32_t major1;
    uint32_t minor1;
    uint32_t patch1;
    int32_t  revision;
    int32_t  prerelease;
    int32_t  build;
} eh_host_coprocessor_fwver_t;
#define esp_hosted_coprocessor_fwver_t eh_host_coprocessor_fwver_t

#define ESP_HOSTED_VERSION_MAJOR_1 3
#define ESP_HOSTED_VERSION_MINOR_1 0
#define ESP_HOSTED_VERSION_PATCH_1 10

int esp_hosted_connect_to_slave(void);
int esp_hosted_get_coprocessor_fwversion(esp_hosted_coprocessor_fwver_t *ver_info);
