# CHANGES

## 0.2.4 (not released yet)

- New board: the Waveshare ESP32-S3-Touch-AMOLED-1.32, `esp32_s3_touch_amoled_1_32`. A round 466x466 AMOLED with a
  CO5300 on QSPI, started through DGX 0.12.4 or later; an ES8311 with a speaker header; BOOT and PWR buttons; a battery
  divider on GPIO4. Pins from the schematic of Waveshare. On the board `hello_board` shows its picture and its tone is
  heard. Its CST820 touch stays data for the program (`board_bus_get`): no library of the catalog starts that chip yet.
  On a battery the program keeps the power on with GPIO18 high, which the glue does not set yet.
- A touch whose chip no library starts as a touch is kept as data, as a display with such a chip already was, and the
  kit of the editor says the program starts it. A chip a library drives only as a display, as the AXS15231B, counts as
  not started for its touch.
- `boards_mcp.py --install` writes the skill `boards-editor` for Claude Code, as dgx-ui writes its own: the order of
  work with the editor, what the agent must not do, the questions of a display, what comes after the choice, where the
  API and the data are told, and worked cases. A skill of the same name it did not write stays as it is.
- The editor shows the builder of the pages of dgx-ui on a page of its own, "pages", when the project has dgx-ui:
  `boards_mcp.py` serves it under `/dgx-ui` through the `mounted()` of the project's own copy of dgx-ui, which reads and
  writes the project by its own rules, and the builder runs with no agent of its own. Without such a copy, or with one
  that has no `mounted()` yet, the editor is as before. Tried in headless Chrome with dgx-ui 0.1.10 of its tag (not in
  the registry yet) in a project of nine pages: the builder opens the project at once and draws its first page, with no
  error on the page; a page written through the server of boards is taken, a write from another origin and one of
  `CMakeLists.txt` are refused.
- The solver asks a graphics display for its pixels: along the short side at least and along the long side at least,
  so that a board can be chosen for pages made first, as those of dgx-ui. The sides are compared by length, as DGX
  turns a picture: a page of 480x800 fits a glass of 800x480.
- The record of DGX describes 0.12.13 and its four new displays: the CO5300 of round AMOLED panels on QSPI from 0.12.4,
  the ST7796 (ST7796S) of 320x480 panels on SPI or the 8-bit bus and the AXS15231B of the Guition JC3248W535 on QSPI from
  0.12.7, the NV3007 of 142x428 bar panels on SPI from 0.12.9. A board with one of them needs that version. No board of
  the catalog has them yet. The index of chips names DGX for the four.
- The radio beside the chip of the JC1060P470C, the JC4880P443C and the JC8012P4A1C is off until the program turns it on:
  `CONFIG_BOARD_RADIO=y` in its `sdkconfig.defaults`, or Boards in menuconfig. esp_hosted starts itself before
  `app_main()` once it is in the build, and it came with the board, so a program that never used Wi-Fi carried it: on the
  JC4880P443C `hello_board` is 201 KB smaller without it. While the radio is off, esp_hosted and esp_wifi_remote are not
  in the build, the flash step leaves the C6 alone, and `board_radio_start()` returns false and logs how to turn the
  radio on. The settings of esp_hosted move from the defaults of the board to `sdkconfig.defaults.radio` of its data:
  `board_select.py` writes them beside the board's as `sdkconfig.defaults.<board>.radio`, and the `CMakeLists.txt` of
  a project reads that file when `CONFIG_BOARD_RADIO=y`, so no Kconfig meets the settings of a library it does not have.
  With the radio on, the project keeps a lock of its own, `dependencies.lock.<board>.radio`: the component manager does
  not solve a lock again when only the configuration changed, so the radio turned on or off in menuconfig would keep
  the components of the other state. A build stops when the radio is on and esp_hosted is not there, and warns when
  the radio is off and esp_hosted is, both naming the lock to remove. A project made before this takes the new lines
  of `editor/skeleton/CMakeLists.txt`. Built on ESP-IDF 6.1 for the JC4880P443C with the radio off, on, off and on
  again in its sdkconfig, and on 5.5.5 for the JC1060P470C off and on: off has no warning and no esp_hosted, on has
  esp_hosted with the pins of the data. Not flashed.

## 0.2.3 (2026-11-22)

