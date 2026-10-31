#pragma once

/* A touch panel of boards.h as DGX-DI has it. Compiled in when the board has a touch panel (CONFIG_BOARD_TOUCH). */
#include "boards.h"
#include "dgx_di.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The device of the panel, and the pointer on it, calibrated by the board's data. NULL before board_touch_start. */
dgx_di_device_t  *board_dgx_di_device(const struct board_touch *touch);
dgx_di_pointer_t *board_dgx_di_pointer(const struct board_touch *touch);

#ifdef __cplusplus
}
#endif
