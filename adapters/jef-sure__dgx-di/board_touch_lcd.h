#pragma once

/* A touch panel of esp_lcd_touch as a device of DGX-DI: its device is given by the glue. */
#include "board_touch.h"
#include "dgx_di_esp_lcd_touch.h"

/* numbered: the panel numbers its fingers. */
bool board_glue_touch_lcd_attach(dgx_di_esp_lcd_touch_t *device, int index, esp_lcd_touch_handle_t handle, bool numbered, const struct board_touch_panel *panel,
                                 const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out);
