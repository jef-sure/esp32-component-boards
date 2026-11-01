# boards

*[По-русски: README.ru.md](README.ru.md)*

An ESP-IDF component that describes the boards a program runs on **once, as
data**, and sets their hardware up for the program. A directory per board in
`catalog/boards/` holds its pins, buses and peripherals in one `board.json`; the
component turns that into C glue and the program asks for what it needs **by
kind**, never by the board's name:

```c
#include "boards.h"
#include "boards_dgx.h"
#include "boards_dgx_di.h"

struct board_display display = {0};
if (board_display_init(&display)) {
    /* display.width, display.height: 1024x600 or 320x240, whatever the chosen board has;
       display.mm_w, display.mm_h: its size in millimetres */
    dgx_screen_t *screen = board_dgx_screen(&display);
}

struct board_touch touch;
if (board_touch_start(&display, &touch)) {
    /* the touch panel under that display, calibrated by the board's data */
    dgx_di_pointer_t *pointer = board_dgx_di_pointer(&touch);
}
```

Every function of `boards.h` exists on every board. One the board does not have
returns `false`, and the program goes on without it. `boards.h` names no library:
the handles of DGX, DGX-DI or hd44780 come from the headers of their adapters. The same `main.c` builds
and runs on the 2.8-inch CYD S028R and on the 10.1-inch Guition.

The component knows no display by itself: a board may have none, and a display
is one peripheral among others. What a board can have today:

