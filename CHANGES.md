# CHANGES

## 0.1.1 (not released yet)

- The computer has a touch, the mouse over its window, only when the board it shows has one: `board_select.py` writes
  `CONFIG_BOARD_HOST_TOUCH` from the data of that board, and DGX-DI comes only then. Before, it had one always, and a
  computer that showed a board with no touch took DGX-DI nobody asked for.
- The page writes a computer for the board of the program it writes, `host_<project>_<board>`, when the project has a
  computer for the board itself: it shows only what is on the canvas, and it becomes current in place of the old one,
  which stays. The computer showed the whole board before, its touch among the rest.
- A configuration of a project VS Code works on adds the ESP-IDF extension and clangd to the recommendations of
  `.vscode/extensions.json`, after those it has: the ESP-IDF extension sets clangd up, and nothing reads that without
  the clangd extension.
- The examples name their colors by `dgx_colors.h`, packed by `dgx_rgb_to_16`, the depth most displays take.
- The quick start names the project before the board, says that clangd needs its extension and, on ESP-IDF 6.1, the
  headers of clang, which its package lacks, why the debug of the ESP-IDF extension asks for a build of the computer
  again and again, and to close the old terminals of ESP-IDF after a change of the board.

## 0.1.0 (2026-11-08)

- The computer is `host_<board>`, one for each board it shows: `board_select.py host --as cyd_s028r --as jc1060p470c .`
  makes `host_cyd_s028r` and `host_jc1060p470c`, each with its file of defaults, preset, lock and build directory, so
  they build and run side by side. A project of 0.0.7 changes one line of its `CMakeLists.txt`,
  `if(BOARD STREQUAL "host")` to `if(BOARD MATCHES "^host_")`: `board_select.py` says so and writes nothing before.
  Then `board_select.py --again .` renames `sdkconfig.defaults.host` and `dependencies.lock.host`, and the computer
  stays the current board if it was. The `sdkconfig` the first `reconfigure` left in the folder of the project goes.
- The ESP-IDF extension of VS Code follows the current board: `board_select.py`, and the page when it writes, set
  `idf.customExtraVars.IDF_TARGET` and `idf.sdkconfigFilePath` (`build/<board>/sdkconfig`) in `.vscode/settings.json`,
  which the extension reads when it starts and gives new terminals as `IDF_TARGET`, and `idf.buildPath`, `build/<board>`,
  where its build goes with no project configuration chosen; till then `unset IDF_TARGET` in such a terminal. A
  configuration with no `BOARD` in a project with presets of `board_select.py` stops before the compiler checks, as the
  build of the extension with no project configuration once failed at the compiler of the computer. Before, the
  extension took the target of the `sdkconfig` in the folder of the project, which the first `idf.py reconfigure` left
  for no board and for esp32, and `idf.py` refused a board of another target.
- The page writes a project whose boards `board_select.py` chose: a board chosen by its name alone counts as the card of
  that board, and a file that is what `board_select.py --again` makes of the project is the component's to replace.
- A configure with no board, as the first `idf.py reconfigure` of a new project, keeps its `sdkconfig` in `build/`. In
  the folder of the project that file, of esp32, stopped the first build of the computer in a terminal of the ESP-IDF
  extension: until a board has a build, `idf.py` checks `IDF_TARGET` against the target of `<project>/sdkconfig`, not
  against the preset.
- The recipes take the component as `>=0.1.0`.

## 0.0.7 (2026-11-07)

- A new project comes from the registry: `compote project create-from-example -p my_project jef-sure/boards:hello`.
  `examples/hello` is the project the page and `tools/board_project.py` make, filled for the registry: it builds for the
  computer, its program is `main/main.c`, and its `.gitignore` keeps out `build/`, `managed_components/`, `sdkconfig`,
  the clangd index `.cache/` and `.vscode/`. `tools/check_format.py` compares the two, and `--fix` writes the example.
  `main/idf_component.yml` of a new project ends with no empty line.
- CMake Tools of VS Code builds a project: each configuration writes the environment of ESP-IDF into `cmake.environment`
  of `.vscode/settings.json` (`tools/vscode_env.py`), for a project with `.vscode/` or configured from VS Code, and the
  presets name Ninja, so CMake Tools and `idf.py` share a build directory.
- A build with no `BOARD` in a project whose boards `board_select.py` made stops and names them, as `cmake` with no
  preset builds, the ESP-IDF extension of VS Code with no project configuration among them. The CMake of a new project
  stops `cmake` run outside ESP-IDF with what to do.
