/* A GSL3680 on the board's I2C bus: it keeps no firmware, the program gives it with board_touch_firmware_set. */
#include "board_touch_gsl3680.h"
#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_touch_gsl3680_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out)
{
    const struct board_touch_panel *panel  = entry->gsl3680->panel;
    dgx_di_gsl3680_t               *device = entry->gsl3680->device;
    if (!board_dgx_screen(display)) return false;
    i2c_master_bus_handle_t bus = board_glue_i2c(panel->i2c_port);
    if (!bus) return false;
    const uint8_t *fw_start;
    size_t         fw_size;
    if (!board_glue_touch_firmware(&fw_start, &fw_size)) {
        ESP_LOGE(TAG, "board_touch_start: no firmware for the touch panel: the program gives it with board_touch_firmware_set, see the docs");
        return false;
    }
    if (!dgx_di_gsl3680_init(device, bus, panel->rst, panel->irq, 0, fw_start, fw_size)) {
        ESP_LOGE(TAG, "dgx_di_gsl3680_init: no GSL3680 found");
        return false;
    }
    return board_glue_touch_attach(index, &device->device, panel, entry->gsl3680->calibrated, display, out);
}
