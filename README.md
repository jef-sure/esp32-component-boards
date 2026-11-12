# boards

*[По-русски: README.ru.md](README.ru.md)*

An ESP-IDF component that sets up the hardware of a board, its display, touch, sound, buttons and buses, from a
description of the board. A board is described **once, as data**: pins, buses, parts, the size of the display, the
calibration of the touch, each fact with where it comes from. The program asks for parts **by kind**, never by the
board's name, so the same `main.c` builds for the 2.8-inch CYD S028R, for the 10.1-inch Guition, and for a window on
the computer with the display of the board chosen:

```c
#include "boards.h"
#include "boards_dgx.h"
#include "boards_dgx_di.h"

board_display_t display = {0};
if (board_display_init(&display)) {
    /* display.width, display.height: 1024x600 or 320x240, whatever the chosen board has;
       display.mm_w, display.mm_h: its size in millimetres */
    dgx_screen_t *screen = board_dgx_screen(&display);
}

board_touch_t touch;
if (board_touch_start(&display, &touch)) {
    /* the touch panel under that display, calibrated by the board's data */
    dgx_di_pointer_t *pointer = board_dgx_di_pointer(&touch);
}
```

Every function of `boards.h` exists on every board; for a part the board does not have it returns `false`, and the
program goes on without it. The handles of libraries (DGX, DGX-DI, hd44780) come from the headers of their adapters,
see [the API](docs/en/api.md).

## Quick start

It needs ESP-IDF 6 activated in the terminal, and for the window on the computer, Linux with SDL2.

```sh
compote project create-from-example -p my_project jef-sure/boards:hello
cd my_project
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py host --as cyd_s028r .
idf.py build && build/host_cyd_s028r/hello.elf
idf.py --preset cyd_s028r build flash monitor
```

