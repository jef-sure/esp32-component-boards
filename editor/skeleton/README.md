# @TITLE@

@BOARD_TITLE@.

## What it takes

@PARTS@

## The wires

@WIRES@

## The libraries

@LIBRARIES@

## The first build

The board is chosen before the first build: the dependencies come from what it has.
The first `reconfigure` fetches the component, and `board_select.py` comes with it.

```sh
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py --reset @BOARD@ .
```

`board_select.py` names the next command: `idf.py reconfigure build`, or `idf.py set-target <target>` first when the
build directory was made for another chip. Then `idf.py flash monitor`.

`selection.json` keeps how this kit was chosen: the answers, what fits too and why the rest does not. Open
this folder on the page of the component to see it again.

To change the board later: `board_select.py <board> --reset .` and the command it names. To build for several boards,
see choosing-a-board.md of the component.
