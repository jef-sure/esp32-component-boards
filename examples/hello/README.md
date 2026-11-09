# hello

The program of the [quick start](../../docs/en/quick-start.md): it tells the board, its display, its touch and its
button, and paints the display white with a blue band at the top. The component comes from the registry.

```sh
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .   # or another board of the README
idf.py build flash monitor
```

ESP-IDF 5 does not read the presets the second command writes:
`idf.py -B build/cyd_s028r -D SDKCONFIG=sdkconfig.cyd_s028r -D BOARD=cyd_s028r build flash monitor`.
