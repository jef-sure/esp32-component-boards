# Choosing a board for a project

The board is named once, on one command line. Everything else follows.

## A new project

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards>=0.0.4"
```

`>=0.0.4`, not `^0.0.4`: the component manager reads a caret on a version 0.0.x as that version alone, and a later
one would not be taken. What a build took stays in the lock of each board. A commit not published yet is taken from
git, at that commit, so that a build gives the same tomorrow:

```yaml
# main/idf_component.yml
dependencies:
  jef-sure/boards:
    git: https://github.com/jef-sure/esp32-component-boards.git
    version: <a commit>
```

In `CMakeLists.txt`, before `project.cmake` is included, read the defaults of the
board the preset names before the project's own, and give each board its own lock
of the components beside the project:

```cmake
cmake_minimum_required(VERSION 3.22)
# BOARD=<board>, which the preset of a board sets, builds with sdkconfig.defaults.<board> that board_select.py writes,
# then with the program's own sdkconfig.defaults when it has one. A -D SDKCONFIG_DEFAULTS=... on the command line wins.
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS AND BOARD)
    if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
        message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} . of jef-sure/boards")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(hello)
```

`main/CMakeLists.txt` names nothing for the component: the component manager makes
what `main/idf_component.yml` names a requirement of `main`, `jef-sure__boards` by its
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

`board_select.py` writes `sdkconfig.defaults.cyd_s028r`: the command that made it,
then the board's `sdkconfig.defaults` from the component's data. Its first settings are
`CONFIG_IDF_TARGET="esp32"` and `CONFIG_BOARD_SELECT_CYD_S028R=y`; the rest is what
the chip, the memory and the flash need. ESP-IDF takes the target from the
first file of `SDKCONFIG_DEFAULTS` that names one, so no `idf.py set-target`
is needed, and the menu *Boards → Board the program runs on* shows the board
chosen. It writes `CMakePresets.json` too: the preset `cyd_s028r`, which sets `BOARD`
and builds in `build/cyd_s028r` with its `sdkconfig` there, and the preset `default`,
a copy of it, which `idf.py` takes when no preset is named. The `build/` and
`sdkconfig` the first `reconfigure` leaves are not read after it.

ESP-IDF 5 does not read presets; the board is named on the command line:

```sh
idf.py -B build/cyd_s028r -D SDKCONFIG=build/cyd_s028r/sdkconfig -D BOARD=cyd_s028r build
```

Commit `sdkconfig.defaults.<board>`, `CMakePresets.json` and `dependencies.lock.<board>`:
a fresh clone reads them before the component is downloaded.

## A module

A module wired to a board makes a board of the program: `components/local-boards/boards/<board>/board.json`
names the board it stands on and its modules with their buses and pins. The page writes it for a kit with
modules; `examples/local_boards` has one written by hand. `board_select.py <board> .` takes it as a board of
the catalog and makes its glue beside its data. A board of the program changed later to need another library
takes it once its `dependencies.lock.<board>` and `build/<board>` are removed: the component manager solves a
lock again when the manifest changes, not when the board does. See [modules.md](modules.md).

## Another board

Another board named joins the boards of the project and becomes the current one:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c .
idf.py build flash monitor            # jc4827w543c, in build/jc4827w543c
idf.py --preset cyd_s028r build       # the board before it, still there
```

Each board builds in a directory of its own, with its own target and `sdkconfig`, so
a board of another chip needs no `set-target` and nothing is cleaned. A board does not
change in the same build directory: the chip of a build directory is fixed in its
CMake cache before `CMakeLists.txt` is read, so a line there could not choose another
chip. A board is taken out by removing its `sdkconfig.defaults.<board>`, then
`board_select.py --again .` writes the presets of the rest; its `build/<board>` and
`dependencies.lock.<board>` are not read any more.

## Several boards