- A library given by `path` or `override_path` in a directory of another name, as `dgx` for jef-sure/dgx, gets its
  version for the glue: `CMakeLists.txt` finds its component by the directory the lock of the component manager gives
  for it, and stops when no component of the build is there. Before, the glue saw no version and built the calls of
  the oldest DGX of the range: the calls DGX 0.12 warns at, and the constructors of the monochrome displays in the
  order of 0.11, which compile in C and return NULL with DGX 0.12.
- The recipes take the component as `^0.2.3`.

## 0.2.2 (2026-11-22)

- DGX 0.12 is in the range: `>=0.10.12,<0.13.0`. The record of DGX describes 0.12.0, whose constructors of the SSD1306,
  SH1106, SSD1309, SSD1322 and SSD1680 take the reset line before the resolution; a call in the order of 0.11 compiles
  in C and returns NULL at run time. From DGX 0.11.1 the glue turns every display by `dgx_screen_orientation()` and
  names the glass with `DGX_`, and the adapter frees a bus by `dgx_bus_dispose()`: 0.12.0 warns at the calls named
  after a driver, the names without `DGX_` and `bus->dispose`. The window of the computer turns its display the same
  way and gets the version of DGX of its build, as a board does. CI also builds the boards with DGX 0.11.8, the newest
  of 0.11.
- DGX-DI 0.2 is in the range: `>=0.1.5,<0.3.0`. The record of DGX-DI describes 0.2.0, which requires DGX `^0.12.0`:
  a board with touch builds with DGX 0.12 through it. 0.1.7 and 0.2.0 change the keyboard and the pad, which the
  adapter does not call. CI also builds the boards with touch with DGX-DI 0.1.5 and 0.1.7, except 0.1.5 for the
  boards whose display needs DGX 0.11: it requires DGX `^0.10.10`. `tools/boards_gen.py` leaves a version out of
  that list when what it requires of another library leaves no version the board needs.
- examples/hello_lvgl asks for DGX-LVGL `^0.1.0`, which is on DGX 0.12 and DGX-DI 0.2; with `^0.0.3` it got DGX 0.11.
  The record of DGX-LVGL describes 0.1.0.
- The Sunton ESP32-8048S070C, a 7-inch 800x480 glass on the parallel RGB bus of an ESP32-S3, with GT911 touch, an
  amplifier on I2S and the BOOT button, from the schematic V1.1 of its archive and photos of a board. Its display starts through
  DGX 0.11.6, the first with the RGB bus, at a pixel clock of 33 MHz with two frame buffers in PSRAM: a contributor of
  DGX saw the board hold 33 MHz with these pins, where the demos of the vendor run 12 and 16. A build with an older DGX
  stops at `#error`. The defaults of the board set `CONFIG_SPIRAM_XIP_FROM_PSRAM`, without which every write to the
  flash spoils the picture. The touch has a placeholder calibration until it is measured on the board. Built on
  ESP-IDF 5.5.5 and 6.1 with DGX 0.11.7 of the registry; not flashed. The record imported from guition_boards 0.2.2 is
  gone: it named the controller of the glass ST7262, where the specification of the board names the EK9716. On the
  photo of the back the amplifier has 8 pins, where the MAX98357 of the schematic has 16, and the resistive touch and
  the resistor that joins INT of the touch to GPIO18 are not fitted.
- The record of DGX describes 0.11.7: the parallel RGB bus of 0.11.6 and its glass of the ESP32-8048S070. The bus takes
  its lines in a structure: a transport of a library names its type and fields in `pins`, and the glue makes a constant
  of it. The index of chips names DGX for the EK9716 and for the ST7701S, which it has since 0.11.5.
- `tools/import_board_manager.py` compares the data lines of an RGB display of a pack with the catalog: it read only
  single pins and said the pack had none of them.
- The step of the flash that keeps the radio of an ESP32-P4 board at the esp_hosted of the build works on revision 3
  of the chip: its update program, which starts from the bootloader of the program, is built with the size of the L2
  cache of the program, and panicked before its first line with another. A radio too old to tell its version gets the
  image as any other, and the step waits up to 60 s for the radio to check it. Tried on the JC4880P443C: its C6 went
  from the factory firmware to esp_hosted 3.0.10.
- The JC4880P443C was flashed with `hello_board`: the display shows its frame through DGX 0.11.5 with two frame
  buffers. Its touch is calibrated on the board, three rounds of nine targets: 4.9 pixels off on average and 9 at
  worst with the calibration, 10.6 and 18 without. Its sound starts; no speaker was on CN1 to hear it.
