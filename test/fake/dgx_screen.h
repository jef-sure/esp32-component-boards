#pragma once
/* The shape of DGX a glue sees, as DGX 0.12.0 has it: a screen, a bus, the orientation and color order enums. What DGX
 * marks deprecated is marked here too, so a glue that uses it does not compile under -Werror. */
#include "esp_idf_stubs.h"
#define DGX_DEPRECATED(instead) __attribute__((deprecated(instead)))
typedef struct _dgx_screen_t { int width, height; } dgx_screen_t;
typedef struct _dgx_bus_protocols_t {
    union {
        void (*dispose_bus)(struct _dgx_bus_protocols_t *);
        void (*dispose)(struct _dgx_bus_protocols_t *) DGX_DEPRECATED("use dgx_bus_dispose(&bus)");
    };
} dgx_bus_protocols_t;
typedef enum { DgxScreenBottomTop = -1, DgxScreenTopBottom = 1, DgxScreenLeftRight = 1, DgxScreenRightLeft = -1 } dgx_orientation_t;
typedef enum { DgxScreenRGB, DgxScreenBGR } dgx_color_order_t;
typedef enum { DgxDsiOneFrame = 1, DgxDsiTwoFrames = 2 } dgx_dsi_frames_t;
/* the calls DGX 0.11.1 and later declare static inline */
esp_err_t dgx_screen_orientation(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy);
void dgx_bus_dispose(dgx_bus_protocols_t **pbus);
