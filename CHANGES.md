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
- Calibrations by library and by measurement: `config.calibrations`, `measured_with`.
- What each pin can do and who has it: `gpio.pins` of `catalog/mcu/`, `board_pins.py --free`.
- JC1060P470C: Ethernet, RS-485, the RTC, the TF slot, the battery divider, the connectors, from its
  schematic.
- Several graphics displays on a board: `board_display_count()`, `board_display_init_at()`; two shown
  as one screen through `display_groups`.
- The local terminal: an ESP32 with two PN532 and the 2004 module. A device the component does not
  set up keeps its lines as data: `board_bus_get("nfc_in", "cs", &pin)`.
- `examples/hello_lvgl`: LVGL on the chosen board through DGX-LVGL.
- Sound through an I2S amplifier with no codec: `"kind": "i2s"`.
- JC4827W543C: the amplifier, the BOOT button, the TF slot, the battery divider,
  the connectors, from its schematic. CYD S028R: the RGB LED, the light sensor,
  the connectors. JC8012P4A1C: the BOOT button.
- DGX ^0.10.1 and DGX-DI ^0.1.4. A bus with only a display is set up by DGX,
  which does not release it between drawings, so `board_spi_bus()` returns
  `NULL` for it. When a touch panel or an SD slot is on the display's bus, the
  component sets the bus up and the display joins it with
  `dgx_spi_init_on_bus()`.

Known: the GSL3680 firmware of the 10.1-inch board is the program's to embed.
