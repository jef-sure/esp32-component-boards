#pragma once

/* A GSL3680 on the board's I2C bus: its device is given by the glue. */
#include "board_touch.h"
#include "dgx_di_gsl3680.h"

struct board_touch_gsl3680 {
    const struct board_touch_panel       *panel;
    const struct board_touch_calibration *calibrated;
    dgx_di_gsl3680_t                     *device; /* given by the glue */
};

/* The start of a board_touch_entry of the kind gsl3680. */
bool board_glue_touch_gsl3680_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out);
