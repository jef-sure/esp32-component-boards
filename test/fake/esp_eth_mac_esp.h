#pragma once
/* The internal EMAC of the chip, as esp_eth_mac_esp.h of ESP-IDF 6.1 declares it for the ESP32-P4. */
#include "esp_eth.h"
#include "soc/soc_caps.h"

typedef enum { EMAC_DATA_INTERFACE_RMII, EMAC_DATA_INTERFACE_MII } eth_data_interface_t;
typedef enum { EMAC_CLK_DEFAULT, EMAC_CLK_EXT_IN, EMAC_CLK_OUT } emac_rmii_clock_mode_t;

typedef struct {
    struct {
        int mdc_num;
        int mdio_num;
    } smi_gpio;
    eth_data_interface_t interface;
    struct {
        struct {
            emac_rmii_clock_mode_t clock_mode;
            int                    clock_gpio;
        } rmii;
    } clock_config;
#if SOC_EMAC_USE_MULTI_IO_MUX || SOC_EMAC_MII_USE_GPIO_MATRIX
    struct {
        struct {
            int tx_en_num, txd0_num, txd1_num, crs_dv_num, rxd0_num, rxd1_num;
        } rmii;
    } emac_dataif_gpio;
#endif
} eth_esp32_emac_config_t;
#define ETH_ESP32_EMAC_DEFAULT_CONFIG() {.smi_gpio = {.mdc_num = 31, .mdio_num = 52}, .interface = EMAC_DATA_INTERFACE_RMII}
esp_eth_mac_t *esp_eth_mac_new_esp32(const eth_esp32_emac_config_t *esp32_config, const eth_mac_config_t *config);
