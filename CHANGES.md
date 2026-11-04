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
- `board_display_orientation` turns the display and gives the size as shown;
  `board_character_display_init` for an HD44780 on the board or as a module;
  `board_touch_firmware_set` for a program to give the GSL3680 its firmware; `board_sound_source` to change the source of the sound.
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
- The speed of a display on its connection goes before that of its bus. A display with no line back gets a
  bus with no MISO from the solver.
- A kit names its libraries. Those the board does not start go into the written project and its README,
  and a plan for an existing program shows the lines to add to `main/idf_component.yml`.
- `tools/check_format.py` compiles the templates of the page.
- A project keeps `selection.json`: the answers, the kit, what fits too and why the rest does not. Opening
  the folder brings the answers back.
- NFC chips and modules: the MFRC522 and CLRC663, `rc522_module`, `rc522_mini`, `clrc663_module`, from a
  comparison not yet checked against datasheets; `features`, `frame_bytes`, `stack`, `reads`, a range as
  `range_mm`, `identify` for clones. A question asks which cards, and a chip with no library in the catalog
  counts as an unknown of its kit.
- From two readers on, a question asks the distance between their antennas. A longest `range_mm` that reaches
  it, or no answer, is an unknown of the kit and not a refusal: two PN532 work side by side in one case, and
  two readers are not measured. `when` takes `{"at_least": n}`.
- A kit says what its board holds and nobody asked for, and such a part counts after the modules and
  before the wires, so a display does not come first for one wire less. `"used": false` on a device of a
  project: its pins stay taken, no library comes for it, its `board_*_init` returns false. A kit sets it on
  what was not asked for, but not on the display under a touch that was asked for.
- `tools/import_board_manager.py` takes the boards of esp_board_manager packs into `imported/`, a tree the checks
  read after `catalog/`, with no glue and no build. It gives no value a pack does not, takes no DSI timings and
  writes no `shared_pins`. `lanes` of a CSI bus and `sample_rate` of a sound are no longer required by the format.
- The solver and the page read `imported/`. A board with no supply lines or connectors in its data takes a module as
  an unknown of the kit, an imported board says nothing of what its chip can do as an unknown, and such a board makes
  no project yet. `tools/make_mcu.py` writes `platforms` into a chip: since which ESP-IDF it is taken, by revision,
  from COMPATIBILITY.md of ESP-IDF. The map of pins counts the data lines of RGB and DVP, and buttons on a ladder.
- The page runs the solver in a worker, so an answer no longer stops it.
- `tools/import_fritzing.py` takes modules from Fritzing parts into `imported/modules/`: the contacts, the supply they
  name, the part number. With a copy of a shop's list it also takes the price and the sections of a part, and leaves
  out what is no longer sold.
- `catalog/roles.json`: what a part can be for, by groups, with the variants that change what it takes. A part names
  its roles in `provides`. The words of a role are a hint for an import.
- `kind: addon` in `catalog/addons/`: a part that stands in the way of lines, a supply or a port and takes no pins. A
  kit adds a level shifter by itself where a level needs one: both ways for lines a module drives, one way for lines
  that only listen, by the channels of one.
- `max7219` and the module `max7219_4in1`: its chain takes no pins, and `high_min_mv` of a chip brings a level shifter.
  The LEDs of the boards name their variant.
- `tools/boards_mcp.py`: an MCP server that serves the page on 127.0.0.1 and puts the agent of a person beside it, for a
  dialog, proposals of blocks and a description that a project keeps as `DESCRIPTION.md`. The page needs no key.
- `kind: platform` in `catalog/platforms/`: which chips each version of ESP-IDF and Arduino takes, where its libraries
  are published. A choice in the top row limits the boards by their chip.
- `catalog/libraries/` holds all about libraries. `tools/import_libraries.py` writes `libraries.json`, the leading list with
  the same facts about each, and `chip_libraries.json`, an index into it. It ranks nothing: popularity is shown and comes
  last. A library nobody audited is no proposal of a kit, and a library with no chip is a library too.