`board_select.py host --as cyd_s028r` gives the project two boards: the CYD and the computer that shows its display in a
window. The first build is the computer: a window with the display of the CYD, the mouse as its touch. The last line
builds and flashes the CYD itself. For another board, put its name from [the table](#the-boards); [the page](#the-page)
helps to choose a board for a device.

The whole path, in VS Code, with the board chosen on the page, a program of your own and what can go wrong, is in
[Getting started](docs/en/getting-started.md).

## Three words

- **The computer** is a build of the same program for Linux, for the target `linux` of ESP-IDF. DGX shows the display of
  the chosen board in a window of SDL2, at its size and turned as the board is held; the mouse is the touch, keys are
  the buttons of the board, and NVS lies in the file `build/host_<board>/flash.bin`. It is the board `host_<board>`,
  which `board_select.py host --as <board>` gives: a program is debugged in the window, then built for the board and
  flashed with no change.
- **A board of the program** is a board described in the program itself, in `components/local-boards/`: a board of the
  catalog with the modules wired to it, or a board of your own. The page names it `<project>_<board>`.
- **The page** is the web page of the component (`editor/`): what the device needs goes on its canvas, and it chooses
  the boards and modules and writes the project, see [below](#the-page).

## What a board can have

The component knows no display by itself: a board may have none, and a display is one peripheral among others:

- a **graphics display** driven by [DGX](https://github.com/jef-sure/esp32-component-dgx):
  MIPI-DSI, QSPI or SPI panels, with their size in pixels and in millimetres and
  the way they lie on the board;
- a **character display** (HD44780, a 2004 on a PCF8574 backpack) through
  [hd44780](https://github.com/jef-sure/esp32-component-hd44780), on the board
  or as a module of the program on its I2C bus;
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

The board is named once, on one command line. The component's `tools/board_select.py` writes two files into the
project: `sdkconfig.defaults.<board>`, the board's chip, memory and flash settings and the line that chooses it in the
menu of the configuration; and `CMakePresets.json`, whose preset builds the board in `build/<board>`. No `set-target`,
no `menuconfig`. ESP-IDF 5 does not read the presets; there the board is named on the command line:
`idf.py -B build/cyd_s028r -D SDKCONFIG=sdkconfig.cyd_s028r -D BOARD=cyd_s028r build flash monitor`.

What the board needs comes with the choice: the DGX drivers of its panel as `select`s, the other parts (a touch
driver, a codec, hd44780) by rules in the component's `idf_component.yml`, so a build for the CYD S028R downloads the
XPT2046 driver and nothing of the GT911 or of the codec. **Every dependency of the component but ESP-IDF is
conditional in this way: a build downloads only what the chosen board needs. The list of dependencies on the page of
the registry cannot tell a conditional one from one that always comes and shows them all: it is what the whole catalog
may need, not what one build downloads.** See
[what comes with the choice](docs/en/choosing-a-board.md#what-comes-with-the-choice). Changing the board and building
for several boards are in [choosing-a-board.md](docs/en/choosing-a-board.md).

## The boards

<!-- boards:table -->
| board | chip | display | touch | sound | button |
|---|---|---|---|---|---|
| CYD (ESP32-2432S028R) | ESP32 | 320x240 ILI9341, SPI, 58x43 mm | XPT2046 (resistive) | DAC, GPIO26 | yes |
| ESP32-C3 with a 0.42-inch OLED | ESP32-C3 | 72x40 SSD1306, I2C, 9.196x5.18 mm | none | none | yes |
| Waveshare ESP32-C3-Zero | ESP32-C3 | none | none | none | yes |
| ESP32-C6 Super Mini | ESP32-C6 | none | none | none | yes |
| ESP32 DevKit, 4 MB | ESP32 | none | none | none | yes |
| ESP32 DevKit, 4 MB, USB-C | ESP32 | none | none | none | yes |
| ESP32 with a 0.96-inch OLED | ESP32 | 128x64 SSD1306, I2C, 22x11.2 mm | none | none | yes |
| Waveshare ESP32-P4-ETH | ESP32-P4 | none | none | ES8311 | yes |
| Waveshare ESP32-P4-POE-ETH | ESP32-P4 | none | none | ES8311 | yes |
| Waveshare ESP32-S3-Zero | ESP32-S3 | none | none | none | yes |
| ESP32-WROVER-DEV | ESP32 | none | none | none | yes |
| ESP32-S3 DevKit, 16 MB, 8 MB PSRAM | ESP32-S3 | none | none | none | yes |
| Guition JC1060P470C | ESP32-P4 | 1024x600 JD9165, MIPI-DSI, 154x86 mm | GT911 | ES8311 | yes |
| Guition JC4827W543C | ESP32-S3 | 480x272 NV3041A, QSPI, 95x54 mm | GT911 | I2S amplifier | yes |
| Guition JC8012P4A1C | ESP32-P4 | 1280x800 JD9365, MIPI-DSI, 217x136 mm | GSL3680 (firmware embedded by the program) | ES8311 | yes |
| NodeMCU ESP-32S V1.1, 38 pins | ESP32 | none | none | none | yes |
<!-- boards:end -->

A module is wired to a board in a board of the program, in its `components/local-boards/`: the page writes one
for a kit with modules, and [examples/local_boards](examples/local_boards) has one written by hand, a round display
on QSPI and a 2004 character LCD on I2C. See [docs/en/modules.md](docs/en/modules.md).

The GSL3680 of the
10.1-inch board keeps no firmware of its own, and the vendor's array carries no
licence to redistribute: the program embeds it, see
[docs/en/touch-firmware.md](docs/en/touch-firmware.md); without it the board
builds and runs with its touch off.

## The page

The page chooses a board and the parts for a device: the roles it needs (a display, a reader, a sensor), the kits that
fit with their wires, levels and prices, and what is not known; then it writes the project. In the folder of a
project, `python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve` prints its link; given to an agent over MCP
(`boards_mcp.py --install`), the page has a dialog with the model too. See [tools.md](docs/en/tools.md#the-page).

## Documentation

[Getting started](docs/en/getting-started.md), [choosing a board](docs/en/choosing-a-board.md),
[moving a program with boards of its own](docs/en/moving-a-program.md), [the API](docs/en/api.md),
[modules](docs/en/modules.md), [the touch firmware](docs/en/touch-firmware.md), [calibration](docs/en/calibration.md),
[the tools](docs/en/tools.md), [the data format](docs/en/data-format.md), [how it works](docs/en/how-it-works.md),
[adding a board](docs/en/adding-a-board.md). In Russian: [docs/ru/](docs/ru/).

## How it differs from esp-bsp and esp_board_manager

[espressif/esp-bsp](https://github.com/espressif/esp-bsp) describes Espressif's own boards around LVGL: every manifest
pulls `lvgl` and `esp_lvgl_port`, and the display comes as an LVGL object.
[espressif/esp_board_manager](https://github.com/espressif/esp_board_manager) describes boards in YAML and generates
initialisation code into the project, with a board selected by `idf.py bmgr`. This component is meant for any board
and any library: today it starts DGX, DGX-DI, DGX-LVGL and hd44780, and other libraries, Arduino among them, are
planned. It differs in how it works. A board is data a script checks: pins, buses, devices, a calibration
measured on the board, and where each fact comes from; a board of a program is described the same way, beside the
program. The display is one peripheral among others. A library is described by chip in `catalog/libraries/`, what it
does with each chip and what its versions require, so DGX, LVGL through DGX-LVGL and other libraries come in through
adapters on the same terms. The page and its solver choose a board and the parts for a task from those facts. Beside the boards of the catalog
in the table above, the page offers boards imported from other descriptions, marked as such. What it takes from esp-bsp is the mechanism of `components/bsp_selector`: one Kconfig
choice, hidden symbols beside it, manifest rules on them.

## Status

The versions and what changed in each are in [CHANGES.md](CHANGES.md). CI builds every board of the catalog under
ESP-IDF 5.5 and 6.1, and a board of a program with a display and a 2004: the jobs of `.github/workflows/build.yml`.

On hardware, in the versions before 0.1.0: `examples/hello_board` and
`examples/hello_lvgl` were flashed on a CYD S028R, a JC4827W543C and a JC1060P470C
under ESP-IDF 6.1: the display, the touch and the sound start without errors in
the log. Touch coordinates were checked by finger on all three and are correct.
On the JC1060P470C the picture was checked too, colors and orientation. The 2004
module showed its text on an ESP32 dev board, as a board of a program that wires its I2C: `esp32_devkit` of the
catalog opens no bus to a module. On the JC8012P4A1C, flashed too, the display starts and the sound of
`hello_board` was heard. Its touch needs the firmware the program embeds: with it the handwritten clock, moved onto
the component, was worked by finger on this board and on the JC1060P470C.

The display module `tft153_st77916` ran on `esp32s3_devkit` as a board of a program, and its picture
was seen. On those pins ESP-IDF 6.1 needs DGX 0.10.3: the SPI driver of 6.1 takes a quad bus for an
octal one. `esp32_devkit` ran as the base of a board of a program.

## How the repository is built

For those who change the component, not for a program that uses it.

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
tools/board_select.py                  choose the boards of a project: their defaults, presets and locks
tools/board_project.py                 a new project without the page, or a kit of the page taken back
tools/boards_mcp.py, project_writer.py the page beside an agent over MCP, or alone with --serve, and its writes
tools/board_bom.py                     what to buy for a product, with prices as ranges
tools/take_report.py                   a price from a GitHub issue, into the catalog
tools/update_rates.py                  the exchange rates of the catalog, from the ECB
editor/                                the page: what to build, a kit, a project; and the editor. Any static server from the root, then /editor/
examples/hello_board/                  the smallest program, built for every board in CI
examples/hello_lvgl/                   LVGL through DGX-LVGL, built in CI for every board with a graphics display
examples/local_boards/                 a board and a module of the program itself, in components/local-boards/
examples/multi_board/                  one program built for two boards of different chips, by presets
examples/board_report/                 the report of a new board, for its first entry in the catalog
docs/en/, docs/ru/                     the documentation
```

The glue, the Kconfig and the rules of the manifest are made from the data and lie in the component: whoever takes it
from the registry makes nothing. The generator and the checks are for whoever changes the data of the boards:
`tools/check_boards.py` fails in CI when what lies in the component differs from the data.

### Adding a board

Copy the nearest `catalog/boards/<board>/`, edit `board.json`, write its
`sdkconfig.defaults` with the reasons in comments, run
`python3 tools/boards_gen.py --all`, then `python3 tools/check_boards.py
--host-syntax`. The board is in the menu, the manifest and the README table
without touching any of them. Measure the touch on the board
(`dgx_di_calibrate_measure` of DGX-DI) and give the log to `tools/board_calibration.py`.
See [docs/en/adding-a-board.md](docs/en/adding-a-board.md).

License: MIT for the work of this repository; what came from others keeps its own license, see [LICENSES.md](LICENSES.md).
