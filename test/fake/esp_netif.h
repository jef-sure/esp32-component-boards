#pragma once
/* The calls of esp_netif the Ethernet adapter makes, as esp_netif.h and esp_netif_defaults.h of ESP-IDF 6.1 declare them. */
#include "esp_err.h"

typedef struct esp_netif_obj esp_netif_t;
typedef struct {
    const void *base;
    const void *driver;
    const void *stack;
} esp_netif_config_t;
#define ESP_NETIF_DEFAULT_ETH() {.base = 0, .driver = 0, .stack = 0}
esp_err_t    esp_netif_init(void);
esp_netif_t *esp_netif_new(const esp_netif_config_t *esp_netif_config);
void         esp_netif_destroy(esp_netif_t *esp_netif);
esp_err_t    esp_netif_attach(esp_netif_t *esp_netif, void *driver_handle);