- On an ESP32 a program starts every part before any other work: both SPI hosts share one DMA, and setting a host up
  resets it, so a transfer on the other host breaks. `hello` started the touch after it drew, and the end of the band
  reached the CYD wrong; `hello` and `hello_board` start every part first, and the glue of an ESP32 board with SPI buses
  and `api.md` say why.
- The page: a kit shows the parts of its board that answer the blocks, with their buses and lines on the board, and what
  a switch or a solder bridge sets. The boards of the project count as ones the person has, and the current one has a
  card of its own. The palette shows the parts of the selected board; one goes on the canvas with its variant and the
  answers its data gives, as the diagonal and the shape of a display, so another board is asked for the same. A page
  opened as a file names the command that serves it. The server of the page asks the browser to fetch every file again.
- One `boards_mcp.py --install` serves every project: a server started in a project with its own copy of the component
  in `managed_components/` hands over to that copy, so the catalog and `board_select.py` are of the version the project
  builds with.
- `LICENSES.md` says what is not under MIT. The breadboard drawings of the imported Fritzing parts, under CC BY-SA 3.0,
  are gone, with `tools/import_pictures.py`.
- The quick start follows the path of a beginner in VS Code: the project from the registry, the computer, the board,
  Git and GitHub, and what not to do.

## 0.0.6 (2026-11-07)

- A graphics display can be on I2C: the glue puts it on the board's bus with `dgx_i2c_init_on_bus`, and the master of
  the bus comes from `board_glue_i2c`, so other parts can share it. A driver with no orientation call starts its panel
  as it is, and the generator refuses another orientation for it.
- The boards take DGX 0.10.12, which turns the SSD1306, SSD1309 and SH1106. The catalog describes DGX 0.10.12: SSD1322
  came in 0.10.6, and the ST7789 of 76x284 and 284x76.
- SSD1306 is in the catalog and starts through DGX. `config.external_vcc` says when the high voltage of an OLED comes
  from outside.
- A library lists the glasses it takes for a chip in `panels`, by size and by the name it gives each; several can share
  a size, as the SSD1322 256x64 of Newhaven and of ZJY. A display names its own in `config.libraries`, the page offers
  those of its chip and size, and with none named it gets the first of its size. The DGX entries of SSD1306, SH1106,
  SSD1309, SSD1322 and ST7789 have them; the init calls take `{panel}`, and `supports.resolution` is gone.
- `board_display.mm_w` and `mm_h` and `BOARD_MM` are whole millimetres, rounded, where the data has fractions.
- The catalog describes DGX-DI 0.1.5, whose mouse on the computer is a touch, and hd44780 0.1.3. The list of libraries
  says the version each record describes, and the checks see when it does not.
- New boards:
  - the ESP32 DevKit with USB-C and a CH340, `esp32_devkit_usb_c`, a variant of `esp32_devkit`;
  - the ESP32-C3 with a 0.42-inch 72x40 OLED, `esp32_c3_oled_042`;
  - the ESP32 with a 0.96-inch 128x64 OLED, yellow on its top 16 rows, `esp32_oled_096`;
  - the NodeMCU ESP-32S V1.1 of 38 pins in the layout of the ESP32-DevKitC, `nodemcu_esp32s`;
  - the ESP32-C6 Super Mini with its charger for a cell, `esp32_c6_supermini`;
  - the ESP32-WROVER-DEV with 8 MB PSRAM and an OV2640 camera, `esp32_wrover_dev`.
- A camera on a parallel port: the catalog describes esp32-camera 2.1.8 and its sensors, the OV2640, and the OV2640 on a
  24-pin ribbon as a module. The component does not start the camera; a program takes its pins from the board:
  `board_bus_get` gives a list of lines by number, as `data0` to `data7` of `dvp.dvp0`. Every line of a DVP port is an
  input of the chip, so GPIO 34 to 39 of an ESP32 can carry them.
- Photos of the S3 DevKit, the front of the C3-Zero, the three Guition boards and the CYD.
- The recipes take the component as `>=0.0.6`.

## 0.0.5 (2026-11-06)

- On the computer the window is the glass of the display of the board shown, turned as the board is held, with the
  screen at the orientation the board starts with: `board_display_init` gives the width, the height and the
  orientation it gives on the board. The title of the window tells the time on the bus of that board when it is SPI or
  QSPI, and none is counted for another. The boards take DGX 0.10.11: the turn of the window came in 0.10.9, its keys
  and a window on no bus in 0.10.11.
