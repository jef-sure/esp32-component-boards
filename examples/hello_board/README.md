# The board the program runs on, as it is

The smallest program: it takes the board the build chose and tells what it is
and what it has (the display by its pixels and its millimetres, the character
display, the touch, the button, the sound), draws a frame, writes the board's
name on a character LCD if one is there, and sounds a second of a tone. Build
it for one board, it runs on another with the same `main.c`.

The board is chosen once, by the component's `tools/board_select.py`, which
writes `sdkconfig.defaults.board` here: the board's chip, its memory and its
flash, and the line that chooses it in the menu of the configuration. No
`set-target`, no `menuconfig`:

```sh
python3 ../../tools/board_select.py cyd_s028r .                # or jc1060p470c, jc8012p4a1c, jc4827w543c
python3 ../../tools/board_select.py jc1060p470c --module lcd2004_pcf8574 .  # a 2004 on the board's I2C
idf.py build flash monitor
```

To change the board: `board_select.py` again with `--reset` (ESP-IDF reads the
defaults only into a new `sdkconfig`), then `idf.py build`.

The 10.1-inch Guition JC8012P4A1C builds without the firmware of its touch
panel (the vendor's array has no licence to give away): the touch of that
board is off then, everything else works. To have it, see the docs of the
component (the touch firmware).
