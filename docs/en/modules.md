# Modules

A module is a device that is not a board of its own but rides a bus of
whichever board is chosen. Today there is one: the 2004 character LCD on a
PCF8574 I2C backpack, the common 20x4 display with four pins (VCC, GND, SDA,
SCL).

## Turning it on

```sh
python3 tools/board_select.py jc1060p470 --module lcd2004_pcf8574 .
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
    lcd_set_cursor((hd44780_t *)lcd.lcd, 0, 0);
    lcd_write_str((hd44780_t *)lcd.lcd, "hello");
}
```

The display comes up cleared with its backlight on; `lcd.cols` and `lcd.rows`
are its geometry. The rest is hd44780's API (`hd44780.h`). The module uses the
board's I2C master, shared with the board's touch panel and codec; the
backpack's address is in the module's data (`0x27`; a backpack with its
address jumpers set differently needs the data changed).

On a board without the module, `board_character_display_init` answers
`false`: the same program runs with and without the LCD.

## How it is described

`boards-data/lcd2004_pcf8574/board.json` is a board with `"module": true`, no
chip, no buses and no button, and a character display whose bus is the
carrier's `i2c.i2c0`:

```json
{
    "format": "jef-sure/boards", "format_version": 1,
    "name": "lcd2004_pcf8574",
    "title": "2004 character LCD on a PCF8574 backpack",
    "description": "...",
    "display": { "driver": "hd44780", "geometry": "20x4", "bus": { "bus": "i2c.i2c0", "address": "0x27" } },
    "module": true
}
```

Its glue defines only the function of its kind,
`board_character_display_init`. Every board's glue has that function too,
answering `false`, but under `#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY`, so
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
