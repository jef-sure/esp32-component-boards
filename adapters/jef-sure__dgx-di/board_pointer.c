/* The pointers of DGX-DI the touch panels of the board are read through: one for each, in a slot of the glue. */
#include "board_touch.h"

#include "esp_log.h"

static const char *TAG = "board";

bool board_glue_touch_attach(int index, dgx_di_device_t *device, const struct board_touch_panel *panel,
                             const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out)
{
    struct board_touch_slot *slot = &board_touch_slots.slots[index];
    dgx_di_pointer_init(&slot->pointer, device, 0, board_dgx_screen(display));
    if (!dgx_di_pointer_calibrate(&slot->pointer, calibrated->calibration))
        ESP_LOGW(TAG, "dgx_di_pointer_calibrate: the calibration is not this board's: the touch works, only not as straight");
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
