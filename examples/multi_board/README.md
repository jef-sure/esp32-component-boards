# multi_board

One program built for two boards with different chips, each with its own defaults and build directory. See
[choosing-a-board.md](../../docs/en/choosing-a-board.md#several-boards).

```sh
python3 ../../tools/board_select.py cyd_s028r jc8012p4a1c .
idf.py -B build-cyd_s028r -D SDKCONFIG=build-cyd_s028r/sdkconfig -D BOARD=cyd_s028r build
idf.py -B build-jc8012p4a1c -D SDKCONFIG=build-jc8012p4a1c/sdkconfig -D BOARD=jc8012p4a1c build
```

`board_select.py` writes `sdkconfig.defaults.cyd_s028r` and `sdkconfig.defaults.jc8012p4a1c`. A project of its own
commits them, so that a fresh clone reads them before the component is downloaded; this example does not, so that
they do not age beside the catalog, and CI writes them before it builds.
