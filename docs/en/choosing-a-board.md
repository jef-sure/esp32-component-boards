# Choosing a board for a project

The board is named once, on one command line. Everything else follows.

## A new project

```sh
idf.py create-project hello && cd hello
```

The component is not in the registry yet: take it from git, at a commit, so that
a build gives the same tomorrow. Once it is published, `idf.py add-dependency
"jef-sure/boards^0.0.1"` will take its place.

```yaml
# main/idf_component.yml
dependencies:
  jef-sure/boards:
    git: https://github.com/jef-sure/esp32-component-boards.git
    version: <a commit>
```

In `CMakeLists.txt`, before `project.cmake` is included, read the board's
defaults before the project's own, and keep the lock of the components in the
build directory:

```cmake
cmake_minimum_required(VERSION 3.22)
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS)
    if(BOARD)
        if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
            message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} ... . of jef-sure/boards")
        endif()
        set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD};sdkconfig.defaults")
    elseif(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
        set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
    endif()
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_BINARY_DIR}/dependencies.lock)
project(hello)
```

`BOARD` chooses among several boards (see below); with none, the one file
`sdkconfig.defaults.board` is read.

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
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
idf.py build flash monitor
```

`board_select.py` writes `sdkconfig.defaults.board`: the board's
`sdkconfig.defaults` from the component's data. Its first lines are
`CONFIG_IDF_TARGET="esp32"` and `CONFIG_BOARD_SELECT_CYD_S028R=y`; the rest is what
the chip, the memory and the flash need. ESP-IDF takes the target from the
first file of `SDKCONFIG_DEFAULTS` that names one, so no `idf.py set-target`
is needed, and the menu *Boards → Board the program runs on* shows the board
chosen.

Commit `sdkconfig.defaults.board` when the project is for one board; a project for
several keeps `sdkconfig.defaults.<board>` instead (see below).

## A module

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc1060p470c --module lcd2004_pcf8574 .
```

The module's defaults are appended after the board's: they turn its option on
in the menu (`CONFIG_BOARD_MODULE_LCD2004_PCF8574=y`), which brings hd44780 in
and compiles the module's glue beside the board's. See [modules.md](modules.md).

## Changing the board

ESP-IDF reads `sdkconfig.defaults*` only when it creates a new `sdkconfig`. To
move a project to another board:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c --reset .
```

`--reset` moves the old `sdkconfig` to `sdkconfig.old` and names the next
command. A build directory keeps the target of its chip in its CMake cache, which
is read before any defaults: when the new board has another chip, the command is
`idf.py set-target <target>`, which cleans the build and makes a new `sdkconfig`
from the defaults, then `idf.py build`; with the same chip it is `idf.py
reconfigure build`. Without `--reset`, `board_select.py` writes nothing and fails
when the `sdkconfig` is made for another board: a build would give that board.

## Several boards

A project built for several boards keeps a file of defaults and a build directory
for each:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r jc1060p470c .
idf.py -B build-cyd_s028r -D SDKCONFIG=build-cyd_s028r/sdkconfig -D BOARD=cyd_s028r build
idf.py -B build-jc1060p470c -D SDKCONFIG=build-jc1060p470c/sdkconfig -D BOARD=jc1060p470c build
```

`board_select.py` writes `sdkconfig.defaults.<board>` for each, with the lines of
the revision of its chip, and prints these commands. Commit those files: a fresh
clone reads them before the component is downloaded. Each build directory has its
own target, `sdkconfig` and lock of the components, so the boards do not disturb
each other. The files of the catalog are not read directly: the lines of the
revision are only in what `board_select.py` writes.

A `-D SDKCONFIG_DEFAULTS=...` on the command line wins over both: the CMake
snippet above only sets the variable when none is given.

## What comes with the choice

- The DGX drivers of the board's panel: `select`s of the choice in the
  component's Kconfig (`CONFIG_DGX_ENABLE_DSI`, `CONFIG_DGX_ENABLE_JD9165`, ...).
- The other parts: rules in the component's `idf_component.yml` on hidden
  symbols beside the choice. A build for the CYD S028R gets `atanisoft/esp_lcd_touch_xpt2046`
  and nothing of the GT911 or the ES8311; a build with *None* chosen gets none
  of DGX.
- The glue of the chosen board, compiled into the component by
  `CONFIG_BOARD_<BOARD>`; its `board.cmake` names the components it needs.
- The size of the primary display for the program's CMake, as shown: `BOARD_PIXELS`
  (width and height) and `BOARD_MM` (in millimetres, `0 0` when the data has no size),
  set by the component's `project_include.cmake`. `main/CMakeLists.txt` has them before
  and after `idf_component_register`; in the early expansion of the requirements they
  are empty, and so they are for a board with no pixel display. A game hands them to DGX
  once: `dgx_fonts_board(PIXELS ${BOARD_PIXELS} MM ${BOARD_MM})`.

The component manager evaluates its rules against the `sdkconfig`. When the
project has none yet, the first `idf.py build` generates it from the defaults,
sees that the set of dependencies changed (*Direct dependencies have changed,
solving dependencies* in the log) and resolves them again by itself, in the
same run. One `idf.py build` is enough; the log shows which optional
dependencies were skipped.

## Without board_select.py

The file it writes is a copy of `catalog/boards/<board>/sdkconfig.defaults`. Any
other way of getting that file into `SDKCONFIG_DEFAULTS` works: a path into
`managed_components/` or into a checkout of the component beside the project,
or copying the lines into the project's own `sdkconfig.defaults`. And the
menu works as a menu: `idf.py menuconfig`, *Boards*, choose; but then the
chip's settings (PSRAM mode, flash size, chip revision) are yours to set too,
which is what the defaults file saves you from.

## Chip revisions

The ESP32-P4 boards come with chips of revision 1.x or 3.x, and a build for
one does not start on the other. The revisions differ in what they can do: 360
or 400 MHz of the CPU, 200 or 250 MHz of the PSRAM, and a MIPI-DSI panel depends
on that PSRAM. `mcu.revision` of the board names the revision it was measured on,
and `tools/board_select.py` writes the lines of that revision from `catalog/mcu/`.
A board with another chip takes `--revision`. Check your chip (`esptool.py chip_id`
or the boot log) before the first flash:

```sh
python3 tools/board_select.py jc1060p470c --revision 3.1 .
```