Several boards are named at once too:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r jc1060p470c .
idf.py build                          # ESP-IDF 6: the first board, cyd_s028r
idf.py --preset jc1060p470c build     # another
```

`board_select.py` writes `sdkconfig.defaults.<board>` for each, with the lines of
the revision of its chip, and the presets of every board of the project: those it had,
then those named, in the order named. Each board has its lock of the components,
`dependencies.lock.<board>` beside the project, so the boards do not disturb each
other; the versions of the components stay as they were solved. The first time,
`board_select.py` copies the `dependencies.lock` of the project to each board, so a
project made before keeps its versions; then each board reads its own, and
`dependencies.lock` is not read. One lock for two boards would keep the solution of the
first: the component manager solves again when the manifest changes, not when the
board does. The files of the catalog are not read directly: the lines of the revision
are only in what `board_select.py` writes.

`default` is the current board, the first named unless `--current <board>` says
another: `idf.py build`, `flash` and `monitor` take it with no more words.
`idf.py --preset <board>` or `IDF_PRESET=<board>` in the environment takes another for
one command; `board_select.py --current <board> .` makes another current and changes
nothing but `default`, so the boards keep their order, and the `current` of `selection.json` when the project has one. The extension of ESP-IDF for
VS Code shows the presets as project configurations: *ESP-IDF: Select Project
Configuration* chooses one, and the status bar names it.

The page does the same from its kits: *add to the project* on a card puts a kit among the boards of the project, the
radio beside each makes one current, and *make the project of these boards…* writes them. It writes `selection.json`,
whose `boards` keep the order they were added, `current` the current one and `name` the name of the project, a board of the program
`<project>_<board>` for a kit with a project of its own, and `sdkconfig.defaults.<board>` of each with the command
that makes it in its first line: `board_select.py --again .` makes the rest, the defaults, the presets and the glue.
Opened from `tools/boards_mcp.py`, the page writes through it and the server runs `--again` itself, so the project
builds at once; it also starts from the `selection.json` of the project, to add a board. A board of the presets that
the page has no kit for, one a command named or one whose kit does not fit the answers now, is listed among the boards
of the project with its radio and stays in the project.

A `CMakePresets.json` that `board_select.py` did not write is not touched: the
command says so, and the presets are added by hand. `board_select.py --again .` makes
every file again by the command in its first line, and the presets, in their order and with
their current board: the first time, as `selection.json` has them. The presets record the
current board they were made with, and each command that changes it writes it into the `current` of `selection.json`
too, so a current board the page changes since is taken, and one a command chose stays. The page opens a project with the order and the current board of
its presets. ESP-IDF reads the defaults only into a new `sdkconfig`: to take what changed,
remove `build/<board>/sdkconfig`. A build whose configuration did not choose the board `BOARD` names stops at the
configure and says which board it chose and for which chip: on ESP-IDF 6 the form `-B ... -D BOARD=<board>` takes the
chip of the preset `default`, and an `sdkconfig` of another board in the build directory keeps its board.

A `-D SDKCONFIG_DEFAULTS=...` on the command line wins over both: the CMake
snippet above only sets the variable when none is given.

## The computer

A program runs on the computer as on a board: the board `host`, the linux target of ESP-IDF, a window of DGX as large
as the display of the board it shows.

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py host --as jc8012p4a1c .
idf.py -B build/host -D SDKCONFIG=build/host/sdkconfig -D BOARD=host build
build/host/<project>.elf
```

Its log comes as it is written in a terminal; through a pipe it is buffered, and `stdbuf -o0 build/host/<project>.elf`
gives it at once.

`board_select.py` writes `sdkconfig.defaults.host` beside the files of the boards of the project, and the CMake of the
skeleton builds only `main` and what it asks for the computer. `BOARD_PIXELS` and `BOARD_MM` are those of the board
shown. The window is a host screen of DGX (`dgx_host_screen_init`, DGX 0.10.8 and later): `board_dgx_screen()` draws
on it as on the panel of the board, and its title tells how long the bytes sent would take on an SPI bus of 40 MHz and
how much memory the program and DGX hold. The task that starts the display shows the window in its waits (`vTaskDelay`), so the
display is started from `app_main` or from a task with 48 KB of stack left; `sdkconfig.defaults.host` gives `app_main`
128 KB (`CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`, in words of 8 bytes). After `app_main` returns the window stays until
it is closed; a window that is closed ends the program. The touch panel is the mouse: pressed on the window it is a
finger on the glass (`dgx_di_host.h`, DGX-DI 0.1.5 and later), read through `board_dgx_di_pointer()` as on a board, with
no calibration, and it turns with the display. The computer has the sound, by SDL. It takes SDL2 and libbsd of the computer (`libsdl2-dev`, `libbsd-dev`) and runs on
Linux; Windows is not a target of ESP-IDF.

## What comes with the choice

- The DGX drivers of the board's panel: `select`s of the choice in the
  component's Kconfig (`CONFIG_DGX_ENABLE_DSI`, `CONFIG_DGX_ENABLE_JD9165`, ...).
- The other parts: rules in the component's `idf_component.yml` on hidden
  symbols beside the choice. A build for the CYD S028R gets `atanisoft/esp_lcd_touch_xpt2046`
  and nothing of the GT911 or the ES8311; a build with *None* chosen gets none
  of DGX, and links: every function of `boards.h` returns `false`.
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

## What stays with the program

The board brings what its hardware needs: the drivers of its panel and, for two displays shown as one,
`CONFIG_DGX_ENABLE_VSCREEN` and `CONFIG_DGX_ENABLE_VSCREEN_2H`. What the program uses for itself stays in its own
`sdkconfig.defaults`, read after the board's, and is the same on every board: the tick of FreeRTOS, the optimization,
a feature of a library it calls. The game of dgx-ge draws into a screen in RAM and steps its loop by milliseconds, so
its own defaults say

```
CONFIG_FREERTOS_HZ=1000
CONFIG_COMPILER_OPTIMIZATION_PERF=y
CONFIG_DGX_ENABLE_VSCREEN=y
```

where the board directories of dgx-ge used to repeat `CONFIG_DGX_ENABLE_VSCREEN` for each board. A line of the
program's file that the board's file also sets wins, as the later one.

## Without board_select.py

The file it writes is `catalog/boards/<board>/sdkconfig.defaults` with the lines of the
revision of its chip and those of each module. Any other way of getting those lines into
`SDKCONFIG_DEFAULTS` works: a path into `managed_components/` or into a checkout of the
component beside the project, or copying the lines into the project's own
`sdkconfig.defaults`. And the menu works as a menu: `idf.py menuconfig`, *Boards*,
choose; but then the chip's settings (PSRAM mode, flash size, chip revision) are yours
to set too, which is what the defaults file saves you from.

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
