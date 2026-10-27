# Choosing a board for a project

The board is named once, on one command line. Everything else follows.

## A new project

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards^0.0.1"
```

In `CMakeLists.txt`, before `project.cmake` is included, read the board's
defaults before the project's own:

```cmake
cmake_minimum_required(VERSION 3.22)
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(hello)
```

In `main/CMakeLists.txt`, `PRIV_REQUIRES jef-sure__boards`: the component's
directory under `managed_components/`. (A checkout of the component taken by
`override_path` or `EXTRA_COMPONENT_DIRS` is named after its own directory
instead, and the component manager matches a dependency to a local component
only when that directory is called `boards` or `jef-sure__boards`. The example
inside this repository therefore takes the component by `EXTRA_COMPONENT_DIRS`,
names no component in `main`, and lets `main` depend on every component of the
build, as ESP-IDF's `main` does when it names none.) Then choose the board and
build:

```sh
idf.py reconfigure            # once: downloads the component into managed_components/
python3 managed_components/jef-sure__boards/tools/board_select.py cyd .
idf.py build flash monitor
```

`board_select.py` writes `sdkconfig.defaults.board`: the board's
`sdkconfig.defaults` from the component's data. Its first lines are
`CONFIG_IDF_TARGET="esp32"` and `CONFIG_BOARD_SELECT_CYD=y`; the rest is what
the chip, the memory and the flash need. ESP-IDF takes the target from the
first file of `SDKCONFIG_DEFAULTS` that names one, so no `idf.py set-target`
is needed, and the menu *Boards → Board the program runs on* shows the board
chosen.

Add `sdkconfig.defaults.board` to the project's `.gitignore` if the project is
built for several boards; commit it if the project is for one.

## A module

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc1060p470 --module lcd2004_pcf8574 .
```

The module's defaults are appended after the board's: they turn its option on
in the menu (`CONFIG_BOARD_MODULE_LCD2004_PCF8574=y`), which brings hd44780 in
and compiles the module's glue beside the board's. See [modules.md](modules.md).

## Changing the board

ESP-IDF reads `sdkconfig.defaults*` only when it creates a new `sdkconfig`. To
move a project to another board:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543 --reset .
idf.py build
```

`--reset` moves the old `sdkconfig` to `sdkconfig.old`. Without it,
`board_select.py` writes the file and tells you the `sdkconfig` is in the way.
A project built for several boards at once keeps a build directory per board:

```sh
idf.py -B build-cyd -D SDKCONFIG=build-cyd/sdkconfig \
       -D SDKCONFIG_DEFAULTS="managed_components/jef-sure__boards/boards-data/cyd/sdkconfig.defaults;sdkconfig.defaults" build
```

A `-D SDKCONFIG_DEFAULTS=...` on the command line wins over
`sdkconfig.defaults.board`: the CMake snippet above only sets the variable
when none is given.

## What comes with the choice

- The DGX drivers of the board's panel: `select`s of the choice in the
  component's Kconfig (`CONFIG_DGX_ENABLE_DSI`, `CONFIG_DGX_ENABLE_JD9165`, ...).
- The other parts: rules in the component's `idf_component.yml` on hidden
  symbols beside the choice. A build for the CYD gets `atanisoft/esp_lcd_touch_xpt2046`
  and nothing of the GT911 or the ES8311; a build with *None* chosen gets none
  of DGX.
- The glue of the chosen board, compiled into the component by
  `CONFIG_BOARD_<BOARD>`; its `board.cmake` names the components it needs.

The component manager evaluates its rules against the `sdkconfig`. When the
project has none yet, the first `idf.py build` generates it from the defaults,
sees that the set of dependencies changed (*Direct dependencies have changed,
solving dependencies* in the log) and resolves them again by itself, in the
same run. One `idf.py build` is enough; the log shows which optional
dependencies were skipped.

## Without board_select.py

The file it writes is a copy of `boards-data/<board>/sdkconfig.defaults`. Any
other way of getting that file into `SDKCONFIG_DEFAULTS` works: a path into
`managed_components/` or into a checkout of the component beside the project,
or copying the lines into the project's own `sdkconfig.defaults`. And the
menu works as a menu: `idf.py menuconfig`, *Boards*, choose; but then the
chip's settings (PSRAM mode, flash size, chip revision) are yours to set too,
which is what the defaults file saves you from.

## Chip revisions

The ESP32-P4 boards come with chips of revision 1.x or 3.x, and a build for
one does not start on the other. Each board's `sdkconfig.defaults` is written
for the revision of the board it was measured on and says so in its comments,
with the lines to change for the other revision. Check your chip
(`esptool.py chip_id` or the boot log) before the first flash.
