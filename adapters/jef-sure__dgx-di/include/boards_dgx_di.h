#pragma once

/* A touch panel of boards.h as DGX-DI has it. Compiled in when the board has a touch panel (CONFIG_BOARD_TOUCH). */
#include "sdkconfig.h"
#if !CONFIG_BOARD_TOUCH
#error "boards_dgx_di.h: the board chosen has no touch panel; a program for such boards too includes it under #if CONFIG_BOARD_TOUCH"
#endif
#include "boards.h"
#include "dgx_di.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The device of the panel, and the pointer on it, calibrated by the board's data. NULL before board_touch_start. */
dgx_di_device_t  *board_dgx_di_device(const board_touch_t *touch);
dgx_di_pointer_t *board_dgx_di_pointer(const board_touch_t *touch);

#ifdef __cplusplus
}
#endif
