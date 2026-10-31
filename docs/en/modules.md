# Modules

A module is a device that is not a board of its own but rides a bus of
whichever board is chosen. Today there is one: the 2004 character LCD on a
PCF8574 I2C backpack, the common 20x4 display with four pins (VCC, GND, SDA,
SCL).

## Turning it on

```sh
python3 tools/board_select.py jc1060p470c --module lcd2004_pcf8574 .
```

The module's `sdkconfig.defaults` is appended to the board's and sets
`CONFIG_BOARD_MODULE_LCD2004_PCF8574=y`. That option is also in the menu,
under *Boards*, below the choice of the board. With it on, the component
brings `jef-sure/hd44780` in by a manifest rule and compiles the module's glue
beside the board's.

## Using it

```c
struct board_character_display lcd;
if (board_character_display_init(&lcd)) {
    lcd_set_cursor(board_hd44780(&lcd), 0, 0);
    lcd_write_str(board_hd44780(&lcd), "hello");
}
```

`lcd_write_str` writes on through the memory of the HD44780, where row 0 of a 20x4 runs into row 2, so
a text longer than a row goes row by row, with `lcd_set_cursor` for each.

The display comes up cleared with its backlight on; `lcd.cols` and `lcd.rows`
are its geometry. The rest is hd44780's API (`hd44780.h`). The module uses the
board's I2C master, shared with the board's touch panel and codec; the
backpack's address is in the module's data (`0x27`; a backpack with its
address jumpers set differently needs the data changed).

On a board without the module, `board_character_display_init` returns
`false`: the same program runs with and without the LCD.

## How it is described

`catalog/modules/lcd2004_pcf8574/module.json` has no chip and no buses. Its `on`
names only the kind of bus: the wiring is the project's, and the glue today puts
it on the I2C bus of the board.

```json
{
    "format": "jef-sure/boards", "format_version": 2, "kind": "module",
    "name": "lcd2004_pcf8574",
    "title": "2004 character LCD on a PCF8574 backpack",
    "description": "...",
    "devices": {
        "lcd": { "chip": "hd44780", "on": { "i2c": { "address": "0x27" } }, "config": { "primary": true, "geometry": "20x4" } }
    }
}
```

Its glue defines only the function of its kind,
`board_character_display_init`. Every board's glue has that function too,
returning `false`, but under `#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY`, so
when the module is on the board's version steps aside and the module's is the
one that links. A board that has an HD44780 soldered on (on I2C or on GPIOs)
describes it in its own `display` and defines the real function itself; then
no module is needed.

## Adding a module

Another character display on a backpack is another directory with its
geometry and address. A module of another kind (a sensor, a radio) needs a
kind in `boards.h`, a branch in the generator and a feature symbol; that is
the shape planned for the next version, where devices are a list rather than
one slot per kind.

## On a board

A module is a board used as a part of another, with the same fields, and it may have a chip of its
own: a C6 on the SDIO of a P4 is a module with `mcu`. A board that always has a module names it:

```json
"modules": {
    "screen": { "module": "lcd2004_pcf8574", "on": { "i2c.i2c0": {} } },
    "tft": {
        "module": "tft_with_touch",
        "on": { "spi.spi2": {} },
        "devices": {
            "lcd": { "on": { "spi.spi2": { "cs": 5 } }, "pins": { "dc": 2, "rst": 4 } },
            "touch": { "on": { "spi.spi2": { "cs": 16 } }, "pins": { "int": 17 } }
        }
    }
}
```

`on` says which bus each kind of bus of the module joins. `pins` and `config` beside it are for a
module of one part; a module of several takes its wiring by part, in `devices`. A part is named
`<use>_<part>` on the board, `screen_lcd`, however many parts the module has, and what its parts
say of each other (`over`, `after`) follows the new names.
