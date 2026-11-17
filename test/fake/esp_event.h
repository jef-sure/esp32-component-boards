#pragma once
/* The call of esp_event the Ethernet adapter makes, as esp_event.h of ESP-IDF 6.1 declares it. */
#include "esp_err.h"

esp_err_t esp_event_loop_create_default(void);
