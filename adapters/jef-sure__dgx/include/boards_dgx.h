#pragma once

/* A display of boards.h as DGX has it. Compiled in when the board has a graphics display (CONFIG_BOARD_DISPLAY_GRAPHICS). */
#include "sdkconfig.h"
#if !CONFIG_BOARD_DISPLAY_GRAPHICS
#error "boards_dgx.h: the board chosen has no graphics display; a program for such boards too includes it under #if CONFIG_BOARD_DISPLAY_GRAPHICS"
#endif
#include "boards.h"
#include "dgx_screen.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The screen to draw on; NULL for a display not started. */
dgx_screen_t *board_dgx_screen(const board_display_t *display);

/* The bus of the panel, for tuning (dgx_dsi_tune) and its pace (dgx_dsi_frame_us); NULL for displays shown as one screen. */
dgx_bus_protocols_t *board_dgx_bus(const board_display_t *display);

#ifdef __cplusplus
}
#endif
