/* The pointers of DGX-DI the touch panels of the board are read through: one for each, in a slot of the glue. */
#include "board_touch.h"

#include "esp_log.h"

static const char *TAG = "board";

/* dgx_di_calibration_make takes the range from the device, so the range of the data is compared here. Each failure says
 * its own cause: the touch works without a calibration, only not as straight. */
static void calibrate(struct board_touch_slot *slot, const dgx_di_device_t *device, const struct board_touch_panel *panel, const struct board_touch_calibration *calibrated)
{
    if (device->x_max != panel->x_max - 1 || device->y_max != panel->y_max - 1) {
        ESP_LOGW(TAG, "board_touch_start: the panel range %dx%d is not the %dx%d of the data: the calibration is another board's", device->x_max + 1,
                 device->y_max + 1, panel->x_max, panel->y_max);
        return;
    }
    if (!dgx_di_calibration_make(&slot->calibration, device, calibrated->width, calibrated->height, calibrated->aims, calibrated->count)) {
        ESP_LOGW(TAG, "dgx_di_calibration_make: the %d aims of the data do not span the display", calibrated->count);
        return;
    }
    dgx_di_calibration_steady(&slot->calibration, calibrated->blink_ms, calibrated->gap_ms);
    if (!dgx_di_pointer_calibrate(&slot->pointer, &slot->calibration))
        ESP_LOGW(TAG, "dgx_di_pointer_calibrate: the calibration is not for this pointer: measured on another display size");
}

bool board_glue_touch_attach(int index, dgx_di_device_t *device, const struct board_touch_panel *panel,
                             const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out)
{
    struct board_touch_slot *slot = &board_touch_slots.slots[index];
    dgx_di_pointer_init(&slot->pointer, device, 0, board_dgx_screen(display));
    calibrate(slot, device, panel, calibrated);
    if (calibrated->placeholder) ESP_LOGW(TAG, "the touch calibration of this board is a placeholder, not measured: measure the board and put the numbers in the data");
    slot->device = device;
    *out         = (struct board_touch){.fingers = panel->fingers, .x_max = panel->x_max - 1, .y_max = panel->y_max - 1};
    return true;
}

static struct board_touch_slot *slot_of(const struct board_touch *touch)
{
    return touch && touch->index >= 0 && touch->index < board_touch_slots.count ? &board_touch_slots.slots[touch->index] : NULL;
}

dgx_di_device_t *board_dgx_di_device(const struct board_touch *touch)
{
    struct board_touch_slot *slot = slot_of(touch);
    return slot ? slot->device : NULL;
}

dgx_di_pointer_t *board_dgx_di_pointer(const struct board_touch *touch)
{
    struct board_touch_slot *slot = slot_of(touch);
    return slot && slot->device ? &slot->pointer : NULL;
}
