#pragma once

/* A GSL3680 on the board's I2C bus: its device is given by the glue. */
#include "board_touch.h"
#include "dgx_di_gsl3680.h"

bool board_glue_touch_gsl3680_start(dgx_di_gsl3680_t *device, int index, const struct board_touch_panel *panel, const struct board_touch_calibration *calibrated,
                                    const struct board_display *display, struct board_touch *out);