- On the computer a task asks the source of the sound, as on a board; the audio thread of SDL asked it before.
- On the computer the flash of a program that has partitions is kept in `build/host/flash.bin` between runs, while the
  partition table of the build is the one it has: NVS keeps what it was given. ESP-IDF made a new file in `/tmp` at
  each run and left it there.
- A sound may have `mixer_volume` in its data, the level of samples in percent of full scale heard comfortable on the
  speaker of the board, and `board_sound_t` gives it to the program (0 when the data has none).
  `examples/sound_level` plays a tone at levels from 5 to 100 percent to hear it.
- The JC8012P4A1C has its level, 50 percent, heard on the board.
- The level the person chose last is kept in NVS by `board_sound_volume_keep`, and `board_sound_init` gives it at the
  next start before the level of the data: how loud is right depends on the room. The component sets NVS up when the
  program has not.
- A program finds a button by its name, `board_button_find`. A button that controls a program has a name of a gamepad,
  `up`, `down`, `left`, `right`, `a`, `b`, `start`, `select`. On the computer the buttons of the board shown and those
  of a gamepad are keys, WASD and the arrows among them; CI presses them by a script of keys.
- The recipes take the component as `>=0.0.5`.

## 0.0.4 (2026-11-06)

- A build whose configuration did not choose the board `BOARD` names stops at the configure with a message: on ESP-IDF
  6 the form `-B ... -D BOARD=<board>` took the chip of the preset `default` and built no board with no error, and so
  did an `sdkconfig` of another board in the build directory. CI checks it.
- On the computer the touch panel is the mouse: pressed on the window it is a finger on the glass, read through
  `board_dgx_di_pointer()` as on a board, with no calibration, and it turns with the display. This takes DGX-DI 0.1.5,
  the first version that builds for the linux target, and the boards take that version too. CI checks that the touch
  of `hello_board` starts on the computer.
- The page says what of the price of a kit is the board and what the parts, on the card and in the README of a
  project.
- The page lists the boards of the presets it has no kit for, those a command named and those whose kit does not fit
  the answers now, each with its radio, and opens a project with the current board its presets have.
- `board_select.py` writes the current board it chooses into `selection.json` too, and records it in the presets: a
  current board chosen on the page is taken in a project made by command, and one a command chose can be changed back
  on the page.
- The recipes take the component as `>=0.0.4`.

## 0.0.3 (2026-11-05)

- On the computer, the board `host`, the display is a window of DGX: the program draws on it through
  `board_dgx_screen()` as on the board it shows. This takes DGX 0.10.8, the first version that builds for the linux
  target, and the boards take that version too. The display is started from `app_main` or from a task with 48 KB of
  stack left; `board_select.py host` gives `app_main` 128 KB. The computer has no touch until DGX-DI builds for the
  linux target.
- CI builds `hello_board` for the computer under ESP-IDF 5.5 and 6.1, runs it with no screen and checks the picture of
  its window.
- The description of the component names no libraries, and the README puts the note on conditional dependencies in bold.
- The recipes take the component as `>=0.0.3`.

## 0.0.2 (2026-11-05)

- One example comes with the component from the registry, `hello`, the program of the quick start, and it builds as
  the registry hands it out. The examples of 0.0.1 took the component from a clone and did not configure.
- The recipes take the component as `>=0.0.2`: a caret on a version 0.0.x would take that version alone.
- The README says that every dependency but ESP-IDF is conditional: a build downloads only what the chosen board
  needs, which the list of the registry cannot show.
- `board_select.py` names the version of a copy from the registry in the files it writes; it wrote `?`.

## 0.0.1 (2026-11-05)

The first release. The boards a program runs on are described once, as data; the component sets the hardware of the
chosen board up, and the program asks for its parts by kind, never by the name of a board. Ten boards, the page that
chooses a board and the parts for a device and writes the project, and the tools around them: see the README and the
[quick start](docs/en/quick-start.md).

Known:

- The GSL3680 of the JC8012P4A1C keeps no firmware of its own, and the array of its maker has no licence to give away:
  the program embeds it, see `docs/en/touch-firmware.md`. Without it the board builds and runs with its touch off.
- On the computer the window stays black and there is no touch until DGX and DGX-DI build for the linux target.
- The camera is data only: the component does not start it.
