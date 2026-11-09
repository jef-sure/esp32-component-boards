# multi_board

One program built for two boards with different chips, each with its own defaults and build directory. See
[choosing-a-board.md](../../docs/en/choosing-a-board.md#several-boards).

```sh
python3 ../../tools/board_select.py cyd_s028r jc8012p4a1c .
idf.py build                          # ESP-IDF 6: the current board, the first named, in build/cyd_s028r
idf.py --preset jc8012p4a1c build     # the other, in build/jc8012p4a1c
```

`board_select.py` writes `sdkconfig.defaults.cyd_s028r`, `sdkconfig.defaults.jc8012p4a1c` and `CMakePresets.json`, a
preset for each board in the order named and `default` for the current one; `board_select.py --current jc8012p4a1c .`
makes the other current. ESP-IDF 5 does not read presets:

```sh
idf.py -B build/cyd_s028r -D SDKCONFIG=sdkconfig.cyd_s028r -D BOARD=cyd_s028r build
idf.py -B build/jc8012p4a1c -D SDKCONFIG=sdkconfig.jc8012p4a1c -D BOARD=jc8012p4a1c build
```

A project of its own commits these files, so that a fresh clone reads them before the component is downloaded; this
example does not, so that they do not age beside the catalog, and CI writes them before it builds.
