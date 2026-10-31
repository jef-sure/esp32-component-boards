/* A GSL3680 on the board's I2C bus: it keeps no firmware, the program gives it through board_touch_firmware. */
#include "board_touch_gsl3680.h"
#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_touch_gsl3680_start(dgx_di_gsl3680_t *device, int index, const struct board_touch_panel *panel, const struct board_touch_calibration *calibrated,
                                    const struct board_display *display, struct board_touch *out)
{
    if (!board_dgx_screen(display)) return false;
    i2c_master_bus_handle_t bus = board_glue_i2c();
    if (!bus) return false;
    const uint8_t *fw_start;
    size_t         fw_size;
    if (!board_touch_firmware(&fw_start, &fw_size)) {
        ESP_LOGE(TAG, "board_touch_firmware: no firmware embedded for the touch panel: the program defines it, see the docs");
        return false;
    }
    if (!dgx_di_gsl3680_init(device, bus, panel->rst, panel->irq, 0, fw_start, fw_size)) {
        ESP_LOGE(TAG, "dgx_di_gsl3680_init: no GSL3680 answers");
        return false;
    }
    return board_glue_touch_attach(index, &device->device, panel, calibrated, display, out);
}
