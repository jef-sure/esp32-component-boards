#pragma once

/* An Ethernet PHY on the MAC of the chip over RMII, by esp_eth of ESP-IDF and its generic PHY driver. */
#include "board_glue.h"
#include "driver/gpio.h"

struct board_ethernet_emac {
    int  phy_address;
    int  rst; /* GPIO_NUM_NC when the board has no reset line */
    int  mdc, mdio;
    int  tx_en, txd0, txd1, rxd0, rxd1, crs_dv;
    int  ref_clk;
    bool clock_out;                /* the chip gives the clock of RMII on ref_clk; else the PHY gives it */
    int  reset_us, after_reset_ms; /* how long the reset of the PHY is held and waited for; 0 leaves those of the driver */
};

/* The start of a board_ethernet_entry of the kind emac. */
bool board_glue_ethernet_emac_start(const struct board_ethernet_entry *entry, struct esp_netif_obj **netif);
