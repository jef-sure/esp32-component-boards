/* A touch panel of esp_lcd_touch as a device of DGX-DI. */
#include "board_touch_lcd.h"

#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_touch_lcd_attach(dgx_di_esp_lcd_touch_t *device, int index, esp_lcd_touch_handle_t handle, bool numbered, const struct board_touch_panel *panel,
                                 const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out)
{
    dgx_di_esp_lcd_touch_init(device, handle, panel->fingers, numbered);
#if BOARDS_VERSION_JEF_SURE__DGX_DI >= BOARDS_VERSION(0, 2, 2)
    /* a chip that has no new points between its reports is read at their pace, after its INT when it is wired */
    if (panel->reports_hz && !dgx_di_esp_lcd_touch_reports(device, panel->reports_hz))
        ESP_LOGW(TAG, "dgx_di_esp_lcd_touch_reports: its INT not listened to, read at %d Hz without it", panel->reports_hz);
#endif
    return board_glue_touch_attach(index, &device->device, panel, calibrated, display, out);
}
