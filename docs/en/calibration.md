# Calibration

Two things on a board are measured rather than read off a schematic, and the
component keeps them with the board: the calibration of its touch panel and
the tuning of a MIPI-DSI bus.

## The touch calibration

A touch panel reports raw coordinates in its own range (`x_max`, `y_max` of
the data). DGX-DI maps them onto the display with a calibration measured on a
real board: an affine transform plus three correction knots per axis, and the
timing of how a finger appears and leaves (`down_ms`, `up_ms`, `blink_ms`).
The data of every board carries one, under `config.calibrations` of the touch, by the library
that reads it: each library has a form of its own, and a panel may keep one for each. A library
keeps a list, the newest last. `measured_with` of an entry says which versions it was measured
with, since a change in a library can make a calibration wrong, `rule` says in words when it holds
and `notes` what else is known. No tool reads `rule` yet: the glue takes the last entry. The glue
hands it to the pointer at `board_touch_start`.

A calibration is measured on **one** board of a kind. Another board of the
same kind is close, not identical; if it matters, measure again. A calibration
holds for the display size and panel range it was measured with: the pointer
refuses one that does not match and the log says *the calibration is not this
board's*.

### Measuring

DGX-DI provides `dgx_di_calibrate_measure(device, screen, rounds, &calibration)`
(`dgx_di_calibrate.h`): targets blink on the display in turn, a finger goes
down on each, and after the rounds the function fills the calibration and
logs it both in words and as a C initializer. DGX-DI's example `touch_check`
runs it on a board's own display. In a program of this component:

```c
struct board_display display = {0};
struct board_touch touch;
board_display_init(&display);
board_touch_start(&display, &touch);
dgx_di_calibration_t measured;
if (dgx_di_calibrate_measure(board_dgx_di_device(&touch), board_dgx_screen(&display), 3, &measured)) {
    char text[1024];
    dgx_di_calibration_code(&measured, text, sizeof text);  /* the C initializer, printed to the log */
    puts(text);
}
```

Give the task that runs it some stack (it takes about 3 KB) and let nothing
else draw meanwhile.

### Keeping it

Save the log and give it to the tool, which writes the numbers into the board and
drops `measured`: `python3 tools/board_calibration.py <board> < log.txt`. Then run
`tools/boards_gen.py --all` and build.
The log at the next start says how far off touches were before and after
(`off_tenths`, `left_tenths`: tenths of a pixel), which is a good check that
the right numbers landed.

A board whose calibration was never measured has `"measured": false`: the
glue warns at start and the README table says so.

## The DSI tuning

On MIPI-DSI the DGX bus decides what goes through the chip's 2D DMA and what
through the processor, and how much room to leave before the panel's scan, by
numbers that depend on the chip, its PSRAM and the panel. The bus starts with
the numbers of the board DGX was written on; `dgx_dsi_bench()` measures the
board at hand in a fraction of a second, `dgx_dsi_tune()` gives the result to
the bus. The component exposes the bus as `board_display.bus` for exactly
this. A program measures once and keeps the numbers in NVS:

```c
#include "bus/dgx_dsi_esp32.h"
if (display.bus && display.bus->bus_type == DGX_BUS_DSI) {
    dgx_dsi_tuning_t tuning;
    /* read it from NVS; if there is none or dgx_dsi_tune() refuses it: */
    if (dgx_dsi_bench(display.bus, &tuning) && dgx_dsi_tune(display.bus, &tuning)) { /* write it to NVS */ }
}
```

Unlike the touch calibration, this is not kept in the board's data yet: it
belongs to the chip at hand as much as to the board. A future version keeps
measured calibrations of both kinds in `catalog/boards/<board>/calibrations/`
and lets a program choose by chip revision.
