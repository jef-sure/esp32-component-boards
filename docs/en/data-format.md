# The data format: board.json

One file per board, `boards-data/<board>/board.json`. Format `jef-sure/boards`,
`format_version` 1. Everything the generator reads is here; the editor in
`editor/index.html` edits the same file with these rules checked as you type.

## The board

```json
{
    "format": "jef-sure/boards",
    "format_version": 1,
    "name": "jc1060p470",
    "title": "Guition JC1060P470",
    "description": "7-inch 1024x600 JD9165 on MIPI-DSI, GT911 touch, ES8311 sound",
    "mcu": { "target": "esp32p4", "flash_mb": 16, "psram_mb": 32, "notes": "..." },
    "buses": { ... },
    "display": { ... },
    "touch": { ... },
    "sound": { ... },
    "button": { ... },
    "sd": { ... }
}
```

| field | meaning |
|---|---|
| `name` | the directory name; lowercase letters, digits and `_`. It becomes `CONFIG_BOARD_SELECT_<NAME>` and the glue's file name |
| `title` | what the menu and `board_info()->title` show |
| `description` | one sentence; the menu's help and the glue's header comment |
| `mcu.target` | `esp32`, `esp32s3` or `esp32p4` (the chips with a table of SPI hosts in the generator) |
| `mcu.flash_mb`, `mcu.psram_mb` | for people; `sdkconfig.defaults` carries the settings |
| `mcu.notes` | what the `sdkconfig.defaults` encodes and why: a chip revision, a PSRAM speed |
| `module` | `true` for a device that rides another board's bus; then no `mcu`, no `buses`, no `button`, and the display is a character one |
| `extra_requires` | ESP-IDF components the glue needs at link beyond what the structure says; rarely needed |

## Buses

`buses` is a dictionary of kinds, each a dictionary of named buses. The name of
a bus is the claim of a host or port of the chip: `spi.spi2` is the chip's
SPI2, `i2c.i2c0` its I2C0, `i2s.i2s0` its I2S0. A device references a bus by
`"<kind>.<name>"`.

```json
"buses": {
    "spi":  { "spi2": { "hz": 40000000, "mosi": 13, "miso": 12, "sclk": 14 },
              "spi3": { "hz": 1000000, "mosi": 32, "miso": 39, "sclk": 25 } },
    "qspi": { "spi2": { "hz": 40000000, "d0": 21, "d1": 48, "d2": 40, "d3": 39, "sclk": 47 } },
    "i2c":  { "i2c0": { "sda": 7, "scl": 8 } },
    "i2s":  { "i2s0": { "mclk": 13, "bclk": 12, "ws": 10, "dout": 9, "din": null } },
    "dsi":  { "dsi0": { "lanes": 2, "lane_mbps": 750, "phy_ldo_chan": 3, "phy_ldo_mv": 2500 } },
    "p8":   { "i80":  { "d0": 0, "...": 0, "d7": 0, "wr": 0, "rd": null, "dc": 0, "hz": 10000000 } },
    "sdio": { "sdio0": { "clk": 18, "cmd": 19, "d0": 14, "d1": 15, "d2": 16, "d3": 17, "reset": 54 } }
}
```

Kinds the component sets up itself, with the fields it requires:

| kind | name | fields |
|---|---|---|
| `spi` | a host: `spi2`, `spi3` | `mosi`, `miso`, `sclk`; `hz` optional |
| `qspi` | a host: `spi2`, `spi3` | `d0`..`d3`, `sclk`; `hz` optional |
| `i2c` | a port: `i2c0`, `i2c1` | `sda`, `scl` |
| `i2s` | a port: `i2s0`, `i2s1` | `mclk`, `bclk`, `ws`, `dout`; `din` a pin or `null` |
| `dsi` | `dsi0` | `lanes`, `lane_mbps`, `phy_ldo_chan`, `phy_ldo_mv` |
| `p8` | any | `d0`..`d7`, `wr`, `dc`, `hz`; `rd` a pin or `null` |

Any other kind (`sdio`, `uart`, the CYD's `sdspi` for SD pins that have no
host left) is kept as data: every value must be a number, a string or `null`.
The program reads it with `board_bus_get("sdio.sdio0", "clk", &pin)`. When
the component learns to set a kind up, it moves into the table above and gets
glue; the data does not change.

Only one I2C bus is set up by the component (the first by name); its master
is shared by the touch, the codec and a character display module.

## The display

A pixel panel driven by DGX:

```json
"display": {
    "driver": "ili9341",
    "bus": { "bus": "spi.spi2", "cs": 15, "dc": 2 },
    "panel": { "width": 240, "height": 320, "mm_w": 43, "mm_h": 58 },
    "original_orientation": { "x": "right-left", "y": "top-bottom", "swap": true },
    "rst": null,
    "backlight": 21,
    "backlight_on_high": true,
    "depth_bits": 16
}
```

