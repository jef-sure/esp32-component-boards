# Calibration

Two things on a board are measured rather than read off a schematic, and the
component keeps them with the board: the calibration of its touch panel and
the tuning of a MIPI-DSI bus.

## The touch calibration

A touch panel reports raw coordinates in its own range (`x_max`, `y_max` of
the data). DGX-DI maps them onto the display with a calibration measured on a
real board: an affine transform plus three correction knots per axis, and the
timing of how a finger appears and leaves.

`config.calibrations` of the touch keeps what was measured, not that transform: a list with one
entry a measurement, the newest last. An entry holds the places aimed at, each named for where it
is on the display in its own orientation: `left_up`, `right_up`, `left_down`, `right_down`, and
`up`, `down`, `left`, `right`, `middle` when they were measured. Each has `meant`, the pixel aimed
at, and `device`, what the touch controller reported there. The corners are required: TFT_eSPI and
LovyanGFX calibrate by four corners. They aim at the corners themselves and DGX-DI aims further
in, so an export has to extend the places to the corners. No tool exports them yet.

`x_max`, `y_max`, `width` and `height` say what the entry was measured with. `libraries` holds what
only one library uses. For DGX-DI that is `blink_ms` and `gap_ms`, how the panel behaved, and
`rounds` and the `*_tenths` figures, how the measurement went.

`board_touch_start` makes the calibration of DGX-DI from the places with
`dgx_di_calibration_make()`, and its timing with `dgx_di_calibration_steady()`. The transform is
not in the data, so it cannot disagree with the places.

`measured_with` of an entry says which versions it was measured with, since a change in a library
can make a calibration wrong, `rule` says in words when it holds and `notes` what else is known. No
tool reads `rule` yet: the glue takes the last entry.

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
`off_tenths` and `left_tenths` of the entry say how far off the touches were without and with the
calibration, in tenths of a pixel, as the measurement found them.

The tool takes each place from the touches in the log, as their median. The calibration made from
them at start is the one the log printed: on the CYD S028R every number is the same. A text with
only the C initializer gives places worked back from it, where the calibration placed each target.
Those of the JC1060P470C, JC4827W543C and JC8012P4A1C were made that way, since their logs are
gone, and their calibrations are up to 2 pixels from the records they came from.

Nine places are worth measuring: four corners alone lose what bends. On the JC8012P4A1C a
calibration of the corners is up to 13 pixels from one of the nine places.

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