- `tools/board_calibration.py` takes the last calibration of a log, the one of all the rounds:
  `dgx_di_calibrate_measure` logs one after each round, and the tool took the first. A measurement takes the place of
  a placeholder calibration.
- The Guition JC4880P443C, a 4.3-inch 480x800 ST7701S on MIPI-DSI with GT911 touch, ES8311 sound and the ESP32-C6 of the
  module JC-ESP32P4-M3, from the schematic of its archive. Its display starts through DGX 0.11.5, the first with the
  ST7701S, with two frame buffers; a build with an older DGX stops at `#error`, and CI builds the board with no older
  one. Built on ESP-IDF 5.5.5 and 6.1. The record imported from guition_boards 0.2.2 is gone: it gave the touch of the
  10.1-inch board, a GSL3680 of 800 x 1280, 550 Mbit/s of DSI and 24 bits, where its own demos and the schematic give a
  GT911 of 480 x 800, 750 or 1000 Mbit/s and 16 bits.
- A display whose chip no library of the catalog names, and a touch over it, are kept as data: the glue does not start
  them, `boards_gen.py` names them, and a kit with them says the program starts them.
- The record of DGX describes 0.11.5: the ST7701S, turned by `dgx_screen_orientation()`, which the adapter of DGX wraps
  for the table of a panel. CI builds a board with the older versions of a library only from the version its devices
  need.
- Ethernet: `board_ethernet_start()` starts the IP101 beside the MAC of the ESP32-P4-ETH, the ESP32-P4-POE-ETH and the
  JC1060P470C by esp_eth of ESP-IDF, with the generic PHY driver and the reset times of the IP101 driver of ESP-IDF
  5.5, and makes an interface of esp_netif that takes its address by DHCP. The device is `ip101` of the catalog, and its
  library is the record `espressif/esp_eth`. BOOT on GPIO35, TXD1 of RMII on those boards, is gone once it starts:
  `board_button_at` returns false for it. `hello_board` starts it and says so. Built on ESP-IDF 5.5.5 and 6.1, not
  tried on a board yet.
- A glue of a board of the program made by an older component, with no table of the Ethernet, links: the component
  has an empty one beside it, which the glue's own replaces.
- The display of the CYD S028R is recorded as seen working: examples/hello of 0.0.7 from the registry drew its white
  background and blue bar on 2026-11-07. The table of the README says so.
- The description of the component in the registry begins with the program, as the README does.
- [Getting started](docs/en/getting-started.md) points to the two ways on Windows in the README, and the headers of
  clang for clangd are in a section of their own after the path, "Hints in the editor": a build does not need them.
- [radio.md](docs/en/radio.md) says the JC8012P4A1C was not tried.
- The connectors of the ESP32 DevKit with micro-USB are recorded from the photo of the USB-C one, the same board:
  a kit with it no longer says they are from memory.
- `boards_mcp.py --install` finds `claude` in the extension of Claude Code for VS Code, which does not put it on PATH;
  it wrote `.mcp.json` into the current folder before.
- The dialog with a model, first run by a model on 2026-11-16: a theme the person stopped typing for 3 s ends the wait of
  the model, which answered it after up to two minutes before; `page_state` after `edit_blocks` waits until the kits of
  the editor answer the edit, as the editor now says which edit they answer; a block name the format refuses, as one in
  Cyrillic, is refused by `edit_blocks` with the reason, where before every board failed on it.
- `boards_mcp.py` gives an agent its tools and the editor only in an empty folder or a program of ESP-IDF: installed for
  every folder, it stays empty in the others.
- The dialog of the editor draws the Markdown of the model, and a line above its field says whether the model listens,
  works or has most likely ended its turn; a dialog whose agent stopped stays with what was said.
- The recipes take the component as `^0.2.2`.

## 0.2.1 (2026-11-15)

- The configuration says when `IDF_COMPONENT_LOCAL_STORAGE_URL` names a copy of the registry, as the installer of
  ESP-IDF leaves it: it prints one line while the variable is set, and the step of the flash, when it writes an older
  esp_hosted to the radio than the radio runs, names the lock the version came from and the copy. The component
  manager takes a version from the copy before the registry whenever one there fits the range. Tried on the
  JC1060P470C: the copy of 2026-10-11 gave 3.0.9 for a C6 at 3.0.10.
