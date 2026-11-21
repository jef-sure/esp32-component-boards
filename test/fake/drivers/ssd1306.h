#pragma once
#include "../dgx_screen.h"
typedef enum dgx_ssd1306_resolution_t {
    DGX_SSD1306_128X32 = 256,
    DGX_SSD1306_128X64,
    DGX_SSD1306_96X16,
    DGX_SSD1306_64X48,
    DGX_SSD1306_72X40,
    SSD1306_128X32 DGX_DEPRECATED("use DGX_SSD1306_128X32") = DGX_SSD1306_128X32,
    SSD1306_128X64 DGX_DEPRECATED("use DGX_SSD1306_128X64") = DGX_SSD1306_128X64,
    SSD1306_96X16 DGX_DEPRECATED("use DGX_SSD1306_96X16") = DGX_SSD1306_96X16,
    SSD1306_64X48 DGX_DEPRECATED("use DGX_SSD1306_64X48") = DGX_SSD1306_64X48,
    SSD1306_72X40 DGX_DEPRECATED("use DGX_SSD1306_72X40") = DGX_SSD1306_72X40,
} dgx_ssd1306_resolution_t;
void dgx_ssd1306_contrast(dgx_screen_t *scr, uint8_t contrast);
dgx_screen_t *dgx_ssd1306_init(dgx_bus_protocols_t *bus, gpio_num_t rst, dgx_ssd1306_resolution_t resolution, bool ext_vcc);
DGX_DEPRECATED("use dgx_screen_orientation()") void dgx_ssd1306_orientation(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy);
