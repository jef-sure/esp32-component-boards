/* A touch panel of esp_lcd_touch as a device of DGX-DI. */
#include "board_touch_lcd.h"

bool board_glue_touch_lcd_attach(dgx_di_esp_lcd_touch_t *device, int index, esp_lcd_touch_handle_t handle, bool numbered, const struct board_touch_panel *panel,
                                 const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out)
{
    dgx_di_esp_lcd_touch_init(device, handle, panel->fingers, numbered);
    return board_glue_touch_attach(index, &device->device, panel, calibrated, display, out);
}
