/*
 * The Ethernet of a board on the MAC of the chip. The generic PHY driver of esp_eth runs a PHY with the registers of IEEE
 * 802.3, as the IP101, which ESP-IDF 6 has no driver of its own for; an interface of esp_netif takes the address by DHCP.
 */
#include "board_ethernet_emac.h"

#include "esp_eth.h"
#include "esp_eth_mac_esp.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "soc/soc_caps.h"

static const char *TAG = "board";

bool board_glue_ethernet_emac_start(const struct board_ethernet_entry *entry, esp_netif_t **netif)
{
    const struct board_ethernet_emac *emac = entry->emac;
    esp_err_t                         err  = esp_netif_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_netif_init: %s", esp_err_to_name(err));
        return false;
    }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) { /* INVALID_STATE: the program made it already */
        ESP_LOGE(TAG, "esp_event_loop_create_default: %s", esp_err_to_name(err));
        return false;
    }

    eth_mac_config_t        mac_config       = ETH_MAC_DEFAULT_CONFIG();
    eth_esp32_emac_config_t emac_config      = ETH_ESP32_EMAC_DEFAULT_CONFIG();
    emac_config.smi_gpio.mdc_num             = emac->mdc;
    emac_config.smi_gpio.mdio_num            = emac->mdio;
    emac_config.interface                    = EMAC_DATA_INTERFACE_RMII;
    emac_config.clock_config.rmii.clock_mode = emac->clock_out ? EMAC_CLK_OUT : EMAC_CLK_EXT_IN;
    emac_config.clock_config.rmii.clock_gpio = emac->ref_clk;
#if SOC_EMAC_USE_MULTI_IO_MUX || SOC_EMAC_MII_USE_GPIO_MATRIX
    emac_config.emac_dataif_gpio.rmii.tx_en_num  = emac->tx_en;
    emac_config.emac_dataif_gpio.rmii.txd0_num   = emac->txd0;
    emac_config.emac_dataif_gpio.rmii.txd1_num   = emac->txd1;
    emac_config.emac_dataif_gpio.rmii.crs_dv_num = emac->crs_dv;
    emac_config.emac_dataif_gpio.rmii.rxd0_num   = emac->rxd0;
    emac_config.emac_dataif_gpio.rmii.rxd1_num   = emac->rxd1;
#endif
    esp_eth_mac_t *mac = esp_eth_mac_new_esp32(&emac_config, &mac_config);
    if (!mac) {
        ESP_LOGE(TAG, "esp_eth_mac_new_esp32: %s", entry->name);
        return false;
    }
    eth_phy_config_t phy_config = ETH_PHY_DEFAULT_CONFIG();
    phy_config.phy_addr         = emac->phy_address;
    phy_config.reset_gpio_num   = emac->rst;
    if (emac->reset_us) phy_config.hw_reset_assert_time_us = emac->reset_us;
    if (emac->after_reset_ms) phy_config.post_hw_reset_delay_ms = emac->after_reset_ms;
    esp_eth_phy_t *phy = esp_eth_phy_new_generic(&phy_config);
    if (!phy) {
        ESP_LOGE(TAG, "esp_eth_phy_new_generic: %s", entry->name);
        mac->del(mac);
        return false;
    }

    esp_eth_config_t            config       = ETH_DEFAULT_CONFIG(mac, phy);
    esp_eth_handle_t            eth          = NULL;
    esp_netif_t                *made         = NULL;
    esp_eth_netif_glue_handle_t glue         = NULL;
    const esp_netif_config_t    netif_config = ESP_NETIF_DEFAULT_ETH();
    err                                      = esp_eth_driver_install(&config, &eth);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_eth_driver_install: %s", esp_err_to_name(err));
        goto free_phy;
    }
    made = esp_netif_new(&netif_config);
    if (!made) {
        ESP_LOGE(TAG, "esp_netif_new: %s", entry->name);
        goto uninstall;
    }
    glue = esp_eth_new_netif_glue(eth);
    if (!glue) {
        ESP_LOGE(TAG, "esp_eth_new_netif_glue: %s", entry->name);
        goto destroy;
    }
    err = esp_netif_attach(made, glue);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_netif_attach: %s", esp_err_to_name(err));
        goto unglue;
    }
    err = esp_eth_start(eth);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_eth_start: %s", esp_err_to_name(err));
        goto unglue;
    }
    *netif = made;
    return true;

unglue:
    esp_eth_del_netif_glue(glue);
destroy:
    esp_netif_destroy(made);
uninstall:
    esp_eth_driver_uninstall(eth);
free_phy:
    phy->del(phy);
    mac->del(mac);
    return false;
}
