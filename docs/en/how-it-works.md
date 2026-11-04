# How it works

The component has one idea: a board is described once, as data, and
everything that follows from that description is generated from it and
checked against it. This page explains the pieces and why they are shaped the
way they are.

## The data

`catalog/boards/<board>/board.json` is the only place a board is described; what
its chips are is described in `catalog/devices/` and `catalog/mcu/`, under it. It
names the chip, the buses the board wires (each by the host or port of the
chip it claims), and the devices on those buses: the display, the touch panel,
the sound, the button, the SD slot. A device references a bus by name and
carries its own strobe lines; two devices on one bus are two entries sharing
the bus's pins. The format is described in [data-format.md](data-format.md).

Beside the JSON lies `sdkconfig.defaults`, written by hand: what the chip, its
memory and its flash need from ESP-IDF's configuration, with the reasons in
comments. Its first two lines choose the chip and the board:

```
CONFIG_IDF_TARGET="esp32p4"
CONFIG_BOARD_SELECT_JC1060P470C=y
```

That is how a project chooses a board: by reading this file before its own
defaults. See [choosing-a-board.md](choosing-a-board.md).

## The generator

`tools/boards_gen.py` reads every `board.json`, checks it (unknown driver,
missing pin, a bus the display references but the board does not wire, pixels
and millimetres in different orientations) and writes:

- `boards/<board>/<board>.c`: the glue. It gives the data of the board as
  tables: the numbers of its buses, its SPI and I2C buses, its buttons, touch
  panels and sounds. A row of a touch panel or a sound names the function of its
  adapter (`function` of the chip in the record of its library) and the data of
  its kind. Only the bus and the screen of a display and the bus of a character
  display are functions, each a call filled from the record of the library. The
  core in `src/` reads the tables, and for a part the board has not a function of `src/`
  returns `false`. So **every** function of `boards.h` exists at link time on
  every board, and a program never needs `#if` on the board's name.
- `boards/<board>/display.cmake`: the primary display as shown, `BOARD_PIXELS` and
  `BOARD_MM`, which the component's `project_include.cmake` gives the CMake of a
  program when the board is chosen (see [choosing-a-board.md](choosing-a-board.md)).
- `boards/<board>/board.cmake`: the components the glue needs, derived from
  what the board has (`esp_driver_spi`, `jef-sure__dgx`, `espressif__esp_codec_dev`, ...).
  They are added after `idf_component_register`, as optional requirements
  (`idf_component_optional_requires`): a requirement that depends on the board
  chosen cannot stand in `REQUIRES`, which ESP-IDF reads before the
  configuration exists, and a component the manifest's rules did not bring is
  simply not there.
- `boards/boards.cmake`: the lists of boards and modules the component's
  `CMakeLists.txt` compiles by.
- `Kconfig`: the choice of the board, one option per module, and the hidden
  symbols described below.
- the `dependencies:` block of `idf_component.yml`, between two marker lines.
- the table of boards in the READMEs, between two marker lines.

The generated files are committed. A program that takes the component from
the registry builds without Python and without any tool of this repository.
`tools/check_boards.py` regenerates everything in memory and fails when a
committed file differs from the data, so the two cannot drift apart.

## The choice and the hidden symbols

Kconfig holds one `choice BOARD_SELECT` with an entry per board. An entry
depends on the chip (`IDF_TARGET_ESP32P4`) and `select`s the DGX drivers the
panel needs (`DGX_ENABLE_DSI`, `DGX_ENABLE_JD9165`).

Beside the choice are hidden `int` symbols: `BOARD_<BOARD>` is 1 when the
board is chosen, and feature symbols say what the chosen board has:
`BOARD_DISPLAY_GRAPHICS`, `BOARD_TOUCH`, `BOARD_TOUCH_GT911`,
`BOARD_TOUCH_XPT2046`, `BOARD_SOUND_ES8311`, `BOARD_DISPLAY_HD44780`. They are
numbers because the rules of the component manager compare numbers easily.

The rules in `idf_component.yml` look at those symbols:

```yaml
espressif/esp_lcd_touch_gt911:
  version: "^1"
  matches:
    - if: "$CONFIG{BOARD_TOUCH_GT911} == 1"
```

