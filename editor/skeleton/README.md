# @TITLE@

@BOARD_TITLE@.

## What it takes

@PARTS@

## The wires

@WIRES@

## The first build

The board is chosen before the first build: the dependencies come from what it has.
`board_select.py` is in a checkout of https://github.com/jef-sure/esp32-component-boards.

```sh
python3 path/to/boards/tools/board_select.py @BOARD@ .
idf.py build flash monitor
```

After changing the board of a project already built, run `idf.py reconfigure build`.