- `audit.json` beside a library record keeps what audits found, by commit, and `catalog/rubrics/` what they ask.
  `tools/audit.py` takes a result and shows what a newer version changed in what was read.
- A kit names the audited libraries that fit its platform and bus, in order, with no counts: a library answers for what it
  requires. What was found reaches the model through `library_audits` of `boards_mcp.py`.
- A chip goes first on the bus its library was tried on, and a kit says so of any other.
- SPI parts each take a host of their own while the chip has a free one and the pins for it, so their tasks run apart
  (Anton: the terminal and dotview-clock are built so); a host is shared when none is left, up to six devices as in
  `spi_master.c`, and the kit says which. A kit opens a second I2C port when the bus of the board does not come out:
  the JC4827W543C takes a CO2 sensor on GPIO 6 and 7. The I2C ports of a chip in catalog/mcu are its HP ports.
- A display chip says its variant, so a board with a TFT is no answer to a request for an OLED or for shift registers. A variant
  with a way of its own, as a chain of shift registers, a photoresistor on ADC1 or a button on a GPIO, needs no part: the kit
  gives it the lines, and chains share their data and clock in `shared_pins`. `gpio.adc1` of a chip comes from ESP-IDF.
- The HLK-LD2410C radar, and PIR and radar as variants of presence.
- The solver tries every choice of modules for a board while they are few, and past that what one change of the best gives, twice.
- A part chosen for one block takes the place of another whose role it gives: an SCD4x is CO2, temperature and humidity.
- What a person can ask for comes from the roles too, and a part a module of the board brings is left unused through that module.
- Kits rank what a board has and nobody asked for before the count of modules, so a camera nobody needs puts a kit below one
  without it. The button of a strapping pin is not counted, and an imported board says that its pack lists only some of its parts.
- Pictures of parts: `tools/import_pictures.py` draws the breadboard drawing of the Fritzing part of each imported module
  into a WebP of 320 px. They are under CC BY-SA 3.0, each names its author, and a kit shows them with that credit.
- A block of your own part replaces the field of pins in use: its lines, those already soldered as line=GPIO, and its bus with
  an address. The kit keeps those pins for it and the checks name it when another owner wants one.
- A card is titled by its board, with the parts bought one by one under it, and the page asks the solver only what it shows:
  answers left from the old questions no longer add parts. The project name stands above the theme.
- A display block can ask for a round panel, and the settings of a block hold on the canvas. The SCD4x names CO2 by its role
  `air`. SCD40 and SCD41 modules at the prices Anton paid, their boards from his photos: four holes, VDD 2.4 to 5.5 V by the
  datasheet, no regulator on the top side, pull-ups to VDD assumed. The kit feeds them from 3V3.
- Input has a gamepad: a module, an NES or SNES pad (pads share latch and clock), a PlayStation 2 pad, buttons on GPIOs, or a
  pad by Bluetooth Classic or BLE. Classic is `bluetooth_classic` of a chip, from ESP-IDF: ESP32 and ESP32-S31 have it. The
  joystick is an analog stick, its two axes on ADC1, or an arcade stick. A way can take several pins of ADC1.
- A kit says when the data names no supply of a module, or no voltage of a step, instead of listing no wire for it.
- The antenna of the radio of the chip is `mcu.antenna`; an antenna on the board has a `form` and can have an `external`
  connector beside it, chosen by a resistor or a switch. Wi-Fi and Bluetooth blocks have the variant `external_antenna`.
  The JC4827W543C of Anton has an external antenna, though the vendor's specification names a WROOM-1.
- The Waveshare ESP32-S3-Zero, `esp32_s3_zero`, from the schematic of Waveshare: the WS2812B on GPIO 21, BOOT, the holes and
  the pads, 4 MB flash and 2 MB quad PSRAM. Built, not flashed yet.
