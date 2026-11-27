#pragma once
#include "dgx_di.h"
typedef struct { dgx_di_device_t device; esp_lcd_touch_handle_t handle; bool numbered; } dgx_di_esp_lcd_touch_t;
static inline void dgx_di_esp_lcd_touch_init(dgx_di_esp_lcd_touch_t *t, esp_lcd_touch_handle_t h, int fingers, bool numbered) {
    t->handle         = h;
    t->numbered       = numbered;
    t->device.fingers = fingers;
}
/* 0.2.2: the panel read at the pace of its chip */
bool dgx_di_esp_lcd_touch_reports(dgx_di_esp_lcd_touch_t *t, int hz);
