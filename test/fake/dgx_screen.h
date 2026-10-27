#pragma once
/* The shape of DGX a glue sees: a screen, a bus, the orientation and color order enums. */
#include "esp_idf_stubs.h"
typedef struct dgx_screen { int width, height; } dgx_screen_t;
typedef struct dgx_bus_protocols { void (*dispose)(struct dgx_bus_protocols *); } dgx_bus_protocols_t;
typedef enum { DgxScreenBottomTop = -1, DgxScreenTopBottom = 1, DgxScreenLeftRight = 1, DgxScreenRightLeft = -1 } dgx_orientation_t;
typedef enum { DgxScreenRGB, DgxScreenBGR } dgx_color_order_t;
typedef enum { DgxDsiOneFrame = 1, DgxDsiTwoFrames = 2 } dgx_dsi_frames_t;
