# CHANGES

## 0.0.1 (2026-10-27)

The first release: boards as data, one choice, the glue generated and
committed, a program that asks by kind.

- Four boards and one module: Guition JC1060P470C (7-inch, ESP32-P4),
  JC8012P4A1C (10.1-inch, ESP32-P4), JC4827W543C (4.3-inch, ESP32-S3), the CYD S028R
  (ESP32-2432S028R), and a 2004 character LCD on a PCF8574 backpack as a
  module on any board's I2C bus. Their buses, devices, touch calibrations
  (measured on the boards),
  buttons and `sdkconfig.defaults` with the reasons in comments.
- `catalog/boards/<board>/board.json` is the only source of truth.
  `tools/boards_gen.py --all` makes from it the C glue, `board.cmake`,
  `boards/boards.cmake`, the `Kconfig`, the dependencies of
  `idf_component.yml` and the tables of the READMEs; `tools/check_boards.py`
  fails when any of them differs from the data.
- The contract of `boards.h` holds at link on every board: the glue defines
  every function, those for parts the board has not return `false`.
- `board_display_orientation` turns the display and keeps the size as it lies;
  `board_character_display_init` for an HD44780 on the board or as a module;
  `board_touch_firmware` as the hook a program defines to give the GSL3680 its
  firmware; `board_sound_source` to change the source of the sound.
- The CYD S028R as it is: the XPT2046 touch on its own SPI3 (pins 25, 32, 39, cs 33,
  irq 36) through `atanisoft/esp_lcd_touch_xpt2046`, the speaker on the DAC at
  GPIO 26 fed by DMA (`dac_continuous`, which ESP-IDF 6 still has), the BOOT
  button, the SD pins kept as data since no SPI host is left for them. The
  display lies landscape, 320x240.
- The board is chosen once: `tools/board_select.py` puts the board's
  `sdkconfig.defaults` into the project as `sdkconfig.defaults.board`, with
  `CONFIG_IDF_TARGET` and `CONFIG_BOARD_SELECT_<BOARD>=y` as its first lines,
  and the menu follows. Modules are appended with `--module`.
- `tools/board_pins.py`: the map of a board's pins (GPIO to owner, conflicts)
  and its tree; the same checks run in `check_boards.py`.
- `tools/check_boards.py --host-syntax`: every glue compiled on the host
  against `test/fake/` with `-Werror`.
- CI: `examples/hello_board` built for every board, and once with the module,
  under ESP-IDF 5.5 and 6.1.
- Documentation in English and Russian: `docs/en/`, `docs/ru/`, `README.ru.md`.
- The editor of the data (Vue + Pinia from a CDN, no build step) follows the
  format: the `measured` flag of a calibration, a DAC sound without an
  amplifier pin, the touch component with its namespace.

- Format version 2: the data lies in `catalog/`, boards name the devices of the
  catalog, layers merge by JSON Merge Patch, one schema and rules as data.
- Devices and libraries apart: `catalog/libraries/` says for each chip how a library starts it and
  what it can do with it, and what each version of it requires. The tables of the generator
  became these records. A device names its library in `library` and what it needs in `needs`.
  A record says how to get the library (`install`: the registry, git, an archive, the platform) and
  how each call shows it worked (`ok`, by the conventions of that library).
- `boards.h` names no library: it gives sizes, millimetres and orientation. The code for each
  library lies in `adapters/<owner>__<name>/`, and `boards_dgx.h`, `boards_dgx_di.h` and
  `boards_hd44780.h` give the handles. `board_touch_start()` fills a `struct board_touch`.
- Touch panels, sounds and buttons in the plural: `board_touch_count()`, `board_touch_start_at()`,
  `board_sound_start_at()`, `board_button_at()`. The generator reads the devices of a board itself.
- A module has the fields of a board and may have a chip of its own. On a board it is named in
  `modules`, its parts `<use>_<part>`.
- The revision of a chip chooses its settings: `mcu.revision`, `board_select.py --revision`.
- Calibrations by measurement: `config.calibrations` is a list of the places aimed at, each named
  for where it is, `left_up` and the rest, for any library; `libraries` holds what only one uses,
  `measured_with` the versions. The glue makes the calibration of DGX-DI from the places at start.
- What each pin can do and who has it: `gpio.pins` of `catalog/mcu/`, `board_pins.py --free`.
- JC1060P470C: Ethernet, RS-485, the RTC, the TF slot, the battery divider, the connectors, from its
  schematic.
- Several graphics displays on a board: `board_display_count()`, `board_display_init_at()`; two shown
  as one screen through `display_groups`.
- A device the component does not set up keeps its lines as data: `board_bus_get("nfc_in", "cs", &pin)`.
- `examples/hello_lvgl`: LVGL on the chosen board through DGX-LVGL.
- Sound through an I2S amplifier with no codec: `"kind": "i2s"`.
- What a trial import of 115 boards showed the format lacked: millimetres of a panel and
  `fingers` of a touch are optional, `board_display.mm_w` and `mm_h` are 0 when not known;
  `config.timing` of a panel; `format` of an I2S connection, `clock` of a codec, more PDM
  lines; `sio` of an SPI connection; buttons on a resistor ladder with windows in
  millivolts; `chip_try` for a chip found at start; the class `fuel_gauge`.