- Antennas measured on Anton's desk, the RSSI of one access point: the boards with an antenna on them gave -60 to -68 dBm over
  two positions, the JC4827W543C with its external antenna -50.5. A turn of 90 degrees moves a board by up to 11 dB.
  These stay notes of one desk and one evening. The data judges the design instead: `antenna.quality` from 0 to 10, with
  marks for kinds of design; a kit shows it when a radio is asked for and does not rank by it, the model weighs it.
- A kit whose price lacks a part is no longer the cheapest by the sum of the rest.
- A block asks of the data of its part: questions with `limit.field` and `limit.fits`, answers in `asks` of the block. First
  ones: CO2 up to, ppm (the SCD40 stops at 2000), temperature down to and up to. Blocks with different answers are separate needs.
- One part serving several blocks no longer chains: a part that serves another block stays, and the kit keeps it.
- The platform is asked as any, ESP-IDF or Arduino; a kit names the versions that take its chip and its libraries
  (`builds with ESP-IDF 6.1, 5.5`), and a version is fixed only when chosen.
- Waveshare ESP32-C3-Zero, `esp32_c3_zero`, from the schematic of Waveshare; the generator takes the ESP32-C3 and C6. Pictures of
  the S3-Zero and the C3-Zero from Anton's photos.
- A page without an agent shows how to get one, as a single line that opens to the command.
- `tools/board_select.py` no longer writes a board a build would not give: a change of board without `--reset` fails
  with the command, and after `--reset` it names `idf.py set-target <target>` when the build directory was made for
  another chip. Several boards write `sdkconfig.defaults.<board>` each, with the lines of the revision of the chip, and
  build with `-B build-<board> -D SDKCONFIG=... -D BOARD=<board>`; the CMake of the skeleton, the examples and the docs
  reads `BOARD` and keeps the lock of the components in the build directory. The recipe that read the defaults of the
  catalog from managed_components/ is gone: it lost the lines of the revision of a P4.
- A module is offered only with a board that opens the bus it sits on: the Kconfig has a symbol for each kind of bus, and
  `board_select.py` refuses the 2004 module on the CYD, which opens no I2C bus to a module. When the page updates a program
  of its own, it also shows the CMake lines that read the board and the PRIV_REQUIRES of main.
- Until the component is in the registry, the docs take it from git at a commit, and a project the page writes gets the
  commit the server of the model reports.
- `tools/check_format.py` checks the index of the catalog, as `check_boards.py` does: a stale index hid two chips from the
  page. The server of the model refuses a body of the wrong form with 400 and answers a tool that fails with an error,
  instead of dying. The checks of CI run on every branch, the builds on main and pull requests.
- The page: the button that pins is `pin`, not `fix`; the lines of the ranking are notes and stay out of the README of a
  project; the hint about Chromium is not shown in Chromium; an answer of a block to a question of another variant does not
  act; `within` reads `!=`.
- A board may name several I2C buses, one a port, and the glue makes a master on each at the first ask. The program gets
  it with `board_i2c(port)` and adds its devices on it, or makes its own on a port `board_i2c_taken` reports free:
  ESP-IDF takes one master on a port. A touch panel, a codec and a module take the port of their own bus. The master is
  made under a lock, so a program task and the start of the touch panel asking at once get the same one.
- The firmware of a GSL3680 is given by `board_touch_firmware_set()` before `board_touch_start`, no longer by a weak
  `board_touch_firmware()` the program redefines: a definition in a file the program links by nothing else lost to the
  weak one, and the touch of the 10.1-inch board stayed off with no word (found by the audit of 2026-11-03).
- The CMake of a program gets the primary display of the board chosen as shown: `BOARD_PIXELS` and `BOARD_MM`, from
  `boards/<board>/display.cmake`, which the generator makes from the data, through `project_include.cmake` of the
  component, for a board of the catalog or of `components/local-boards`. They are set before `idf_component_register`
  and empty in the early expansion of the requirements (ESP-IDF 6.1 and 5.5.5). `board_pins.py <board> --display`
  prints the same for a Makefile. The four boards dgx-ge has give the numbers its own `board.cmake` writes by hand.
