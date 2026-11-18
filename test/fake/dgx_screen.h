#pragma once
/* The shape of DGX a glue sees: a screen, a bus, the orientation and color order enums. */
#include "esp_idf_stubs.h"
typedef struct _dgx_screen_t { int width, height; } dgx_screen_t;
typedef struct _dgx_bus_protocols_t { void (*dispose)(struct _dgx_bus_protocols_t *); } dgx_bus_protocols_t;
typedef enum { DgxScreenBottomTop = -1, DgxScreenTopBottom = 1, DgxScreenLeftRight = 1, DgxScreenRightLeft = -1 } dgx_orientation_t;
typedef enum { DgxScreenRGB, DgxScreenBGR } dgx_color_order_t;
typedef enum { DgxDsiOneFrame = 1, DgxDsiTwoFrames = 2 } dgx_dsi_frames_t;
/* the call that turns every display, as dgx_screen.h of DGX 0.11.1 and later declares it (static inline there) */
esp_err_t dgx_screen_orientation(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy);