| field | meaning |
|---|---|
| `driver` | `jd9165`, `jd9365` (MIPI-DSI), `nv3041a` (QSPI), `ili9341` (SPI or i80). The generator knows which DGX header, which `DGX_ENABLE_*` symbols and which pixel depths each takes |
| `bus.bus` | a name from `buses` of kind `spi`, `qspi`, `dsi` or `p8` |
| `bus.cs`, `bus.dc` | the panel's own strobes: `cs` and `dc` on SPI, `cs` on QSPI and i80, none on DSI |
| `panel` | the glass **as the controller scans it**: pixels and millimetres in the same direction. The generator refuses pixels and millimetres that lie different ways or whose proportions differ by more than a fifth |
| `original_orientation` | how the board shows the glass: `x` is `left-right` or `right-left`, `y` is `top-bottom` or `bottom-top`, `swap` true when the display's x runs along the glass's columns (landscape on a portrait panel). The glue applies this at init; `board_display` reports the size as it lies after the swap |
| `rst`, `backlight` | pins or `null`; `backlight_on_high` says the level that lights it |
| `depth_bits` | 16 everywhere, 24 also on the DSI panels |

A character display (hd44780) on a board or as a module:

```json
"display": {
    "driver": "hd44780",
    "geometry": "20x4",
    "bus": { "bus": "i2c.i2c0", "address": "0x27" }
}
```

`bus.bus` is `i2c.<name>` with the backpack's `address`, or `gpio.4bit` /
`gpio.8bit` with `bus.pins`: `rs`, `en`, `d4`..`d7` (and `d0`..`d3` for 8-bit).
Geometries: `8x2`, `16x2`, `16x4`, `20x2`, `20x4`, `40x2`.

## The touch

```json
"touch": {
    "kind": "gt911",
    "bus": "i2c.i2c0",
    "address_try": ["0x5d", "0x14"],
    "x_max": 1023, "y_max": 599,
    "fingers": 5,
    "rst": null, "int": null,
    "calibration": { ... }
}
```

| kind | bus | fields |
|---|---|---|
| `gt911` | `i2c.*` | `address_try` (the addresses tried in order; the GT911 picks one at power-up), `fingers`, `rst`, `int` |
| `gsl3680` | `i2c.*` | `rst`, `int`, `fingers`; the firmware comes from the program, see [touch-firmware.md](touch-firmware.md) |
| `esp_lcd_touch` | `spi.*` | `component` (`namespace/name` in the registry, with its version in the generator's table), `header`, `cs`, `irq`, `hz` (1 MHz default), `fingers`, `resistive` |

`x_max` and `y_max` are the range of the raw coordinates the panel gives.
`calibration` is the measured calibration of DGX-DI, see
[calibration.md](calibration.md); `"measured": false` inside it marks a
placeholder, and the glue warns at start.

A touch of the `esp_lcd_touch` kind on a bus of its own (not the display's)
gets its SPI host initialised by the glue; on the display's bus, DGX has done
that already.

## The sound

```json
"sound": { "kind": "es8311", "bus": "i2c.i2c0", "address": "0x18", "i2s_bus": "i2s.i2s0",
           "pa": 11, "pa_voltage": 5.0, "codec_dac_voltage": 3.3, "sample_rate": 22050, "volume": 25 }
```

```json
"sound": { "kind": "dac", "out": 26, "pa": null, "sample_rate": 22050 }
```

`es8311`: the codec on an I2C bus (`bus`, `address`) streaming over an I2S bus
(`i2s_bus`), its amplifier's enable pin `pa` (or `null`), the voltages
esp_codec_dev wants for its gain, the `volume` of the codec (0..100).
`dac`: the ESP32's own DAC on GPIO 25 or 26, fed by DMA at `sample_rate`;
`pa` a pin or `null`. 16-bit mono samples in both cases.

## The button, the SD slot

```json
"button": { "pin": 35, "active_low": true },
"sd": { "bus": "spi.spi3", "cs": 5 }
```

The slot is a device on a plain SPI bus of the board, its `cs` its own. When
no host is left for it (the CYD: SPI2 has the display, SPI3 the touch), its
pins go into `buses` under a kind the component does not set up, as data.

## What the generator refuses

Besides the shapes above: a bus name the chip has no host for; a device on a
bus the board does not wire; a touch without a display; a `dac` sound on a
chip other than the ESP32; a module with a chip, buses or a button of its own;
a GPIO the chip has not; an output on an input-only GPIO (34..39 on the
ESP32); two owners of one GPIO. `tools/board_pins.py <board>` shows the map
these last checks are made on.