- A build with no board chosen links: `src/board_none.c` gives the tables of a glue, all empty, every function of
  `boards.h` returns false and `board_info()` names the board `none`. Before, the link failed on seven undefined
  references (the audit of 2026-11-03, 5.7). The glue gives tables only: `board_bus_get`, `board_spi_bus`,
  `board_spi_taken` and the functions of a display a board has not are written once in `src/` instead of being generated
  into every glue, and `CONFIG_BOARD_MODULE_CHARACTER_DISPLAY` is gone (5.10 in part, 5.20).
- The source of the sound takes a context: `board_sound_source_t` is `(void *ctx, int16_t *samples, size_t count)`, and
  `board_sound_start`, `board_sound_source` and their `_at` forms take `ctx`, given back to it at every call, so the mixer
  of a game needs no static. The task takes the source and its context together. The names `board_`, `boards_`,
  `BOARD_` and `CONFIG_BOARD_` are said to be the component's (both found by 7c after the move of dgx-ge was decided).
- The glue of a touch panel or a sound is data only: its row names the function of its adapter, from the new `function`
  of the chip in the record of its library, and the data of its kind (`board_touch_gt911`, `board_touch_spi`,
  `board_touch_gsl3680`, `board_sound_es8311`, `board_sound_dac`, the I2S bus). The functions `touchN_start` and
  `soundN_init` the generator wrote into every glue are gone; the adapters take the row (the audit of 2026-11-03, 5.10).
- The order of audited libraries in a kit holds its basis, shown by the page on hover: for each library the version
  read, the defects with what it requires, the points of `frames`, `waiting` and `code_health`, the date and the file of
  the audit (Anton: the audits serve the choice, and the reason of a choice can be looked at, not shown off). They ship
  in the package as data of the solver.
- The frequency sources of every chip come from ESP-IDF 6.1, not from a table typed by hand for three: `soc_caps.h`,
  `clk_tree_defs.h`, the Kconfig of the crystal, the low-level headers of LEDC, MCPWM, RMT, I2S and the clock tree, the
  drivers. The C3, the C6 and the other ten chips get LEDC, RMT, MCPWM where they have it, CLK_OUT, the APLL and the DAC
  cosine where they have them. The old table differed from the headers and the drivers: the prescale of an MCPWM timer
  goes up to 256, not 65536, because the prescale of the group is shared by its three timers and stays 1 while the
  prescale of each timer fits (below that the driver raises it, which the model does not count); the carrier of RMT
  counts up to 65536 + 65536 ticks of the clock of the group, not 131070, with no prescale of its own, not 256; the DAC
  cosine of the ESP32 has one generator for both channels, not two. A period of MCPWM stays at most 65535 ticks: the
  register would hold 65536, the driver takes less (found by 7c). The range of the multiplier of the APLL is data,
  not a number in the solver. Kits on C3 boards now give tones and LEDC ways.
- A part of the person's own soldered to a pin the board does not leave free (another owner, a note such as USB-JTAG,
  input only) refuses the board with the pin and what holds it, instead of a kit with a wire on that pin. The C3-Zero
  showed it once its kits had tones.
- A fifth judgement, `ledc_channels`, of the kind `resource_limit`: the LEDC channels the ways of the parts take (a chain
  of shift registers, an RGB LED) are counted with those of the outputs against the chip, as data-format.md said and the
  solver did not do. Three RGB LEDs no longer fit an ESP32-S3, which has eight. The C3 and the C6 have no frequency
  sources in the data and are not counted yet.
