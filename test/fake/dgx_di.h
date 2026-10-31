#pragma once
#include "dgx_screen.h"
/* as the real one: the device and the pointer are structs with tags */
typedef struct dgx_di_device { int fingers; } dgx_di_device_t;
typedef struct dgx_di_pointer { int first; } dgx_di_pointer_t;
typedef struct { int16_t meant_x, meant_y, x, y; } dgx_di_knot_t;
#define DGX_DI_KNOTS 3
typedef struct { uint16_t version, size; int16_t x_min, x_max, y_min, y_max, width, height; uint8_t flags, knots_x, knots_y, rounds; int32_t affine[6]; dgx_di_knot_t x[DGX_DI_KNOTS], y[DGX_DI_KNOTS]; uint16_t down_ms, up_ms, blink_ms, gap_ms, off_tenths, worst_tenths, left_tenths, left_worst_tenths; } dgx_di_calibration_t;
void dgx_di_pointer_init(dgx_di_pointer_t *p, dgx_di_device_t *d, int flags, const dgx_screen_t *screen);
bool dgx_di_pointer_calibrate(dgx_di_pointer_t *p, const dgx_di_calibration_t *c);
void dgx_di_pointer_read(dgx_di_pointer_t *p, uint32_t now_ms);
bool dgx_di_pointer_first(dgx_di_pointer_t *p, int *x, int *y);
