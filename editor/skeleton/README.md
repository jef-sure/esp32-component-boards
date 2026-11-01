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
idf.py reconfigure build flash monitor
```

`selection.json` keeps how this kit was chosen: the answers, what fits too and why the rest does not. Open
this folder on the page of the component to see it again.

After changing the board of a project already built, run `idf.py reconfigure build`.
