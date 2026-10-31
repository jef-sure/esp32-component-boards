#pragma once

/* A display of boards.h as DGX has it. Compiled in when the board has a graphics display (CONFIG_BOARD_DISPLAY_GRAPHICS). */
#include "boards.h"
#include "dgx_screen.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The screen to draw on; NULL for a display not started. */
dgx_screen_t *board_dgx_screen(const struct board_display *display);

/* The bus of the panel, for tuning (dgx_dsi_tune) and its pace (dgx_dsi_frame_us); NULL for displays shown as one screen. */
dgx_bus_protocols_t *board_dgx_bus(const struct board_display *display);

#ifdef __cplusplus
}
#endif
