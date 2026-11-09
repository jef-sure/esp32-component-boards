# @TITLE@

@KITS@

## The first build

Each board of the program has `sdkconfig.defaults.<board>` here, its first line the command that makes it. The first
`reconfigure` fetches the component, and `board_select.py --again` makes the rest: the defaults of each board,
`CMakePresets.json` with a preset for each and the glue of a board of the program.

```sh
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py --again .
idf.py build flash monitor
```

When the page wrote the project through `tools/boards_mcp.py`, `--again` has run already: `idf.py build` is the first
command. The `build/` and `sdkconfig` the first `reconfigure` leaves are not read after it: each board builds in
`build/<board>` with its own.

`idf.py build` builds the current board, `@CURRENT@`; `idf.py --preset <board> build` another, each in `build/<board>`.
In VS Code, *ESP-IDF: Select Project Configuration* chooses the board. `board_select.py --current <board> .` makes
another one current. ESP-IDF 5 does not read the presets:

```sh
idf.py -B build/@CURRENT@ -D SDKCONFIG=sdkconfig.@CURRENT@ -D BOARD=@CURRENT@ build
```

`selection.json` keeps how the kits were chosen: the answers, what fits too and why the rest does not. Open this
folder on the page of the component to see it again, or to add a board.