- The reading distance and the cards of an NFC reader are asked of each block (`"asked": "block"` in questions.json), so
  two readers ask their own; the distance between readers stays a question of the page. Two blocks of one role are
  always two parts: with different answers one module served both. The model gets these questions from `roles`
  (Anton's decision: the old questions of the page into the asks of a block, NFC first).
- A fourth judgement, `unnamed_variant_is_no_answer`: a part of a board whose data names no variant answers nothing
  for a variant asked when a module of the catalog names that variant, and stays a line of the kit. Segment LEDs no
  longer give first an imported M5 Atom with some LED and no module, but a DevKit with a segment backpack (the audit of
  2026-11-03, 4.5, Anton's default).
- Small things of the audit of 2026-11-03 (5.16 to 5.22): the generated texts end in one full stop, not two; a kind of bus
  the glue only keeps (dsi, rmii, uart, sdio) brings no `esp_driver_gpio`; `board.cmake` says ESP-IDF 5.5, as the
  manifest; `CONFIG_BOARD_DISPLAY_GROUP` is always in the Kconfig, 0 on a board with no group; hello_board takes the rate
  of its tone from `board_sound_init` and names its numbers; `board_select.py --revision` names the revisions it knows
  instead of a traceback, and says when a chip has none. `check_boards.py` reads what a board must define from
  `boards.h` and `board_glue.h` instead of a second list by hand, which had lost four functions (5.23).
  `take_report.py` puts a reported price into the text of the file, one offer more, and checks by parsing that the file
  says what it should; only a file it cannot take so is written anew (5.17). A kit on a chip whose docs name strapping
  pins no datasheet describes says that it leaves them. The log of a program on the computer is buffered in a pipe:
  `stdbuf -o0` gives it at once.
- A third judgement, `jtag_is_a_cost`, of a new kind `note_cost`: a pin with the note JTAG is given with a line that JTAG
  is gone, as a cost rather than a danger. A display with no line back on an ESP32 DevKit takes SPI2 on 13 and 14 with
  its CS on 15, as the left display of dotview-clock is wired. Other notes (the pins of the flash, of USB, of the
  console) still keep a pin out.
- The strapping pins of a chip are as its datasheet of Espressif gives them, copied, not judged: the rows of its table
  of boot modes (`gpio.boot_modes`: the level of each pin for `spi_boot` and for each download mode) and, for each pin,
  `boot` with what it selects, its pull at reset and the footnote of the table. The datasheets lie in
  `~/dgx-bench/datasheets-espressif-2026-11-04/`, named in `checked.boot`. The list of strapping pins joins the docs of
  ESP-IDF and the datasheet, which name different ones for the C5, C61, H2 and S31; the H21 and H4 have no PDF and keep
  the docs alone. A second judgement, `strapping_by_harm`, reads the harm of a level there: run (the start of the
  program or the voltage of the flash), download, or none; it keeps out run, download and a pin no datasheet describes,
  and lets the others go with a line that names the pin. Two readers on an ESP32 DevKit now have SPI3 on 23, 19, 18
  with the CS on GPIO 5, as the terminal is wired; GPIO 2 of a C3 goes with the footnote of its datasheet (7c read the
  tables against the PDFs).
- The computer is a board: `board_select.py host --as <board>` and `idf.py -D BOARD=host build` build the program for
  the linux target of ESP-IDF, `src/board_host.c` gives `boards.h` over SDL2 (a window as large as the board shown, its
  sound, the time), and `BOARD_PIXELS`/`BOARD_MM` are those of that board. hello_board built so runs on the computer
  unchanged. The window stays black and there is no touch until DGX and DGX-DI build for that target (Anton,
  2026-11-03: the host of dgx-ge as a board; Windows later, through a Makefile).
- The ESP32-C2, C3 and H2 have their table of pins in catalog/mcu: make_mcu.py read only tables with a column of RTC
  or LP GPIO, and those three have none. So their strapping pins were not in the data, and a kit on the C3-Zero put the
  MISO of a reader on GPIO 2. The strapping pins are those the table marks and those the note under it names (the H2
  gets 8 and 9, the S2 gets 46, written with a full-width semicolon). The C61, whose docs name none, has no list and a
  kit on it says so; make_mcu.py fails on a chip whose table does not parse (found by 7c).
- The solver takes its first judgement from data: catalog/judgements.json, each judgement of a kind editor/solver.js has
  a function for, with an id that a line of a kit carries (on hover on the page, to the model, in `selection.json`, and
  checked by `test/solver/`). `host_on_its_iomux` puts a new SPI host on the pins of its IO MUX when they are free, as a
  wired board takes them: two readers on an ESP32 DevKit get SPI3 on 23, 19 and 18, as the terminal has them. The chips
  in catalog/mcu have `iomux`, from `spi_pins.h` of ESP-IDF (Anton's decision of 2026-11-03: the judgements of the
  solver go into data, one at a step).
- The generator checks a board against its chip in catalog/mcu, which make_mcu.py takes from ESP-IDF: the SPI hosts it
  can wire, its GPIOs and those only for input. Its own tables of five chips are gone; a pin a chip has not, as GPIO 24 of
  an ESP32, is now seen (the audit of 2026-11-03, 5.9).
- `tools/board_project.py DIR --board B [--module M]` writes a new project on a board chosen by hand, without the page:
  the files of `editor/skeleton/files.json`, filled as the page fills them, and `selection.json` with no answers;
  `--selection` takes the board and the modules of a `selection.json` back. The page reads the same list of files
  (the audit of 2026-11-03, 1.3).
- `board_bus_get` gives a device the component does not set up the bus it is on: `host` (as `SPI3_HOST`), `port` of
  I2C or a UART, and `address` on I2C when the data gives one. A program took the readers of the terminal by their names
  alone; before, it had to write the host in its code.
- The SSD1351 OLED is in catalog/devices, from the driver of DGX. The glue of a board with a group of displays names
  the board in `board_data`, no longer its last group: a loop over the groups reused the name of the board.
- `BOARD_PIXELS` and `BOARD_MM` of a board whose primary display is a group of two side by side are those of the
  group, as `board_display_init` gives it (256x128 for two 128x128), no longer those of its first member.
- `board_sound_init()` sets the sound of the board up without a task and returns `board_sound_t`; the header of its
  adapter gives the handle of the library: `board_esp_codec_dev()` (ES8311), `board_i2s_channel()` (an amplifier on
  I2S), `board_dac_continuous()` (the DAC of an ESP32). A program with a mixer of its own writes there itself and sets
  the volume of the codec; `board_sound_start` runs its task over the same setup. Setup and task are made under a lock.
  The ES8311 checks each step of its setup and names the call that failed, and the DAC turns its amplifier on or fails
  (the audit of 2026-11-03, 5.15, 5.13, 5.21).
- Every public structure of `boards.h` has a typedef ending in `_t` (`board_info_t`, `board_display_t`,
  `board_character_display_t`, `board_touch_t`, `board_spi_bus_t`), and the headers and examples use them; the tags
  stay for a declaration ahead (the audit of 2026-11-03, 5.14).
- Comments, logs and docs say what the hardware is and does, not what it "answers" or how it "lies": a display has an
  orientation, a touch panel covers a display, a log says "no touch panel found" (the audit of 2026-11-03, item 5.12).
- What a board has and nobody asked for weighs the lowest price by the piece: of its chip, from `price` of its entry in
  catalog/devices, else of the cheapest chip of its role and variant, else of the cheapest module of its role, class or of all.
  A price of nothing is no price, and a part weighs at least a cent (Anton, 2026-11-03). One LED of a board is cents on every
  board, where the median of the modules of its role, rings and strips, made it 11 EUR. The WS2812B, a single SMD LED and an
  RGB LED of 5050 are in the catalog with prices of LCSC, and the LEDs of both Zero boards name the WS2812B.
- Temperature has the variants thermocouple, RTD and infrared: the MAX31865 is an RTD, and the words no longer take it for a
  thermocouple.
- The model gets in page_state why the boards that do not fit do not, the most common first, with how many boards each.
- tools/boards_mcp.py finds the versions of ESP-IDF and of the Arduino core on the computer, and a kit names which of its
  versions are there. A request the page cannot send to its solver is said in the console and counted on the page.
- `tools/boards_mcp.py --install` gives the server to the agent at once: to Claude Code for every folder when its command
  is there, otherwise in `.mcp.json` of the current folder.
- What the person fixes is theirs: the pin of a block, a part chosen in a block, a board fixed from its card. The solver keeps a
  fixed part for its block, even where the board has a part of that role, and tries only a fixed board. The model sets the
  blocks itself with `edit_blocks`, which replaces `propose_blocks`; the server and the page refuse it what the person fixed.
- `tools/import_fritzing.py` takes the chip named first in a title: a second run took CCS811 for the ENS160 module.
- `tools/import_addresses.py` writes the I2C addresses of imported chips, from ESPHome and from library headers with a
  permissive license. The solver gives a second part of one chip the next free address and tells the person to set it. A
  clash on an imported list stays an unknown, since the list can be short.
- `tools/import_board_manager.py` shifts the 8-bit addresses of the packs: ES8311 was at 0x30, not 0x18, on 16 boards.
  `check_format.py` refuses an imported board with the 8-bit form of an address its chip has.
- An addon on a port gives what a board lacks, by what the board has and the plug it takes: a PoE splitter on a board
  with Ethernet, a socket on the wall of a case. `plug` on a step of power, `rj45`, `usb_c`, `micro_usb` in
  `catalog/connectors/`.
- The first screen is a palette of roles, a canvas of blocks with a variant, a name and their settings, and the kits.
  Blocks of one role are one need under their names. A field keeps a description of the device. A part with no bus is
  wired by its first way.
- A DSI bus needs its speed only with a panel on it, so `esp32_p4_eth` lists its free connector.
- A question for the GPIOs already in use, for something added to wiring that exists.
- Reports from people: issue forms for a price and for a board, `.github/workflows/reports.yml` and
  `tools/take_report.py` turn a price into a pull request, and a card links to the form for what has no
  price. The page only opens a link. `examples/board_report` prints what a board can say about itself.
  A second run of one issue replaces its branch and opens no second pull request; a closed issue is left
  alone.
- A kit says which connectors come from memory and which supplies are not measured.
- The page keeps its answers over a reload, holds a count to its range, and shows an error under the top
  row. The commands of a new project take `board_select.py` from `managed_components`.
- A kit counts what is sold by the pack at the price of the pack.
- A character display may stand beside a graphics display: the glue has a slot for each. Built on a
  JC1060P470C, not flashed.
- Prices in any currency: `catalog/rates.json`, the rates of the ECB, written by `tools/update_rates.py`.
  The page shows prices and takes a budget in the currency chosen.
  A price of "less than 3" counts as 3 in a kit, not as 0.
- A card of a kit shows the front picture of its board, when the data has one.
- The page names a kit by its board and modules, lists the wires by module with their power, says how
  many kits fit and in what order, and drops a plan when the answers change. A board that does not fit
  gives the reasons of every choice of modules.
- DGX 0.10.3 at least: under ESP-IDF 6.1 a QSPI display on the IO MUX pins of SPI2 stayed dark.
- The ST7920 as a chip of the glue, and the module `lcd12864_st7920`. `mechanics` on a board or a
  module: outline, holes, what it takes to mount it; `window_mm` of a panel.
- Tones and PWM on the page: a list of outputs, each with its frequency, and for a tone a tolerance and
  jitter, for PWM the bits of duty, on one pin or two in antiphase, changing while running or not.
  `frequency_sources` of a chip holds LEDC, MCPWM, RMT, CLK_OUT and I2S with the APLL, with what can be
  changed while they run. The solver takes the first that holds and a kit lists timers and channels with
  the error and the kind of jitter. A crystal of a board counts: the Waveshare P4 boards have 32.768 kHz.
- Piezo discs in the catalog: the class `buzzer`, `ways` for a device with no bus.
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
