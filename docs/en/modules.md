# Modules

A module is a part connected to a board by wires: a display, a reader, a sensor, a strip of LEDs. It is
not a board of its own: a board of a program names it in `modules`, with the bus it joins and its pins.
The page writes such a board for a kit with modules. `examples/local_boards` has one written by hand: a
round QSPI display and a 2004 character LCD on a PCF8574 I2C backpack, both modules of the program.

## On a board of a program

```json
"buses": { "i2c": { "i2c0": { "sda": 4, "scl": 5 } } },
"modules": {
    "text": {
        "module": "lcd2004_pcf8574",
        "on": { "i2c.i2c0": {} },
        "supply": { "VCC": "5V" },
        "devices": { "lcd": { "config": { "primary": false } } }
    },
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
module of one part; a module of several takes its wiring by part, in `devices`, and so does a change of
one part, as the 2004 above that is not the primary display beside another. A part is named
`<use>_<part>` on the board, `text_lcd`, however many parts the module has, and what its parts say of
each other (`over`, `after`) follows the new names. A module is a board used as a part of another, with
the same fields, and it may have a chip of its own: a C6 on the SDIO of a P4 is a module with `mcu`.

## A character display

```c
board_character_display_t lcd;
if (board_character_display_init(&lcd)) {
    lcd_set_cursor(board_hd44780(&lcd), 0, 0);
    lcd_write_str(board_hd44780(&lcd), "hello");
}
```

`lcd_write_str` writes on through the memory of the HD44780, where row 0 of a 20x4 runs into row 2, so
a text longer than a row goes row by row, with `lcd_set_cursor` for each.

The display comes up cleared with its backlight on; `lcd.cols` and `lcd.rows` are its geometry. The
rest is hd44780's API (`hd44780.h`), brought in by a rule of the manifest when the board has such a
display. It uses the board's I2C master, shared with the board's touch panel and codec; the backpack's
address is in the module's data (`0x27`; a backpack with its address jumpers set differently needs the
data changed). On a board without it, `board_character_display_init` returns `false`: the same program
runs with and without the LCD.

## How a module is described

The 2004 of the example, `components/local-boards/modules/lcd2004_pcf8574/module.json`, has no chip and
no buses. Its `on` names only the kind of bus: the wiring is the board's.

```json
{
    "format": "jef-sure/boards", "format_version": 2, "kind": "module",
    "name": "lcd2004_pcf8574",
    "title": "2004 LCD on a PCF8574",
    "description": "...",
    "power": [{ "name": "VCC", "source": "connector", "volts": [4.5, 5.5], "feeds": ["lcd"] }],
    "devices": {
        "lcd": { "chip": "hd44780", "on": { "i2c": { "address": "0x27" } }, "logic": "VCC", "config": { "primary": true, "geometry": "20x4" } }
    }
}
```

The glue of the board defines `board_character_display_init` for it. `src/board_display_none.c` has
that function too, returning `false`, but under `#if !CONFIG_BOARD_DISPLAY_HD44780`, so on a board
with such a display the glue's function is the one that links.

## The catalog and the program

The modules of `catalog/modules/` are products the page offers in kits. A module of the program's own,
as a part its author wired from pieces, lies in `components/local-boards/modules/` of the program, in
the layout of `catalog/`, as the 2004 of the example does. The glue starts displays, touch panels,
sound and buttons; a module of another kind (a sensor, a radio) is data: a kit names the library of its
chip, and the program starts it.
