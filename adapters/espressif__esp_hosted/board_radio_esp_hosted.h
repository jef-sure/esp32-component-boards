#pragma once

/* The radio beside the chip reached by esp_hosted, as the ESP32-C6 of an ESP32-P4 board. */
#include "board_glue.h"

bool board_glue_radio_esp_hosted_start(const struct board_radio_entry *entry);
