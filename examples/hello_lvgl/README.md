# LVGL on the chosen board

`boards` sets up the display and the touch panel,
[DGX-LVGL](https://components.espressif.com/components/jef-sure/dgx-lvgl)
connects them to LVGL, and `main.c` names no board.

```sh
python3 ../../tools/board_select.py cyd_s028r .      # or jc1060p470c, jc8012p4a1c, jc4827w543c
idf.py build flash monitor
```

The program draws one button in the middle of the screen and counts presses.
To change the board: `board_select.py` again with `--reset`, then `idf.py build`.

DGX-LVGL supports 16-bit screens only. The 10.1-inch JC8012P4A1C has no touch
unless the program embeds the firmware of its panel, see
[docs/en/touch-firmware.md](../../docs/en/touch-firmware.md).