- Cameras as data: the buses `csi` and `dvp`, the class `camera`. JC1060P470C and
  JC8012P4A1C: the CSI bus, the connector, the OV02C10 as a module, its sensor read over
  I2C on both boards. `esp-idf/guition/esp_cam_sensor`: the OV02C10 is in the maker's copy
  of that library, not in the registry.
- Physical facts: `maker`, `part`, `compat`, `marking`, `ref` and `draw` of a device, `maker`,
  `part` and `revision` of a board and a module, `mcu.part`, `checked.*.unit`, `license` of a
  library. `power` also holds the lines of supply: `name`, `source`, `from` with several ways
  in, `through`, `regulator`, `ma_max`, `dropout_mv`, and `feeds` takes `mcu`. A part a program
  does not see is a device of class `other`. The four boards have them, from their schematics.
- A step of `power` with a name owns its GPIO, and `board_pins.py` shows it as taken. The
  generator refuses a step with a `line`: it did not set them and said nothing.
- `config.divider` of a battery is in ohms, with an optional `switch`.
- `catalog/connectors/`: `of` names a connector a standard fixes: STEMMA QT, Qwiic, Grove.
- `price` on a board, a module and a device, as named offers with a range, `tariff` for the
  customs code, `count` for what has no wiring. `tools/board_bom.py` lists what to buy for a
  product.
- `freq_mhz`, `tx_mw_max` and `radiated_mw` of a transmitter. The PN532 and the PN5180 have
  the carrier, the most their transmitter takes and `draw` from their datasheets.
- `editor/resolve.js`, the loader in JS. `check_format.py` compares it with `tools/resolve.py`.
- The editor is new and reads format 2: a tree, the card of a node from the schema, the map of pins,
  the checks of the tools on every change. Vue and Pinia are in `editor/vendor/`. The editor of
  format 1 is gone. `check_format.py` compares `editor/schema.js`, `editor/pins.js` and the JSON it
  saves with Python.
- `esp32s3_devkit`, a standard dev board with two USB-C ports, and `tft153_st77916`, a round
  360x360 display module.
- `esp32_devkit`, a standard dev board.
- The page starts with what to build: a form from `catalog/questions.json`, kits of a board and
  modules with the wires and the reasons, a project written into a folder. The solver only proposes:
  the checks of the tools decide about each kit, and the generator about the kits of `test/solver/`.
  The headers of `esp32_devkit` and `esp32s3_devkit` are in the data, from memory, `unchecked`.
- A chip names the lines it needs beside a bus: `lines` of `on`. The PN5180 needs BUSY and RST, and a
  board without them is refused. The ESP32-C6 on JC1060P470C and JC8012P4A1C provides Wi-Fi and
  Bluetooth in the data; the ESP32-P4 itself has neither.
- Approximate AliExpress prices from Anton: CYD, JC1060P470C, JC4827W543C, JC8012P4A1C, the PN532 and
  PN5180 modules. Prices from a search of listings: the 2004 module and `esp32s3_devkit`.
- The order of kits: the unknowns, the modules, the wires, then the price. A budget moves the price
  right after the unknowns.
- Questions for Ethernet, Power over Ethernet and the reading distance of a reader. `provides.ethernet`
  is now a port, given by the device with the PHY; the MAC of a chip is `provides.emac`.
- Supply and levels: `volts` on a step of `power`, `logic` on a device, `supply` on a module of a
  board or a project, `gpio.high_mv_max` on a chip, from the datasheets. The solver feeds each module
  and asks for a level shifter where the lines of a module go above what the pins take.
- The solver wires QSPI and UART, and a DSI module takes a free bus of the board. `hosts.uart` on a chip.
  A display on SPI or QSPI gets a bus of its own.
- The Waveshare ESP32-P4-ETH and ESP32-P4-POE-ETH, from the schematic of Waveshare, and the module
  `waveshare_poe_b`. Built, not flashed.
- A kit counts what is sold by the pack at the price of the pack.
- DGX 0.10.3 at least: under ESP-IDF 6.1 a QSPI display on the IO MUX pins of SPI2 stayed dark.
- The ST7920 as a chip of the glue, and the module `lcd12864_st7920`. `mechanics` on a board or a
  module: outline, holes, what it takes to mount it; `window_mm` of a panel.
- Piezo discs: the class `buzzer`, `ways` for a device with no bus. Each disc takes a line and a LEDC
  channel, or two of each for more swing, counted against `hosts.ledc` of the chip.
- `board_select.py` says `idf.py reconfigure build` for a project already built.
- A board of a program: `components/local-boards/` of the project, a tree in the layout of `catalog/`,
  read before it. `board_select.py` makes its glue there and the board joins the menu.
  `examples/local_boards`. The catalog holds no projects: `check_format.py` refuses one.
- A board needs no `buses` in the data. `examples/hello_lvgl` is built in CI only for a
  board with a graphics display: it does not link without one.
- JC4827W543C: the amplifier, the BOOT button, the TF slot, the battery divider,
  the connectors, from its schematic. CYD S028R: the RGB LED, the light sensor,
  the connectors. JC8012P4A1C: the BOOT button.
- DGX ^0.10.1 and DGX-DI ^0.1.4. A bus with only a display is set up by DGX,
  which does not release it between drawings, so `board_spi_bus()` returns
  `NULL` for it. When a touch panel or an SD slot is on the display's bus, the
  component sets the bus up and the display joins it with
  `dgx_spi_init_on_bus()`.

Known: the GSL3680 firmware of the 10.1-inch board is the program's to embed.