- [Versions](docs/en/choosing-a-board.md#versions) said `idf.py update-dependencies` solves the lock again; it removes
  only `dependencies.lock`, which a project of `board_select.py` does not read. It says now to remove
  `dependencies.lock.<board>` and run `idf.py reconfigure`.
- CI builds each board that calls a library whose range spans several lines with the oldest version of the range and
  the newest of each older line: `hello_board` of the six boards with DGX on DGX 0.10.12 and 0.10.17, and checks the
  lock took that version. Built on the bench on 2026-11-15 with ESP-IDF 6.1: the six boards on 0.10.12, 0.10.17, 0.11.1
  and 0.11.2, and a board with each of the ten display modules DGX drives; the 0.96-inch ST7735 stops at `#error` below
  0.11.0, the 1.14-inch ST7789 below 0.10.16 and the 2.9-inch e-paper below 0.10.17, the rest build on all four.
- The editor says the range of each library the board starts, as the manifest takes it, not the version the catalog
  describes, and the version a kit needs when it is higher: `jef-sure/dgx >=0.10.12,<0.12.0 (this kit from 0.11.0)`
  with the 0.96-inch ST7735. The resolver and the page give it as `library_from` of a device, and `check_boards.py`
  checks the glue stops at the same version.
- The question of the cards of an NFC reader takes MIFARE Classic, NTAG and ISO 14443-4 (DESFire) beside the standards
  of a chip, and a reader fits by the standards of its chip and by what its library reads: DESFire leaves out the
  RC522, whose library does not read ISO 14443-4, and the PN532 comes first.
- The list of libraries reads the components of Espressif's repositories of many (idf-extra-components,
  esp-iot-solution, esp-bsp) and the other names of a chip, a new field `names` of a device: 835 libraries, 74 of
  ESP-IDF. Records, described from their headers and code and not tried: abobija/rc522 for the MFRC522,
  espressif/led_strip for the WS2812B, esp-idf-lib/max7219 and esp-idf-lib/ht16k33. The 74HC595 needs no library: the
  SPI driver of ESP-IDF shifts its chain out. With a library the RC522 comes first for a reader nobody asked more of.
- The records of the libraries of the author say on which hardware each chip was seen working, with the version and
  the date; the PN5180 since 0.2.0 and the LD2410C since its first version are still to be tried.
- The web tool of the component is called the editor, and what it offers for a device a kit, in the README, the
  documentation, the help of Kconfig and the texts of the tools and the editor.
- The README begins with what a program gets: one program for any board and for a window on the computer, a change of
  board that touches at most what differs in the data, and the handwritten clock as such a program. It names the
  radio among the parts of a board, the libraries the component starts, the ranges of versions, and two ways on
  Windows, not tried yet.
- The recipes take the component as `^0.2.1`.

## 0.2.0 (2026-11-15)

- The radio beside the chip of the JC1060P470C and the JC8012P4A1C: their ESP32-C6 is a device of the catalog,
  `esp32c6`, driven by esp_hosted `~3.0.9`, with `esp_wifi_remote` on ESP-IDF below 6.1, which a library record now
  says by the conditions of `adapter.if`. The settings of the host side (the SDIO lines, the reset, the Bluetooth
  controller in the C6) come with the data of the two boards, and `check_boards.py` checks the lines against
  `buses.sdio.sdio0`. `board_radio_start()` waits for the radio and names a version of esp_hosted apart in the log.
- A step of the flash keeps the firmware of the C6 at the esp_hosted of the build and keeps nothing of it in the flash
  of the board: `tools/board_radio.py` writes an update program into the place of the app, with the program's
  bootloader and partition table, asks the version over USB and sends an image built from the same esp_hosted when it
  differs. `idf.py flash` runs it through the target `board_radio`; `board_select.py` puts the same target into the
  pre-flash task of the presets, for the Flash of VS Code. The version found is remembered by the MAC of the board, so
  a flash with nothing to change only reads the MAC; `BOARD_RADIO_FORCE=1` checks again. A board remembered as other
  hardware stops the step. A radio with firmware of its own says `"firmware": {"set": "tool"}` and is left as it is.
  Tried on the JC1060P470C with the handwritten clock: the C6 from 3.0.10 to 3.0.9 and back, Wi-Fi and the setup of
  the network over BLE.
- DGX `>=0.10.12,<0.12.0` and DGX-DI `>=0.1.5,<0.2.0`: the generator puts the calls that differ between versions of
  a library under `#if`, from the version each build took.
