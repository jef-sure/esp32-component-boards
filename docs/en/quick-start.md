# Quick start

A program on a board in a few minutes: the component sets the board up, and the program asks for its parts by kind,
never by the board's name.

You need ESP-IDF 5.5 or 6.x in the shell (`idf.py --version` answers), Python 3.9 or newer, and a board of the
[table of the README](../../README.md#the-boards) on USB. The CYD S028R (ESP32-2432S028R, 2.8-inch) is the example here;
for another board, put its name from the table in place of `cyd_s028r`.

## 1. A project with the component

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards>=0.0.6"
```

## 2. The CMake that reads the board

In `CMakeLists.txt` the line `include($ENV{IDF_PATH}/tools/cmake/project.cmake)` becomes these lines, the include among
them. They read the defaults of the board before the project's own and give each board its own lock of the
components:

```cmake
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
```

## 3. The board, once

```sh
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
```

The first command downloads the component into `managed_components/`. The second writes `sdkconfig.defaults.cyd_s028r`
(the chip, the flash, the memory and the line that chooses the board), `CMakePresets.json` (a preset that builds the
board in `build/cyd_s028r`) and the lock of the board's components. No `set-target`, no `menuconfig`.

## 4. The program

`main/hello.c`:

```c
#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    /* Start every part before drawing. On an ESP32 both SPI hosts share one DMA, and board_touch_start sets up the
     * touch's host, which resets that DMA: a picture still being sent to the display would end in wrong pixels. */
    board_display_t display = {0};
    bool            shown   = board_display_init(&display);
    if (shown) printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);

    board_touch_t touch;
    if (board_touch_start(&display, &touch)) printf("the touch: %d fingers\n", touch.fingers);

    bool pressed;
    if (board_button(&pressed)) printf("the button: %s\n", pressed ? "held" : "free");

#if CONFIG_BOARD_DISPLAY_GRAPHICS
    if (shown) {
        dgx_screen_t *screen = board_dgx_screen(&display);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0xffff);     /* white */
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, 0x001f); /* a blue band at the top */
    }
#endif
}
```

Every function of `boards.h` exists on every board; one for a part the board does not have returns `false`. The header
of DGX is for a board with a graphics display, so it is included under `CONFIG_BOARD_DISPLAY_GRAPHICS`.
[examples/hello_board](../../examples/hello_board) is the same with the sound and a character display.

## 5. Build, flash, look

```sh
idf.py build flash monitor
```

ESP-IDF 6 builds the preset of the board, into `build/cyd_s028r`. ESP-IDF 5 does not read presets:
`idf.py -B build/cyd_s028r -D SDKCONFIG=build/cyd_s028r/sdkconfig -D BOARD=cyd_s028r build flash monitor`.

The log of the CYD S028R:

```
the board: CYD (ESP32-2432S028R) (cyd_s028r), esp32
the display: 320 x 240 pixels, 58 x 43 mm
the touch: 1 fingers
the button: free
```

On the screen: white, with a blue band along the top. Hold BOOT at reset and the last line says `held`.

## Another board, or several

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c .
idf.py build flash monitor
```

The same program, on a JC4827W543C flashed so:

```
the board: Guition JC4827W543C (jc4827w543c), esp32s3
the display: 480 x 272 pixels, 95 x 54 mm
the touch: 5 fingers
the button: free
```

The board named last is the current one; `idf.py --preset cyd_s028r build` builds the other, each in its own
`build/<board>`. See [choosing-a-board.md](choosing-a-board.md).

## Without editing a file: one command, or the page

With a clone of the repository, a project is made whole, the CMake and the program among its files:

```sh
git clone --depth 1 https://github.com/jef-sure/esp32-component-boards.git
python3 esp32-component-boards/tools/board_project.py hello --board cyd_s028r
cd hello && idf.py reconfigure && python3 managed_components/jef-sure__boards/tools/board_select.py --again . && idf.py build flash monitor
```

The page chooses a board and the parts for a device and writes the project:

```sh
mkdir hello2 && python3 esp32-component-boards/tools/boards_mcp.py --serve --project hello2
```

Open the link it prints. See [tools.md](tools.md#the-page).

## A program you already have

[moving-a-program.md](moving-a-program.md): the component beside your other dependencies, the CMake lines, the boards
named once, your board code replaced by calls by kind.