- a **graphics display** driven by [DGX](https://github.com/jef-sure/esp32-component-dgx):
  MIPI-DSI, QSPI or SPI panels, with their size in pixels and in millimetres and
  the way they lie on the board;
- a **character display** (HD44780, a 2004 on a PCF8574 backpack) through
  [hd44780](https://github.com/jef-sure/esp32-component-hd44780), on the board
  or as a module on its I2C bus;
- a **touch panel** as a device of [DGX-DI](https://github.com/jef-sure/esp32-component-dgx-di),
  with the calibration measured on the board kept in the data;
- **LVGL** through [DGX-LVGL](https://github.com/jef-sure/esp32-component-dgx-lvgl):
  the display and the touch panel this component sets up become an LVGL display
  and input device, see [examples/hello_lvgl](examples/hello_lvgl);
- **sound**: an ES8311 codec on I2S, an amplifier on I2S, or the ESP32's own DAC;
- a **camera**, as data for now: its bus, connector and sensor are described, the
  component does not start it;
- a **button**; and any **bus** the board wires, even one the component does not
  set up itself (the SDIO of a radio, the pins of an SD slot), kept as data the
  program can read.

## Choosing a board

The board is named once, on one command line. The component's
`tools/board_select.py` writes `sdkconfig.defaults.board` into the project: the
board's chip, memory and flash settings, and the line that chooses it in the
menu of the configuration.

```sh
idf.py add-dependency "jef-sure/boards^0.0.1"
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
idf.py build flash monitor
```

The project's `CMakeLists.txt` reads that file before its own defaults:

```cmake
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
```

No `set-target`, no `menuconfig`. The menu (*Boards → Board the program runs
on*) follows the file; it is there to look at and to override. What the board
needs comes with the choice: the DGX drivers of its panel as `select`s, the
other parts (a touch driver, a codec, hd44780) by rules in the component's
`idf_component.yml`, so a build for the CYD S028R downloads no GT911 driver and no
codec library. See [docs/en/choosing-a-board.md](docs/en/choosing-a-board.md).

## The boards

<!-- boards:table -->
| board | chip | display | touch | sound | button |
|---|---|---|---|---|---|
| CYD (ESP32-2432S028R) | ESP32 | 320x240 ILI9341, SPI, 58x43 mm | XPT2046 (resistive) | DAC, GPIO26 | yes |
| ESP32 DevKit, 4 MB | ESP32 | none | none | none | yes |
| Waveshare ESP32-P4-ETH | ESP32-P4 | none | none | ES8311 | yes |
| Waveshare ESP32-P4-POE-ETH | ESP32-P4 | none | none | ES8311 | yes |
| ESP32-S3 DevKit, 16 MB, 8 MB PSRAM | ESP32-S3 | none | none | none | yes |
| Guition JC1060P470C | ESP32-P4 | 1024x600 JD9165, MIPI-DSI, 154x86 mm | GT911 | ES8311 | yes |
| Guition JC4827W543C | ESP32-S3 | 480x272 NV3041A, QSPI, 95x54 mm | GT911 | I2S amplifier | yes |
| Guition JC8012P4A1C | ESP32-P4 | 1280x800 JD9365, MIPI-DSI, 217x136 mm | GSL3680 (firmware embedded by the program) | ES8311 | yes |
<!-- boards:end -->

A module is connected to whichever board is chosen: `board_select.py cyd_s028r --module
lcd2004_pcf8574 .` adds a 20x4 character LCD on the board's I2C bus.

The GSL3680 of the
10.1-inch board keeps no firmware of its own, and the vendor's array carries no
licence to redistribute: the program embeds it, see
[docs/en/touch-firmware.md](docs/en/touch-firmware.md); without it the board
builds and runs with its touch off.

## What is in the repository

```
catalog/boards/<board>/board.json         the board: the only source of truth
catalog/devices/, catalog/mcu/            what its chips are, under it
catalog/libraries/                        what each library does with each chip, and what its versions require
catalog/boards/<board>/sdkconfig.defaults what its chip, memory and flash need; the lines that choose it
boards/<board>/<board>.c, board.cmake  the glue, generated from the data and committed
boards/boards.cmake, Kconfig           generated too, as are the dependencies of idf_component.yml
include/boards.h                       what a program asks for, by kind
src/                                   the core: board_info, the shared I2C and SPI, the sound task, the firmware hook
adapters/<owner>__<name>/              the code for each library, its public header in include/
tools/boards_gen.py                    data -> glue, Kconfig, lists, manifest rules, README tables
tools/check_format.py                  the schema, the rules and their cases in test/format/
tools/check_boards.py                  the generated is what the data says; pins do not collide; the API holds
tools/board_pins.py                    the map of a board's pins and its tree
tools/board_select.py                  choose the board for a project
tools/board_bom.py                     what to buy for a product, with prices as ranges
tools/update_rates.py                  the exchange rates of the catalog, from the ECB
editor/                                the page: what to build, a kit, a project; and the editor. Any static server from the root, then /editor/
examples/hello_board/                  the smallest program, built for every board in CI
examples/hello_lvgl/                   LVGL through DGX-LVGL, built in CI for every board with a graphics display
examples/local_boards/                 a board and a module of the program itself, in components/local-boards/
docs/en/, docs/ru/                     the documentation
```

The generated files are committed, so a program that takes the component from
the registry builds without running any tool of this repository.
`tools/check_boards.py` fails in CI when they differ from the data.

Documentation, in English: [how it works](docs/en/how-it-works.md),
[the data format](docs/en/data-format.md), [the API](docs/en/api.md),
[choosing a board](docs/en/choosing-a-board.md),
[adding a board](docs/en/adding-a-board.md), [the tools](docs/en/tools.md),
[calibration](docs/en/calibration.md), [the touch firmware](docs/en/touch-firmware.md),
[modules](docs/en/modules.md). In Russian: [docs/ru/](docs/ru/).

## Adding a board

Copy the nearest `catalog/boards/<board>/`, edit `board.json`, write its
`sdkconfig.defaults` with the reasons in comments, run
`python3 tools/boards_gen.py --all`, then `python3 tools/check_boards.py
--host-syntax`. The board is in the menu, the manifest and the README table
without touching any of them. Measure the touch on the board
(`dgx_di_calibrate_measure` of DGX-DI) and give the log to `tools/board_calibration.py`.
See [docs/en/adding-a-board.md](docs/en/adding-a-board.md).

## How it differs from esp-bsp and esp_board_manager

[espressif/esp-bsp](https://github.com/espressif/esp-bsp) describes Espressif's
own boards around LVGL: every manifest pulls `lvgl` and `esp_lvgl_port`, and
the display comes as an LVGL object.
[espressif/esp_board_manager](https://github.com/espressif/esp_board_manager)
describes boards in YAML and generates initialisation code into the project,
with a board selected by `idf.py bmgr`. This component is for boards of one's
own (the Guition line and the CYD first), knows no widget library, keeps the
display one peripheral among others, and keeps the data small enough to be
read and checked by a script: pins, buses, devices, measured calibration. What
it takes from esp-bsp is the mechanism of `components/bsp_selector`: one Kconfig
choice, hidden symbols beside it, manifest rules on them.

## Status

0.0.1. Builds for every board, and with the module, under ESP-IDF 5.5 and 6.1:
the matrix of `.github/workflows/build.yml`. `examples/hello_board` and
`examples/hello_lvgl` were flashed on a CYD S028R, a JC4827W543C and a JC1060P470C
under ESP-IDF 6.1: the display, the touch and the sound start without errors in
the log. Touch coordinates were checked by finger on all three and are correct.
On the JC1060P470C the picture was checked too, colors and orientation. The 2004
module shows its text on an ESP32 dev board. On the JC8012P4A1C, flashed too, the display starts and the sound of
`hello_board` was heard. Its touch needs the firmware the program embeds: with it the log is clean,
and nobody has tried it by finger.

The display module `tft153_st77916` ran on `esp32s3_devkit` as a board of a program, and its picture
was seen. On those pins ESP-IDF 6.1 needs DGX 0.10.3: the SPI driver of 6.1 takes a quad bus for an
octal one. `esp32_devkit` ran as the base of a board of a program.

License: MIT.
