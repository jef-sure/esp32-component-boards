#pragma once

/* A touch panel on DGX-DI: a driver gives a device, this gives it a pointer on the display. */
#include "board_glue.h"
#include "boards_dgx.h"
#include "boards_dgx_di.h"

struct board_touch_calibration {
    const dgx_di_calibration_t *calibration;
    bool                        placeholder; /* not measured */
};

/* What DGX-DI keeps for a panel: one for each, given by the glue. */
struct board_touch_slot {
    dgx_di_pointer_t pointer;
    dgx_di_device_t *device; /* NULL until it is up */
};
struct board_touch_slots {
    struct board_touch_slot *slots;
    int                      count;
};
extern const struct board_touch_slots board_touch_slots;

/* The pointer on a device that is up, calibrated. */
bool board_glue_touch_attach(int index, dgx_di_device_t *device, const struct board_touch_panel *panel,
                             const struct board_touch_calibration *calibrated, const struct board_display *display, struct board_touch *out);
