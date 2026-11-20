#pragma once
#include "../bus/dgx_rgb_esp32.h"
typedef struct _dgx_rgb_panel_t { const char *name; } dgx_rgb_panel_t;
extern const dgx_rgb_panel_t dgx_rgb_panel_jc8048b070n;
typedef enum { DgxRgbOneFrame = 1, DgxRgbTwoFrames = 2 } dgx_rgb_frames_t;
dgx_screen_t *dgx_rgb_panel_init(dgx_bus_protocols_t *bus, const dgx_rgb_panel_t *panel, gpio_num_t rst, gpio_num_t backlight, uint8_t color_bits,
                                 dgx_color_order_t cbo, dgx_rgb_frames_t frames);