- [Versions](docs/en/choosing-a-board.md#versions) says how a version is chosen within the range of a library, and
  [radio.md](docs/en/radio.md) how the radio is kept.
- The recipes take the component as `^0.2.0`.

## 0.1.4 (2026-11-14)

- The recipes take the component as `^0.1.4`, which takes DGX 0.11.0.
- Photos of the ESP32 DevKit with micro-USB, the front as its edges name the sides, USB on the left. The variant with
  USB-C keeps its own front and drops the back it would inherit: `"back": null`. The check of the files of the catalog
  takes null in a board that extends another, as the rest of the checks did.
- The USB bridge of the ESP32 DevKit with micro-USB is a CP2102, as the marking on the chip in the photo says; it was
  written CP210x.
- Photos of the MAX7219 matrix of four 8x8, front and back. The order of its five wires, VCC GND DIN CS CLK, is now
  read from the silkscreen, not from the listing, and the connector says its edge: the left one of the front.
- A WS2812B panel of 8x8, `ws2812b_8x8`, with photos: one data line through 64 LEDs, pads IN and OUT on the back. It
  serves LEDs of the variant matrix, as the MAX7219 module does, not a garland: for 61 addressable LEDs the solver
  would take one panel of 64 instead of strips. The case of the MAX7219 module names the module the person has, so a
  matrix there is still that module and not the panel, which takes one line instead of three.
- A 2.8-inch TFT module on an ILI9341, `tft28_ili9341`, with photos: SPI on eight contacts, the controller and the
  size read from its silkscreen, not tried. Its DC, RES and BLK are lines of the module, in `lines` of its `on`: the
  solver now takes those of a module before those of its chip, which an ILI9341 does not name, as on the M5Stack
  Core2 its reset and backlight go through the PMIC. The corner of its first pixel is the start of the chip, unchecked.
- A 2.8-inch TFT module with touch and an SD slot, `tft28_ili9341_xpt2046`, with photos: an ILI9341, an XPT2046 and
  an XC6206 by the schematic of lcdwiki for a board with the same parts and contacts, not tried. The solver finds it
  for touch on a dev board and says that a module of several parts is wired by part, which a kit does not do yet;
  the case that said the catalog has no such module is now `touch_module_of_parts`.
- `boards_gen.py --all` no longer takes a module with touch, sound or a button for one the component sets up on its
  own: it refused such a module there, and failed on its touch first. A project wires such a module by part.
- The Waveshare 1.5-inch RGB OLED, `oled15_ssd1351`, with photos: an SSD1351 of 128x128 on SPI, its power and both
  rows of contacts by the schematic of Waveshare, not tried.
- The GC9A01, a device of the catalog now, and two round 1.28-inch modules on it with photos: `tft128_gc9a01_7pin`, a
  round board with no backlight line, and `tft128_gc9a01_8pin`, with BLK; read from their silkscreen, not tried. A
  round display asked for now gives the one of seven contacts, which takes the fewest wires; the cases that named the
  ST77916 module, the only round one before, name it, and `qspi_display` still takes the ST77916.
- The round GC9A01 module of seven contacts is the display of esp32-co2-station: SPI at 40 MHz, 16 bits in BGR, VCC
  of 3.3 V, tried on hardware there; its data says so now, with the colour order it needs.
- An SPI part with no select line: a module says `"cs": "nc"` and its `mode`, a kit gives it a bus of its own and no CS,
  and the glue passes the mode to `dgx_spi_init`, 0 as before when none is said; the record of DGX takes the mode of
  SPI and QSPI from `{mode}`. The first such part is `tft13_st7789`, a 1.3-inch 240x240 module with no CS, in SPI mode
  3 as its libraries say, not tried; with it the ST7789 is a device of the catalog. Anton: such a module can be taken
  while nothing else is on its bus.
- The HT16K33, a device of the catalog now by its datasheet: I2C at 0x70 to 0x77, 4.5 to 5.5 V, a high level from 3.5
  V on 5 V. With it `ht16k33_8x8`, an 8x8 matrix on an HT16K33 backpack, MRA210A, with photos; its contacts and chip
  read from it, not tried.
- The HD44780 is wired by its lines: `ways` of four bits, RS, E and D4 to D7, and of eight, with RW to ground, by
  the Hitachi datasheet, which also gives the high level, 2.2 V on 5 V, and the pull-ups to VCC of RS, RW and the
  data lines. The chip no longer says I2C: that is the PCF8574 backpack, and a 2004 sold with one soldered on says
  `on.i2c` itself, as the module of `examples/local_boards` does. A module that names a bus is wired by it, one that
  names none by the buses and ways of its chip, and the glue takes the call of the library whose arguments are the
  lines in `pins`, `lcd_bus_gpio4_create` for these. With it `lcd2004`, the bare C2004A, with photos; the names of
  its contacts are those of the usual 2004, not printed on it, not tried. A kit puts a level shifter on its lines,
  as they are pulled up to 5 V.
- The 2004 on a PCF8574 is back in the catalog, `lcd2004_pcf8574`, with photos: Anton bought it with the backpack
  soldered on, so it is a product; 0.0.1 took it out as his own build. A PCF8574T, the address 0x27 of open pads by
  the datasheet of the PCF8574 and the usual backpack, not tried. `examples/local_boards` takes it from the catalog and
  keeps the round display as its own module; CI builds `hello_board` with it on the JC1060P470C again, with
  `--module`.
- The record of DGX describes 0.10.17: the 1.14-inch glass of the ST7789, 135x240 and 240x135, and the NV3041A at 18
  bits came in 0.10.16, the SSD1680 of e-paper in 0.10.17. The component takes DGX `^0.10.17` now, as the glue of an
  e-paper calls `dgx_ssd1680_init` with its BUSY line. The JC4827W543C has its display tried at 16 and 18 bits, by the
  test of DGX 0.10.16.
- The SSD1680, a device of the catalog by its datasheet, and `epaper29_ssd1680`, the 2.9-inch e-paper of black, white
  and red of WeAct Studio, with photos: its contacts, its regulator and its 3.3 V lines by the schematic of WeAct, tried
  by Anton with DGX on SPI of an ESP32, in all eight orientations. The screen of DGX takes a byte a pixel, the ink, so
  its depth is 8, and the program sends a picture by `dgx_ssd1680_refresh()`. A module with no MISO contact says
  `"miso": "nc"`: the kit wires none to it, though its BUSY puts a level on a pin.
- `tft114_st7789`, a 1.14-inch 135x240 module on an ST7789 with CS and BLK, with photos: read from its silkscreen, its
  backlight and its 3.3 V by the schematic of QDtech for a board with the same parts, the size of its glass from
  modules of other makers, the window of the memory it shows from DGX and TFT_eSPI; not tried.
- The component takes DGX `^0.11.0` and DGX-DI `^0.1.6`, and the records describe them. DGX 0.11.0 takes the
  backlight line in the constructor of the GC9A01, JD9165, JD9365, ST7565R, ST7735, ST7789 and ST7920 and lights it
  once the display is set up: the glue passes the line to it, as it did to the ILI9341, NV3041A and ST77916, instead
  of lighting it itself. A backlight lit by a low level stays with the glue, as a driver lights its line by a high one.
  The ST7735 takes a panel: 128x160, or the 0.96-inch glass of 80x160, upright or turned. DGX-DI 0.1.6 is the same
  code on DGX 0.11.0, and so is DGX-LVGL 0.0.3, which examples/hello_lvgl takes now. The calls of 0.10 are in the
  history of the record of DGX.
- The ST7735, a device of the catalog by its datasheet, and `tft096_st7735`, a 0.96-inch 80x160 module on it with
  photos: its backlight and its 3.3 V by the schematic of QDtech for a board with the same parts, tried by Anton with
  DGX on SPI of an ESP32 at 10 MHz, 16 bits in BGR, in all eight orientations.
- A part wired by its lines gets its supply in a kit, as a part on a bus did: the WS2812B panel and the 2004 now list
  their 5 V wire.
- A question that limits some variants keeps a part of another variant out: a block of a display of any kind that
  asks 24 bits of color no longer takes a character LCD, which has no depth of color.
- The table of the boards in the README says what was tried on each board: the display, touch, sound and button
  that entries of `checked` at level `hardware` cover, and those that only started. The facts of the status
  paragraph went into the data: the start of the display of the JC4827W543C and the handwritten clock on both DSI
  boards. The photo of the ESP32 with a 0.96-inch OLED covers the note of its Boot button, not the button: it was
  not pressed.
- A project takes the component by `^0.1.x` now, as the page, `board_project.py`, the example `hello` and the recipes
  write it: the versions 0.1.x from that one, and no 0.2.0, which may change what a program calls. `>=` was there
  for 0.0.x, where a caret takes one version alone.
- The README says what the computer, a board of the program and the page are, and which libraries the component
  starts today, with others, Arduino among them, planned.
- An entry of `checked` may name `values`, the values of the field it covers that were tried. Both DSI boards have
  their display tried at 16 and 24 bits (Anton, in the test procedure of the DGX drivers), so a kit at 24 bits no
  longer calls that depth untried there; 18 bits on the CYD still are.
- Every block on the page has the field "Its side", a letter A to D. A letter names a group, not an edge: the wires
  of the blocks of one letter come out on one edge of the board, those of different letters on different edges,
  and the solver chooses the edges by `edges` of the connectors. An edge where the supply of the group comes out
  too goes first, and the card says where to take a supply that is elsewhere. The sides come after what must hold
  and before the IO MUX of an SPI host, as the new field `rank` of the judgements orders them; a part at a clock
  above `limits.spi_matrix_mhz` of the chip needs its IO MUX all the same. The card gives each wire its connector,
  contact and edge. A wire of a line with its own active level showed `GPIO [object Object]`; it shows its GPIO.
- A chip has `limits.spi_matrix_mhz`, the clock of SPI through the GPIO matrix by the docs of ESP-IDF: 40 MHz on every
  chip, where the ESP32 allows no more and the others run as on the IO MUX. `tools/make_mcu.py` reads it from
  `spi_master.rst`.
- A connector says on which sides of the board its contacts come out: `edges`, runs along the edges in the order of
  its pins, the edges named as the picture of the board shows it. A rule checks that the runs hold all the pins. The
  ESP32-C3-Zero, ESP32-S3-Zero and ESP32-C6 Super Mini have them by the photos of Anton's boards, and the
  ESP32-P4-ETH by the pinout drawing of Waveshare, the ESP32 DevKit by the photo of its USB-C sibling, the same board
  with a micro-USB connector. The connectors of the DevKit are `en_side` and `3v3_side` now, not `left` and `right`,
  and those of the ESP32 with a 0.96-inch OLED `svp_side` and `svn_side`: a connector is named by itself, and where it
  lies comes from `edges` and the picture.
- The buzzer block asks its swing again, as the page did before the blocks: the solver wires a part with no bus by
  the first of its ways that gives it, so four bare discs at 6 V are eight wires in antiphase and eight LEDC channels,
  and the card says how to wire the way taken. Before, a buzzer block always took one pin.
- The long path from an empty folder to the board is called Getting started now, `docs/*/getting-started.md`;
  `docs/*/quick-start.md` points to it. The quick start is in the README: six commands from the example of the
  registry to the window on the computer and the board, with no CMake to edit. The README says what the component
  is in plainer words, and its status names no version but points to this file.
- The display block of the page asks the depth of color, from the depths the drivers of the catalog take. Only the
  parts whose driver takes it fit, and when it is not the depth the data starts the display with, the board of the
  program starts it so, by `config.depth_bits` of the display of the board or of the module; the card names that
  depth as not tried on the board. Before, the depth was the one of the data, and only menuconfig of the computer
  showed a depth.
- `board_select.py host --as BOARD .` makes the board too when the project does not have it, so one command gives the
  board and its computer, and the computer is current. A board the project has, or a file of defaults written by hand,
  is not touched. The quick start chooses a known board with this one command.
- On the page a computer is no board of its own: it is shown with the board it shows, with no radio, and the mark
  "add the build on the computer" makes it current. A project opened with the computer current has the mark set, and
  with the board current has it clear. Before, the radio of the computer named its board, so choosing it kept the board
  current. A computer of a board the project does not have stays in the list, with no radio.
- `board_select.py` and the page keep in `CMakePresets.json` what another tool wrote into a preset. The ESP-IDF
  extension writes the OpenOCD board and its place on USB (Select OpenOCD Board Configuration) into the configuration
  chosen in VS Code; before, the next change of boards removed them. What it wrote into `default` goes to the preset
  of the board `default` copies. The quick start says how to choose the OpenOCD board, with no set-target.
- When the current board changes, the page says after writing to reload the window of VS Code, Developer: Reload Window,
  and open a new terminal of ESP-IDF, and so does `board_select.py`: the build of VS Code takes the new target only
  then.
- The catalog describes DGX 0.10.14: 0.10.13 draws straight segments by the pen and 0.10.14 a filled circle with a soft
  edge, and neither changed its drivers, buses or init calls. The component still takes `^0.10.12`.
- A board of the program is chosen in two steps, so no symbol of Kconfig has two definitions: the choice of the
  component has "A board of this program", and `components/local-boards/Kconfig.projbuild` its own choice, "Board of
  this program", whose boards raise the hidden symbols of the component by selecting their `…_BY_PROGRAM`. Before, that
  file defined the choice and the symbols again, and kconfgen warned that such definitions get a higher severity in the
  future. Its file of defaults sets `CONFIG_BOARD_SELECT_PROGRAM=y` before its own line; `board_select.py --again .`
  makes both files of a project made before.

## 0.1.3 (2026-11-10)

- Each configuration puts what the configuration editor or menuconfig changed in `sdkconfig.<board>` since the one
  before into the project's `sdkconfig.defaults`, as `board_select.py --keep` does: what is set with the gear reaches
  every board at the next build. The options of the board itself are named and not kept, and an older `sdkconfig` of
  another board takes nothing back. A snapshot of each `sdkconfig` lies in `.boards/` of the project.
- `board_select.py --keep` and the keeping at each configuration take, on ESP-IDF 6, each option the person set on, as
  its `sdkconfig` marks the others by `# default:`: an option set together with one that selects it, as
  `DGX_ENABLE_VSCREEN` with `DGX_ENABLE_MORPH`, was left out of the minimal configuration.
- The mark "add the build on the computer" stands beside "make a project…" of a card and "make the project of these
  boards…": set, the board gets the computer that shows its display, and the computer is current; clear, the board is
  current and the computers of the project stay as they were. The mark of the list before writing is gone, and the
  page no longer makes the computer current when the person chose a board.
- On the page a block with nothing chosen in it takes the part of its role of the board selected, as its display, and
  goes back to any when the board changes; what the person chose stays. The Part of a block offers the parts of the
  board selected, so the display of a board is one to choose there, not only the modules of the catalog.
- The package carries `imported/`, the data of boards and modules taken from others, with the licenses it comes under
  in `imported/licenses/` (`LICENSES.md`): the page of a project made from the registry offers its boards and modules
  as it does in a clone, marked unchecked, with no project for an imported board. It adds about 120 KB to the archive.
- The recipes take the component as `>=0.1.3`.

## 0.1.2 (2026-11-10)

- The page writes the computer that shows each board with a display, `host_<board>`, beside the board, while the mark
  "and the computer that shows each board with a display" in its list is set, as it is at first; the computer of the
  current board becomes current. A project begun on the page had no computer before, and the quick start begins with it.
- The quick start chooses the board on the page first and by two commands when the board is known, and says which
  characters the name of a project takes.
- The recipes take the component as `>=0.1.2`.

## 0.1.1 (2026-11-10)

- The preset of the current board comes first in `CMakePresets.json`, the one to choose in VS Code: the page and
  `board_select.py --current` change what it builds. A board of the program is named for the program, as
  "Guition JC8012P4A1C for hello", so the lists of VS Code do not show it as the board it is made of.
- The `sdkconfig` of each board lies in the folder of the project, `sdkconfig.<board>` beside its defaults, as the
  presets and `.vscode/settings.json` name it: `build/` holds only what a build makes again, as in any project of
  ESP-IDF, and removing it loses no option chosen with the configuration editor. `board_select.py --again .` and a
  choice of boards move an `sdkconfig` of `build/<board>/` there. The `.gitignore` of a new project keeps
  `sdkconfig.*` out but for `sdkconfig.defaults*`; a project of 0.1.0 adds those lines itself.
- A configuration whose target is not the one the file of its board names stops before the compiler checks, with what
  to do: `idf.py set-target`, as the button with a chip of the ESP-IDF extension runs it, made the build directory of
  the current board one of another chip, and in the computer's the compiler of the chip took the linker of the
  computer (`unrecognised emulation mode: elf32lriscv`). It stops `-D BOARD` with the preset of a board of another
  chip too, before the check of the board chosen.
- `board_select.py --keep .` puts the options set for the current board, in the configuration editor of VS Code or
  in menuconfig, into the project's own `sdkconfig.defaults`, which every board reads: all but those its file of
  defaults sets, which it names. `idf.py save-defconfig` writes the target and the choice of the board there too.
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
- The recipes take the component as `>=0.1.1`.

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
