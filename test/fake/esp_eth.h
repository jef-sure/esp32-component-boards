#pragma once
/* The calls of esp_eth the Ethernet adapter makes, as esp_eth_driver.h, esp_eth_mac.h, esp_eth_phy.h and
 * esp_eth_netif_glue.h of ESP-IDF 6.1 declare them. */
#include <stdint.h>

#include "esp_err.h"

typedef struct esp_eth_mac_s esp_eth_mac_t;
struct esp_eth_mac_s {
    esp_err_t (*del)(esp_eth_mac_t *mac);
};
typedef struct esp_eth_phy_s esp_eth_phy_t;
struct esp_eth_phy_s {
    esp_err_t (*del)(esp_eth_phy_t *phy);
};

typedef struct {
    uint32_t sw_reset_timeout_ms;
    uint32_t rx_task_stack_size;
    uint32_t rx_task_prio;
    uint32_t flags;
} eth_mac_config_t;
#define ETH_MAC_DEFAULT_CONFIG() {.sw_reset_timeout_ms = 100, .rx_task_stack_size = 4096, .rx_task_prio = 15, .flags = 0}

typedef struct {
    int32_t  phy_addr;
    uint32_t reset_timeout_ms;
    uint32_t autonego_timeout_ms;
    int      reset_gpio_num;
    int32_t  hw_reset_assert_time_us;
    int32_t  post_hw_reset_delay_ms;
} eth_phy_config_t;
#define ETH_PHY_DEFAULT_CONFIG()                                                                                                                 \
    {.phy_addr = -1, .reset_timeout_ms = 100, .autonego_timeout_ms = 4000, .reset_gpio_num = 5, .hw_reset_assert_time_us = 0, .post_hw_reset_delay_ms = 0}
esp_eth_phy_t *esp_eth_phy_new_generic(const eth_phy_config_t *config);

typedef void *esp_eth_handle_t;
typedef struct {
    esp_eth_mac_t *mac;
    esp_eth_phy_t *phy;
    uint32_t       check_link_period_ms;
} esp_eth_config_t;
#define ETH_DEFAULT_CONFIG(emac, ephy) {.mac = emac, .phy = ephy, .check_link_period_ms = 2000}
esp_err_t esp_eth_driver_install(const esp_eth_config_t *config, esp_eth_handle_t *out_hdl);
esp_err_t esp_eth_driver_uninstall(esp_eth_handle_t hdl);
esp_err_t esp_eth_start(esp_eth_handle_t hdl);

typedef struct esp_eth_netif_glue_t *esp_eth_netif_glue_handle_t;
esp_eth_netif_glue_handle_t esp_eth_new_netif_glue(esp_eth_handle_t eth_hdl);
esp_err_t                   esp_eth_del_netif_glue(esp_eth_netif_glue_handle_t eth_netif_glue);
