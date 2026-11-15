# boards

*[По-русски: README.ru.md](README.ru.md)*

Write an ESP-IDF program once and choose the board when you build it: a board of the catalog, a board of your own, or
a window on the computer that shows the display of the chosen board. The component sets up the display, touch, sound,
radio, buttons and buses of that board; the program asks for parts **by kind**, never by the board's name:

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

When the board of a project changes, the program stays: one command chooses the new board, and at most the program
adapts to what differs in its data, such as the size of the display or a part the new board lacks. When a fact about a
board is corrected, or a library changes how its parts are started, the change goes into the data and the component,
not into the program. The [handwritten clock](https://github.com/jef-sure/handwritten-clock) is such a program: one
code for the CYD S028R (ESP32, 320x240 on SPI), the 7-inch JC1060P470C and the 10.1-inch JC8012P4A1C (ESP32-P4,
MIPI-DSI). It names a board in one place only, and not for a technical reason: the vendor gives no licence to
redistribute the firmware of the touch of the 10.1-inch board, so the program embeds it for that board. When the component took over the radio beside the ESP32-P4 in 0.2.0, the clock dropped its
own code for it.

A board is described **once, as data**, each fact with where it comes from: a schematic, the vendor, a measurement on
the board. The rest is made from that description: the code that starts the parts, the configuration, the
dependencies a build downloads, the map of pins, and the choice of a board for a device.

[The editor](#the-editor) shortens the way from an idea to the work on it. It takes what a device needs, a display, a
reader, a sensor, and gives kits: the boards and modules that do it, with their wires, levels and prices, and the
libraries that drive them, the best of what is available, parts already at hand among them. Then it writes the
project.

## Quick start

It needs ESP-IDF 6 activated in the terminal, and for the window on the computer, Linux with SDL2. On Windows there are
two ways, not tried yet:

- **WSL2**: ESP-IDF in a Linux distribution of WSL2; WSLg shows the window; `usbipd attach --wsl` gives it the board
  to flash.
- **A devcontainer**: the ESP-IDF image with SDL2; the window through WSLg mounted into the container
  (`/tmp/.X11-unix`, `/mnt/wslg`); flashing through RFC2217 (`esp_rfc2217_server` on Windows), which the step of the
  radio of the ESP32-P4 boards does not take yet.

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
builds and flashes the CYD itself. For another board, put its name from [the table](#the-boards); [the editor](#the-editor)
helps to choose a board for a device.

The whole path, in VS Code, with the board chosen in the editor, a program of your own and what can go wrong, is in
[Getting started](docs/en/getting-started.md).

## Three words

- **The computer** is a build of the same program for Linux, for the target `linux` of ESP-IDF. DGX shows the display of
  the chosen board in a window of SDL2, at its size and turned as the board is held; the mouse is the touch, keys are
  the buttons of the board, and NVS lies in the file `build/host_<board>/flash.bin`. It is the board `host_<board>`,
  which `board_select.py host --as <board>` gives: a program is debugged in the window, then built for the board and
  flashed with no change.
- **A board of the program** is a board described in the program itself, in `components/local-boards/`: a board of the
  catalog with the modules wired to it, or a board of your own. The editor names it `<project>_<board>`.
- **The editor** is the web page of the component (`editor/`): what the device needs goes on its canvas, and it chooses
  the boards and modules and writes the project, see [below](#the-editor).

## What a board can have

The component knows no display by itself: a board may have none, and a display is one peripheral among others:

- a **graphics display** driven by [DGX](https://github.com/jef-sure/esp32-component-dgx):
  MIPI-DSI, QSPI or SPI panels, with their size in pixels and in millimetres and
  the way they lie on the board;
- a **character display** (HD44780) through
  [hd44780](https://github.com/jef-sure/esp32-component-hd44780), on the board
  or as a module: a 2004 on a PCF8574 backpack on I2C, or a bare one on GPIOs;
- a **touch panel** as a device of [DGX-DI](https://github.com/jef-sure/esp32-component-dgx-di),
  with the calibration measured on the board kept in the data;
- **LVGL** through [DGX-LVGL](https://github.com/jef-sure/esp32-component-dgx-lvgl):
  the display and the touch panel this component sets up become an LVGL display
  and input device, see [examples/hello_lvgl](examples/hello_lvgl);
- **sound**: an ES8311 codec on I2S, an amplifier on I2S, or the ESP32's own DAC;
- a **radio** beside the chip: the ESP32-C6 of the two ESP32-P4 boards, reached through esp_hosted.
  `board_radio_start()` starts it, and a step of the flash brings its firmware to the esp_hosted of the build,
  keeping nothing of it in the flash of the board, see [the radio](docs/en/radio.md);
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

Each library comes as a range of versions, those its adapter is built with: the component manager takes the newest of
the range unless the program names one, and the glue of a board chooses its calls by the version the build took. A
board whose part a library gained later stops with `#error` below that version. CI builds every board with the oldest
version of each range and the newest of each older line, see [versions](docs/en/choosing-a-board.md#versions).

## The boards

<!-- boards:table -->
| board | chip | display | touch | sound | button | tried on the board |
|---|---|---|---|---|---|---|
| CYD (ESP32-2432S028R) | ESP32 | 320x240 ILI9341, SPI, 58x43 mm | XPT2046 (resistive) | DAC, GPIO26 | yes | touch; only started: display, sound |
| ESP32-C3 with a 0.42-inch OLED | ESP32-C3 | 72x40 SSD1306, I2C, 9.196x5.18 mm | none | none | yes | display |
| Waveshare ESP32-C3-Zero | ESP32-C3 | none | none | none | yes | — |
| ESP32-C6 Super Mini | ESP32-C6 | none | none | none | yes | — |
| ESP32 DevKit, 4 MB | ESP32 | none | none | none | yes | — |
| ESP32 DevKit, 4 MB, USB-C | ESP32 | none | none | none | yes | — |
| ESP32 with a 0.96-inch OLED | ESP32 | 128x64 SSD1306, I2C, 22x11.2 mm | none | none | yes | display |
| Waveshare ESP32-P4-ETH | ESP32-P4 | none | none | ES8311 | yes | — |
| Waveshare ESP32-P4-POE-ETH | ESP32-P4 | none | none | ES8311 | yes | — |
| Waveshare ESP32-S3-Zero | ESP32-S3 | none | none | none | yes | — |
| ESP32-WROVER-DEV | ESP32 | none | none | none | yes | — |
| ESP32-S3 DevKit, 16 MB, 8 MB PSRAM | ESP32-S3 | none | none | none | yes | button |
| Guition JC1060P470C | ESP32-P4 | 1024x600 JD9165, MIPI-DSI, 154x86 mm | GT911 | ES8311 | yes | display, touch; only started: sound |
| Guition JC4827W543C | ESP32-S3 | 480x272 NV3041A, QSPI, 95x54 mm | GT911 | I2S amplifier | yes | touch; only started: display, sound |
| Guition JC8012P4A1C | ESP32-P4 | 1280x800 JD9365, MIPI-DSI, 217x136 mm | GSL3680 (firmware embedded by the program) | ES8311 | yes | display, touch, sound |
| NodeMCU ESP-32S V1.1, 38 pins | ESP32 | none | none | none | yes | — |
<!-- boards:end -->

The last column comes from the `checked` entries of level `hardware` in each `board.json`: the parts a unit of
the board was seen, felt or heard working. "Only started" means no errors in the log, the result not judged. A variant
does not take the checks of its base.

A module is wired to a board in a board of the program, in its `components/local-boards/`: the editor writes one
for a kit with modules, and [examples/local_boards](examples/local_boards) has one written by hand, a round display
on QSPI and a 2004 character LCD on I2C. See [docs/en/modules.md](docs/en/modules.md).

The GSL3680 of the
10.1-inch board keeps no firmware of its own, and the vendor's array carries no
licence to redistribute: the program embeds it, see
[docs/en/touch-firmware.md](docs/en/touch-firmware.md); without it the board
builds and runs with its touch off.

## The editor

The editor chooses a board and the parts for a device: the roles it needs (a display, a reader, a sensor), the kits that
fit with their wires, levels and prices, and what is not known; then it writes the project. In the folder of a
project, `python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve` prints its link; given to an agent over MCP
(`boards_mcp.py --install`), the editor has a dialog with the model too. See [tools.md](docs/en/tools.md#the-editor).

## Documentation

[Getting started](docs/en/getting-started.md), [choosing a board](docs/en/choosing-a-board.md),
[moving a program with boards of its own](docs/en/moving-a-program.md), [the API](docs/en/api.md),
[modules](docs/en/modules.md), [the touch firmware](docs/en/touch-firmware.md), [the radio](docs/en/radio.md), [calibration](docs/en/calibration.md),
[the tools](docs/en/tools.md), [the data format](docs/en/data-format.md), [how it works](docs/en/how-it-works.md),
[adding a board](docs/en/adding-a-board.md). In Russian: [docs/ru/](docs/ru/).

## How it differs from esp-bsp and esp_board_manager

[espressif/esp-bsp](https://github.com/espressif/esp-bsp) describes Espressif's own boards around LVGL: every manifest
pulls `lvgl` and `esp_lvgl_port`, and the display comes as an LVGL object.
[espressif/esp_board_manager](https://github.com/espressif/esp_board_manager) describes boards in YAML and generates
initialisation code into the project, with a board selected by `idf.py bmgr`. This component is meant for any board
and any library. Today it starts DGX, DGX-DI and hd44780 of its author, the drivers of Espressif for sound, the touch
panels and the radio beside the chip, and the XPT2046 driver of atanisoft. For the other parts the editor names the
libraries a program takes itself. Where a library of the author competes for a chip, the libraries of that chip are
read in audits; the others are described from their own documentation and not checked. Other platforms, Arduino among
them, are planned. It differs in how it works. A board is data a script checks: pins, buses, devices, a calibration
measured on the board, and where each fact comes from; a board of a program is described the same way, beside the
program. The display is one peripheral among others. A library is described by chip in `catalog/libraries/`, what it
does with each chip and what its versions require, so DGX, LVGL through DGX-LVGL and other libraries come in through
adapters on the same terms. The editor and its solver choose a board and the parts for a task from those facts. Beside the boards of the catalog
in the table above, the editor offers boards imported from other descriptions, marked as such. What it takes from esp-bsp is the mechanism of `components/bsp_selector`: one Kconfig
choice, hidden symbols beside it, manifest rules on them.

## Status

The versions and what changed in each are in [CHANGES.md](CHANGES.md). CI builds every board of the catalog under
ESP-IDF 5.5 and 6.1, each board on the older versions a range of a library takes (the oldest, and the newest of each
older line), and a board of a program with a display and a 2004: the jobs of `.github/workflows/build.yml`.

The `checked` entries say how each part was tried, each with its date: `examples/hello_board` and
`examples/hello_lvgl` under ESP-IDF 6.1, the handwritten clock moved onto the component, probes of DGX on the bench.
The 2004 module showed its text on `esp32_devkit` as the base of a board of a program that wires its I2C: the catalog
board opens no bus to a module. The display module `tft153_st77916` ran on `esp32s3_devkit` as a board of a program,
and its picture was seen.

## How the repository is built

For those who change the component, not for a program that uses it.

```
catalog/boards/<board>/board.json         the board: the only source of truth
catalog/devices/, catalog/mcu/            what its chips are, under it
catalog/modules/<module>/module.json      a module: parts on a small board of their own, wired to a board by a program
catalog/libraries/                        what each library does with each chip, and what its versions require
catalog/boards/<board>/sdkconfig.defaults what its chip, memory and flash need; the lines that choose it
boards/<board>/<board>.c, board.cmake  the glue, generated from the data and committed
boards/boards.cmake, Kconfig           generated too, as are the dependencies of idf_component.yml
include/boards.h                       what a program asks for, by kind
src/                                   the core: board_info, the shared I2C and SPI, the sound task, the firmware hook
adapters/<owner>__<name>/              the code for each library, its public header in include/
radio/                                 the programs of the step of the flash: the firmware of the radio, its update program
tools/resolve.py, rules.py             a board as the data says it, with what it extends and its chips; the engine of the rules
tools/boards_gen.py                    data -> glue, Kconfig, lists, manifest rules, README tables
tools/check_format.py                  the schema, the rules and their cases in test/format/
tools/check_boards.py                  the generated is what the data says; pins do not collide; the API holds
tools/board_pins.py                    the map of a board's pins and its tree
tools/board_select.py                  choose the boards of a project: their defaults, presets and locks
tools/board_radio.py                   the step of the flash that keeps the radio beside the chip at the program's esp_hosted
tools/board_calibration.py             a touch calibration into the data of a board, from the log of DGX-DI
tools/board_project.py                 a new project without the editor, or a kit of the editor taken back
tools/boards_mcp.py, project_writer.py the editor beside an agent over MCP, or alone with --serve, and its writes
tools/board_bom.py                     what to buy for a product, with prices as ranges
tools/take_report.py                   a price from a GitHub issue, into the catalog
tools/update_rates.py                  the exchange rates of the catalog, from the ECB
tools/import_libraries.py              the list of known libraries by the chips they name, beside the records
tools/sync_versions.py                 the versions of a library in the registry and its tags, into its record
tools/audit.py                         what a reading of a library found, kept beside its record
tools/import_*.py, make_mcu.py         imported/ from other descriptions; the facts of a chip from ESP-IDF
tools/vscode_env.py                    the settings of VS Code a project of boards needs
imported/                              boards, modules and chips taken from other descriptions, marked as such
editor/                                the editor: what to build, a kit, a project; and edits of the catalog. Any static server from the root, then /editor/
examples/hello/                        the program of getting started, as the registry hands it out
examples/hello_board/                  the smallest program, built for every board in CI
examples/hello_lvgl/                   LVGL through DGX-LVGL, built in CI for every board with a graphics display
examples/local_boards/                 a board and a module of the program itself, in components/local-boards/
examples/multi_board/                  one program built for two boards of different chips, by presets
examples/sound_level/                  how loud the speaker of a board is at each level, heard on the board
examples/board_report/                 the report of a new board, for its first entry in the catalog
test/                                  the cases of the checks, and fake headers to compile every glue on the host
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