So a build for the CYD S028R downloads no GT911 driver and no codec library, and a
build with no board chosen downloads nothing of DGX. This is the mechanism of
`components/bsp_selector` in espressif/esp-bsp, with the symbols derived from
the data instead of written by hand.

The component's `CMakeLists.txt` compiles only the chosen board's glue, by
`CONFIG_BOARD_<BOARD>`, and includes its `board.cmake` for the link. With
*None* chosen it compiles `src/board_none.c` instead: the tables of a glue, all
empty, so the program links, every part returns `false` and `board_info()`
names the board `none`.

## The core

`src/` is small, depends on no board and names no library:

- `boards.c`: `board_info()`, from the `board_data` the glue defines.
- `board_bus.c`: `board_bus_get()`, the numbers of the board's buses by name.
- `board_i2c.c`: the board's I2C masters, one a port, made once under a lock
  from the pins the glue gives and shared by the touch panel, the codec, a
  character display module and the program.
- `board_spi.c`: the SPI buses open to the program and the hosts the board
  claims, from the table of the glue, and the SPI hosts the component sets up.
- `board_button.c`: the buttons, from the table of the glue.
- `board_touch.c`: the touch panels, each started once, on demand.
- `board_display_none.c`: the display functions of a board with no display of
  that kind, returning `false`.
- `board_none.c`: the empty tables when no board is chosen.
- `board_host.c`: `boards.h` of the computer over SDL2, the only source built for the linux target.
- `board_sound.c`: the task that paces samples to the output of the board.
- `board_touch_fw.c`: `board_touch_firmware_set()`, which keeps the firmware of a
  GSL3680 the program gives. Nothing in this component is weak: a strong definition
  of the program in a file linked by nothing else loses to a weak one of a static
  library, so the program gives the bytes by a call.

## The adapters

The code for each library lies in `adapters/<owner>__<name>/`, and every library
is on the same terms: a record in `catalog/libraries/` and, when this component
can start it, a directory here. The field `adapter` of the record names what the
glue includes (`headers`), what a program includes (`public`, in `include/` of the
directory) and what is compiled by which Kconfig symbol (`sources`); `function` of a chip
names the function of the adapter a table of the glue points to. A touch panel
goes through two: the driver gives an `esp_lcd_touch_handle_t`, and DGX-DI makes a
device and a pointer of it.

## What the component does and does not do

It sets hardware up and gives the program sizes, millimetres and orientation;
the headers of the adapters give the handles of the libraries that drive it: a
`dgx_screen_t`, a `dgx_di_device_t` and its pointer, an `hd44780_t`. From there
the program uses those libraries directly. The
component wraps no API of theirs; it is initialisation and the knowledge of
the board, nothing more. The one convenience beyond that is
`board_sound_start`, which runs the task that paces samples to the speaker.

## Modules

A module is a device any board's bus can carry: today the 2004 character LCD
on a PCF8574 backpack. It is described as a board without a chip
(`"kind": "module"`), has an option of its own in the menu
(`CONFIG_BOARD_MODULE_LCD2004_PCF8574`), and its `sdkconfig.defaults` turns
that option on. Its glue gives the table of its kind, `board_character_panel`;
the adapter of hd44780 defines `board_character_display_init` from it, and the one
of `src/board_display_none.c` that returns `false` is left out while a character
display is there (`#if !CONFIG_BOARD_DISPLAY_HD44780`).
See [modules.md](modules.md).

## The checks

Three layers, from fast to real:

1. `tools/check_boards.py`: the data reads; the generated files equal what the
   data says; every board's defaults choose it; every glue defines the whole
   API; no two owners of one GPIO, no output on an input-only one; every
   component the data names has a manifest rule.
2. `tools/check_boards.py --host-syntax`: every glue and the core compile on the host with
   `gcc -fsyntax-only -Werror` against the stub headers in `test/fake/`, which
   mirror the shape of the real ones. Catches a wrong argument type in seconds,
   without ESP-IDF.
3. CI (`.github/workflows/build.yml`): `examples/hello_board` is built for
   every board, with and without the module, under two versions of ESP-IDF,
   and `examples/hello_lvgl` for every board with a graphics display.
   Only this one proves the glue links.
