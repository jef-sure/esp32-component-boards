# Moving a program with boards of its own

A program that already runs on several boards has its own layer for them: a choice of boards in its Kconfig, a file of
defaults for each board, and code under `#if` that sets up the display, the touch panel and the button of each. This
is how such a program moves onto the component, with the handwritten clock as the example. A copy of the clock moved
this way was built and runs on the Guition JC1060P470C and the JC8012P4A1C, with touch.

## What the clock had

- `main/Kconfig.projbuild`: `choice CLOCK_BOARD` with `CLOCK_BOARD_JC1060P470` and `CLOCK_BOARD_JC8012P4A1C`, each
  selecting the DGX drivers of its panel.
- Files of defaults: `sdkconfig.defaults`, `sdkconfig.defaults.esp32`, `sdkconfig.defaults.esp32p4`,
  `sdkconfig.defaults.esp32p4.jc1060p470`, `sdkconfig.defaults.esp32p4.jc8012p4a1c` and `sdkconfig.defaults.idf5`.
  The files of the two P4 boards hold the choice of the board and the lines of the revision of the chip.
- `main/display.c` and `main/touch.c`: for each board under `#if CONFIG_CLOCK_BOARD_...`, the pins, the bus, the
  driver, the orientation, the light and the calibration of the touch panel. `main/main.c` read the BOOT pin by its
  number for each chip.
- `main/idf_component.yml`: `jef-sure/dgx`, `jef-sure/dgx-di`, and the touch driver of the 7-inch board by a rule on
  `CLOCK_BOARD_JC1060P470`.

## The steps

1. The component goes into `main/idf_component.yml` beside what the program uses itself:

   ```sh
   idf.py add-dependency "jef-sure/boards^0.1.4"
   ```

   The rule that brought the touch driver of one board goes away: the component brings the parts of the board chosen.
   What the program calls itself stays, as `jef-sure/dgx-di` for the gestures of the clock.

2. The top `CMakeLists.txt` gets the lines of [choosing-a-board.md](choosing-a-board.md#a-new-project) before
   `project.cmake` and the lock of each board after it. A line of its own goes after them, as the clock's list of
   defaults for ESP-IDF 5:

   ```cmake
   include($ENV{IDF_PATH}/tools/cmake/version.cmake)
   if(IDF_VERSION_MAJOR LESS 6)
       list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults.idf5")
   endif()
   ```

   `main/CMakeLists.txt` names nothing for it: the component manager makes the component a requirement of `main`.

3. The boards are named once:

   ```sh
   idf.py reconfigure
   python3 managed_components/jef-sure__boards/tools/board_select.py jc1060p470c jc8012p4a1c .
   ```

   This writes `sdkconfig.defaults.jc1060p470c` and `sdkconfig.defaults.jc8012p4a1c`, with the lines of the revision of
   the chip from the data, `CMakePresets.json` and a lock for each board. The files of the program for one board,
   `sdkconfig.defaults.esp32p4.jc1060p470` and `sdkconfig.defaults.esp32p4.jc8012p4a1c`, go away. A board with a chip
   of another revision is named in a command of its own, with `--revision`.

4. The choice of boards of the program goes from `main/Kconfig.projbuild`: the menu *Boards → Board the program runs
   on* holds the boards now. An option of the program that depended on a board depends on what the board has. The
   forecast of the clock is leafed through by touch, so it went from `default y if IDF_TARGET_ESP32P4` to:

   ```
   depends on BOARD_TOUCH != 0
   ```

   `BOARD_TOUCH` is an `int` symbol: a bare `depends on BOARD_TOUCH` is false for every value.

5. The code of the boards becomes calls by kind. The display of `main/display.c`, two branches of pins, buses and
   drivers, is now:

   ```c
   board_display_t board;
   if (!board_display_init(&board)) {
       ESP_LOGE(TAG, "board_display_init failed");
       return NULL;
   }
   display = board_dgx_screen(&board);
   display_bus = board_dgx_bus(&board);
   ```

   The touch panel takes `board_touch_start` and `board_dgx_di_pointer`, with the calibration the data of the board
   holds; the button takes `board_button`. The firmware of the GSL3680 of the 10.1-inch board stays the program's to
   embed, and `board_touch_firmware_set` gives it to the component before `board_touch_start`, see
   [touch-firmware.md](touch-firmware.md).

## What stays with the program

- Its own `sdkconfig.defaults`, read after the file of the board: the tick of FreeRTOS, the partition table, what its
  libraries need. A line both set takes the program's value, as the later one. The target is the one of the file of
  the board, the first file that names one.
- A file of ESP-IDF for a target, as the clock's `sdkconfig.defaults.esp32p4`, is still read after
  `sdkconfig.defaults` for that chip. `board_select.py` does not take it for a board: its first line is not a command.
- Its libraries, its fonts and the files it embeds.

## The page in the program

`python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve --project .` opens the page on the program. A
folder with a `CMakeLists.txt` gets only what the page makes: a board of the program in `components/local-boards/` for
a kit with modules, `sdkconfig.defaults.<board>`, `selection.json` and, through `board_select.py --again`, the presets
and the glue. The lines of CMake and of the manifest the program lacks are shown, to put in by hand. The page makes the
name of the project from `project()`: `handwritten-clock` becomes `handwritten_clock`, and a board of the program is
`handwritten_clock_<board>`.
