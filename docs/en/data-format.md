# The data format

Everything the tools know about hardware is in `catalog/`, format
`jef-sure/boards`, `format_version` 2. One schema, `catalog/format.schema.json`,
describes every file. `tools/check_format.py` checks them.

| path | what it holds |
|---|---|
| `catalog/boards/<name>/board.json` | a board: its wiring and its values; `sdkconfig.defaults` beside it |
| `catalog/modules/<name>/module.json` | a module: devices without a board, the wiring left to the project |
| `catalog/devices/<family>/device.json` | a device: its roles, addresses, parameters, what the chip itself can do |
| `catalog/addons/<name>/addon.json` | an addon: a part in the way of lines, a supply or a port |
| `catalog/platforms/<name>/platform.json` | a platform: which chips each version takes, where its libraries are published |
| `catalog/rubrics/<name>/rubric.json` | what an audit of a kind of library asks |
| `catalog/libraries/<ecosystem>/<owner>/<name>/library.json` | a library: which chips it supports, how it starts them, what it can do with them |
| `catalog/mcu/<target>/mcu.json` | a chip: its GPIOs, hosts and what it has. Made from ESP-IDF by `tools/make_mcu.py` |
| `catalog/connectors/<type>/connector.json` | a type of connector: pins, voltage |
| `catalog/rules.json` | what makes a board wrong and a schema cannot see |
| `catalog/questions.json` | what the selection asks, and what each answer asks of a board |
| `catalog/judgements.json` | the judgements of the solver: how it chooses where a choice is open, each with an id |
| `catalog/index.json` | the list of these files for the page of the editor, made by `tools/boards_gen.py --all` |
| `components/local-boards/` of a program | what is the program's own, in the same layout: read before the catalog |

Names are lowercase letters, digits and `_`: they become Kconfig symbols.

## How a board is put together

A board names devices of the catalog and keeps only what is its own. The tools
merge the layers by JSON Merge Patch (RFC 7386), general to particular:

1. the device of the catalog;
2. its family variant (`"variant": "scd41"`);
3. the board;
4. a variant of the board (`"extends": "cyd_s028r"`);
5. mine for this model, then the project.

A value in a later layer replaces the earlier one, and `null` removes a field.
That is why a line that is not wired is `"nc"`, not `null`. An array is replaced
whole, so what a layer may change is an object with named entries.

The schema checks each file as written, and the merged board once more. Then
`catalog/rules.json` is applied: `tools/rules.py` in the generator and
`editor/rules.js` in the editor read the same rules.

## The board

```json
{
    "format": "jef-sure/boards",
    "format_version": 2,
    "kind": "board",
    "name": "jc1060p470c",
    "title": "Guition JC1060P470C",
    "description": "7-inch 1024x600 JD9165 on MIPI-DSI, GT911 touch, ES8311 sound",
    "notes": ["what is special about it"],
    "mcu": { "target": "esp32p4", "flash_mb": 16, "psram_mb": 32, "notes": "..." },
    "buses": { "...": "..." },
    "devices": { "...": "..." }
}
```

| field | meaning |
|---|---|
| `name` | the directory name. It becomes `CONFIG_BOARD_SELECT_<NAME>` and the glue's file name |
| `title` | what the menu and `board_info()->title` show |
| `description` | one sentence: the menu's help and the glue's header comment |
| `maker`, `part` | who makes the board and its name for it, as `JC1060P470C`. A module has them too |
| `revision` | the revision of the printed board this file describes, as its maker writes it |
| `price`, `tariff` | what it costs and its customs code, see [Price](#price) |
| `notes` | what is special about it, in words, a text or a list. Tools show it and do not read it |
| `mcu.target` | a directory of `catalog/mcu/` |
| `mcu.part` | the chip as its maker names it, as `ESP32-D0WD-V3` |
| `mcu.flash_mb`, `mcu.psram_mb` | for people; `sdkconfig.defaults` carries the settings |
| `mcu.revision` | the revision of the chip: its speeds and lines come from `catalog/mcu/`, see [choosing-a-board.md](choosing-a-board.md) |
| `mcu.psram_mhz`, `mcu.cpu_mhz` | a clock below what the revision takes, when the board holds it down |
| `mcu.notes` | what the `sdkconfig.defaults` encodes and why |
| `mcu.controls` | values for the parameters of the chip, such as `wifi_tx_power` |
| `extends` | the board this one is a variant of |
| `power` | the lines of supply and the strobes, in the order of the start, see [Power](#power) |
| `shared_pins` | lines several devices use on purpose |
| `connectors`, `images`, `checked`, `origin` | see below |

Fields named `x_*` are free: tools do not read them.

## Lines

A wire is written the same way everywhere:

| form | meaning |
|---|---|
| `21` | a GPIO |
| `"nc"` | not wired |
| `{ "gpio": 0, "active": "low", "pull": "up" }` | a GPIO with its properties |
| `{ "gpio": 4, "analog": [600, 960] }` | read through the ADC: a window in millivolts |
| `{ "via": "io", "bit": 3 }` | a bit of an expander |
| `{ "via": "pmu", "rail": "dldo1" }` | a rail of a PMIC |
| `{ "via": "adc", "channel": 2 }` | a channel of an ADC chip |

Buttons on a resistor ladder share a GPIO. Each is a device with its own window,
and windows may touch but not overlap.

## Buses

`buses` is a dictionary of kinds, each a dictionary of named buses. The name of
an SPI, I2C or I2S bus is a host or port of the chip: `spi.spi2` is its SPI2,
`i2c.i2c0` its I2C0. A bus made in software is `soft0`.

```json
"buses": {
    "spi":  { "spi2": { "hz": 40000000, "mosi": 13, "miso": 12, "sclk": 14 } },
    "qspi": { "spi2": { "hz": 40000000, "d0": 21, "d1": 48, "d2": 40, "d3": 39, "sclk": 47 } },
    "i2c":  { "i2c0": { "sda": 7, "scl": 8 } },
    "i2s":  { "i2s0": { "mclk": 13, "bclk": 12, "ws": 10, "dout": 9, "din": "nc" } },
    "dsi":  { "dsi0": { "lanes": 2, "lane_mbps": 750, "phy_ldo_chan": 3, "phy_ldo_mv": 2500 } }
}
```

| kind | fields |
|---|---|
| `spi` | `mosi`, `miso`, `sclk`; `hz` optional |
| `qspi` | `d0`..`d3`, `sclk`; `hz` optional |
| `i2c` | `sda`, `scl`; `hz` optional |
| `i2s` | `bclk` and `ws`, or `clk` for PDM (`"nc"` for a PDM output with no clock line, into a filter); `mclk`, `dout`, `din` optional; `dout2`, `din2`..`din4` for more PDM lines |
| `dsi` | `lanes`, `lane_mbps`, `phy_ldo_chan`, `phy_ldo_mv` |
| `p8` | `d0`..`d7`, `wr`, `dc`, `hz`; `rd` optional |
| `rgb` | `pclk`, `data` (a list); `de`, `vsync`, `hsync`, `hz` optional |
| `csi` | `lanes`; `lane_mbps`, `phy_ldo_chan`, `phy_ldo_mv` optional. The lanes have pins of their own |
| `dvp` | `pclk`, `vsync`, `de`, `data` (8 to 16 lines); `hsync` optional |
| `uart` | `tx`, `rx`; `rts`, `cts`, `baud` optional |

Any other kind (`sdio`, `sdspi`) is kept as data. The program reads it with
`board_bus_get("sdio.sdio0", "clk", &pin)`.

## Devices

`devices` holds named devices. A device with `chip` has the entry of
`catalog/devices/` under it, so the board writes only what differs:

```json
"sound": {
    "chip": "es8311",
    "on": { "i2c.i2c0": {}, "i2s.i2s0": {} },
    "pins": { "pa": 11 },
    "config": { "sample_rate": 22050, "pa_voltage": 5.0, "codec_dac_voltage": 3.3 },
    "controls": { "volume": { "start": 25 } }
},
"boot": { "class": "button", "pins": { "in": { "gpio": 35, "active": "low" } } }
```

| field | meaning |
|---|---|
| `chip` | a directory of `catalog/devices/`. A part with no entry, such as a button, gives `class` itself |
| `chip_try` | instead of `chip`: the chips it can be, found at start, in the order to try. The device gives its `class` itself |
| `variant` | a member of the family |
| `library` | which library the device uses; the loader fills it in for a chip with one library |
| `library_version` | the version of the library, when it is not the one the record describes |
| `needs` | what the program needs of the library, as things of its `supports` |
| `firmware_version` | the firmware of this device, when it is not the newest described |
| `used` | `false`: a project leaves this part of its board alone: its pins stay taken, no library comes for it, its `board_*_init` returns false |
| `maker`, `part`, `marking`, `ref`, `draw` | what it physically is, see [What is on the board](#what-is-on-the-board) |
| `price`, `tariff`, `count` | for what is bought apart, see [Price](#price) |
| `class` | a role or a list of roles: `display`, `touch`, `audio`, `storage`, `radio`, `network`, `nfc`, `sensor`, `io_expander`, `pmic`, `battery_adc`, `adc`, `camera`, `imu`, `rtc`, `button`, `encoder`, `keyboard`, `gamepad`, `led`, `usb`, `gps`, `motor`, `i2c_mux`, `fuel_gauge`, `other` |
| `on` | the buses of the device, each with what belongs to that connection: `address`, `address_try`, `cs`, `hz`, `mode`, `role`; `format` of an I2S bus (`std`, `tdm`, `pdm`; the two directions of a port can differ); `sio` of an SPI bus with data both ways on MOSI |
| `pins` | its other lines: `dc`, `rst`, `backlight`, `int`, `te` |
| `config` | facts that do not change |
| `controls` | parameters, see below |
| `provides` | what it gives, with its figures, see below |
| `start` | `defer` for a device silent until its first event, `after` for an order |

An entry of the catalog writes `on` by kind, `"i2c": { "address": "0x18" }`, and
may mark a kind `required`. A channel of a multiplexer is `i2c.mux.ch0`.

`address_try` lists the addresses a chip can have, the first as it comes. A wiring that sets `address` chooses one of them.
An empty list in a project says that none the data lists is free: the data of an imported chip can be short.

### Display

`config.kind` comes from the chip: `graphics` or `character`.

```json
"lcd": {
    "chip": "ili9341",
    "on": { "spi.spi2": { "cs": 15 } },
    "pins": { "dc": 2, "rst": "nc", "backlight": { "gpio": 21, "active": "high" } },
    "config": { "primary": true, "panel": { "width": 240, "height": 320, "mm_w": 43, "mm_h": 58 }, "depth_bits": 16 },
    "controls": { "orientation": { "start": { "x": "right-left", "y": "top-bottom", "swap": true } } }
}
```

`panel` is the glass as the controller scans it: pixels and millimetres in the
same direction. The millimetres are optional, but go together: without them
`board_display.mm_w` and `mm_h` are 0. `orientation` is how the board shows it. `swap` is true when the
display's x runs along the glass's columns. `primary` marks the main display.
A character display has `config.geometry`, such as `"20x4"`.

`config.timing` is for a panel fed without pause, RGB or MIPI-DSI video:
`pclk_hz`, `hsync_pulse`, `hsync_back`, `hsync_front`, `vsync_pulse`, `vsync_back`,
`vsync_front`, and optionally `pclk_edge`, `hsync_active`, `vsync_active`,
`de_active`. What it stands on goes in `checked`: a maker's figures are a hint until
measured on the board.

Displays shown as one screen are a group. `side_by_side` is
`dgx_vscreen_2h_init(left, right)`: the width adds up, the height is the larger,
and both displays must have one depth. Each keeps its own bus and orientation:

```json
"display_groups": { "wide": { "how": "side_by_side", "left": "left", "right": "right", "primary": true } }
```

### Touch

`config.over` names the display the touch covers, or `"none"`. The generator
needs a display: `"none"` waits for DGX-DI. `x_max` and `y_max` are the largest
raw coordinates, not their number; the calibration must have the same values and
the size of the panel. See [calibration.md](calibration.md). `fingers` comes from the
entry of the chip; a board writes it only when it differs.

### Sound

| chip | what it is |
|---|---|
| `es8311` | a codec on I2C and I2S; `pins.pa` is its amplifier's enable; `controls.volume` |
| `esp32_dac` | the ESP32's own DAC, `pins.out` on GPIO 25 or 26 |
| `i2s_amp` | an amplifier on I2S with no codec and no volume: a program scales its samples |

Samples are 16-bit mono in all cases. `config.clock` says what a codec takes its
clock from: `mclk`, or `bclk` when it derives it from the bit clock.

### Camera

A device of class `camera`: a sensor on a bus for its picture and usually on I2C for
its registers. A board may have the connector and no sensor: then the bus and the
connector are all it says. A sensor on a ribbon is a module:

```json
"buses": { "csi": { "csi0": { "lanes": 2, "phy_ldo_chan": 3, "phy_ldo_mv": 2500 } } },
"modules": { "camera": { "module": "ov02c10_csi", "on": { "csi.csi0": {}, "i2c.i2c0": {} } } }
```

A parallel camera has `xclk`, `rst` and `pwdn` in `pins` and `config.xclk_hz` when the
board gives its clock. `chip` may be missing, as an imported board often does not
name the sensor, and `chip_try` says the ones to try. The entry of a sensor says
`provides.camera`: `width_max`, `height_max`, `formats`. The modes a library has are
in its `supports.modes`. The glue does not start a camera yet: it is kept as data.

### SD

A device of class `storage` on an SPI bus, with its `cs` in `on`. When no host is
left for it, as on the CYD S028R, its bus has a kind the component does not set
up, `sdspi`.

### Battery

A device of class `battery_adc`, read through a divider:

```json
"battery": { "class": "battery_adc", "pins": { "in": 5 }, "config": { "divider": { "top_ohm": 33000, "bottom_ohm": 100000 } } }
```

The battery goes through `top_ohm` to the ADC, and `bottom_ohm` goes from there to
ground. `switch` is a line that feeds the divider only for a reading, `settle_us` the
wait after it. The line is owned like any other.

### What is on the board

A device names what it physically is: `maker`, `part`, `ref` as on the schematic, and
`marking` when only the package can be read. The entry of a chip gives `maker`, `part`
and `compat`, a board writes `part` when it knows more, as `ES8311-S`. A family gives
`part` and `compat` in each variant. `maker` is a short name of ours; `compat` is the
compatible of devicetree, the only field kept for a format outside.

A part a program does not see is a device of class `other` with no `on`:

```json
"reg_esp": { "class": "other", "ref": "U7", "part": "AMS1117-3.3" }
```

`draw` gives its current by mode in mA, here or in the entry of the chip, and
`mcu.draw` the same for the chip of the board:

```json
"draw": { "active": { "ma": 80, "ma_peak": 500 }, "sleep": { "ma": 1 } }
```

An empty place on a board is said in `notes`.

## Power

`power` lists the lines of supply and the strobes in the order of the start. A step
takes only from a step before it, so the list cannot make a loop.

```json
"power": [
    { "name": "USB", "source": "usb", "mv": 5000 },
    { "name": "VIN", "source": "vin" },
    { "name": "5V", "from": [{ "name": "USB", "through": "d_usb" }, { "name": "VIN", "through": "q_vin" }] },
    { "name": "3V3", "from": "5V", "through": "reg_tft", "regulator": "ldo", "mv": 3300, "ma_max": 1000, "dropout_mv": 1300, "feeds": ["lcd", "touch"] },
    { "name": "PERIPH", "from": "3V3", "line": 10, "level": 1, "delay_ms": 100, "feeds": ["keyboard"] },
    { "line": 39, "level": 1, "why": "CS of the SD card, before the bus starts" }
]
```

| field | meaning |
|---|---|
| `name` | as the schematic or the board writes it. A contact of a connector with this text is this line |
| `source` | where a supply comes in: `usb`, `vin`, `battery`, or `connector` for a module fed by its board |
| `from` | the step it takes from, or a list of several ways in: names, or objects with `name`, `through`, `dropout_mv` |
| `through` | the device it goes through, or a list in order. With a list in `from` it comes after the way of each |
| `regulator` | `ldo` passes its current on; `buck`, `boost` and `charger` convert power, so the current differs on each side |
| `efficiency_percent` | of a converter |
| `line`, `level`, `delay_ms` | what switches it or the rail of a PMIC, the level that turns it on, the wait after |
| `mv`, `ma_max` | its voltage and the most it gives |
| `dropout_mv` | what is lost from input to output: the least an `ldo` needs, the drop of a diode |
| `feeds` | devices, `mcu`, or a step of a module as `<use>_<name>`. A chip on two lines is in both |
| `why` | what the step is, in words |

A step with a name is a line of supply and owns its GPIO. A step with no name is a
strobe on a line a device owns. A line a device already owns stays with the device,
and `why` says so: on the JC1060P470C the boost converter of the backlight is enabled
by the backlight line of the display.

The list is one array, so a layer replaces it whole. A layer that removes a device
with `null` needs no new list: the device goes from `feeds` by itself. The steps of a
module follow those of the board, named `<use>_<name>`.

## Parameters

`controls` holds what can differ from what a device starts with:

```json
"controls": {
    "volume": { "how": "codec_volume", "min": 0, "max": 100, "read": "command", "start": 25 },
    "interface": { "how": "switch", "lines": ["I0", "I1"], "values": { "i2c": [1, 0], "spi": [0, 1] }, "read": "none" }
}
```

`how` says what sets it, from a closed list; for what a program can set, it is
one C function in the adapter of the library. `switch`, `solder` and `derived` are for a person or
for the tools. `read` says how the value can be known: `command`, `probe` or
`none`. `start` is the value of the board. A value a person wants lies in a later
layer and is checked against `min`, `max` and `values`.

`shared_pins` can hold a line only while a parameter has a value:

```json
"boot_te": { "line": 0, "devices": ["lcd", "boot"], "only_while": { "device": "lcd", "control": "te", "value": "off" } }
```

## What a device gives

```json
"provides": {
    "co2": { "unit": "ppm", "output": [0, 40000], "specified": [400, 5000],
             "accuracy": [{ "from": 400, "to": 1000, "plus_minus": 50, "percent": 2.5 }] }
}
```

A chip names what it needs beside a bus in `lines` of its connection, as `"on": {"spi": {"required": true, "lines": ["busy", "rst"]}}`: a board wires them in `pins`, and a rule refuses a board that does not.

`output` is what it can report, `specified` is where the maker promises accuracy.
Other figures depend on the kind, such as `standards`, `targets_max` and `range_mm`
of an NFC reader. A figure lies with what sets it: a limit of the
chip here, a limit of a library in its record, see [Libraries](#libraries).

A transmitter has `freq_mhz`, the carrier as a range, and two figures of power.
`tx_mw_max` is the most it takes from its supply, from the chip's datasheet; its current by
mode is in `draw`.
`radiated_mw` is what leaves the antenna: it depends on the antenna, so a module or a
board keeps it, measured, with a `checked` entry. A datasheet of an NFC reader gives no
radiated power. A part of a module inherits the figures of its chip and can replace them.

An antenna is not the
chip's: a module or a board names it in `antenna` (`kind`: `on_board`, `connector`,
`wire`) and keeps its figures, with a `checked` entry saying who measured them. A
larger antenna on the same chip is another module. `form` tells an antenna on the board:
`trace`, `ceramic` or `coil`. `external` is a connector beside it, with what chooses between
the two: a `resistor` to solder over or a `switch`, a device the program sets, and its `ref`.
The radio of the chip itself has its antenna in `mcu.antenna`. A Wi-Fi or Bluetooth block of
the variant `external_antenna` refuses a board whose radio has only the antenna on it, and an
antenna not in the data is an unknown of the kit.

`quality` judges the design from 0 to 10. It is not a measurement: an RSSI holds for one place and one time, and a
device a metre from its access point does not care. A kit shows it when a radio is asked for and does not rank by it;
the model weighs it against the task. The marks between those below are free.

| `quality` | the design |
|---|---|
| 0 | no antenna: a connector with nothing on it, or nothing at all |
| 2 | a known fault of the design, as a chip antenna next to the crystal |
| 4 | a ceramic chip on a small board |
| 5 | a trace on a small board, or a ceramic chip with free space around it |
| 7 | the PCB antenna of a module, as an ESP-WROOM-32, out over the edge of the board |
| 8 | an external antenna on a connector |
| 10 | an external antenna of high gain, or on a cable out of the case |
A family writes what its members share, and each entry of `variants` patches the
rest. `variant_by` says what sets the variant and how a program can know it.

## Libraries

A device says what the chip can do, a library says what it does with that chip. The record
lies in `catalog/libraries/<ecosystem>/<owner>/<name>/library.json`, a chip does not list its
libraries, and a board names a library by that path: `esp-idf/jef-sure/pn5180`.

```json
{
    "kind": "library", "ecosystem": "esp-idf", "owner": "jef-sure", "name": "pn5180",
    "install": [{ "via": "registry" }, { "via": "git", "url": "https://github.com/jef-sure/esp32-component-pn5180.git", "ref": "v{version}" }],
    "transports": {
        "spi": { "init": { "call": "pn5180_spi_init", "args": ["{host}", "{sclk}", "{miso}", "{mosi}", "{hz}"], "returns": "bus" },
                 "shared": { "call": "pn5180_spi_attach", "args": ["{host}", "{hz}"], "returns": "bus" } }
    },
    "chips": {
        "pn5180": {
            "header": "pn5180.h", "on": ["spi"],
            "init": [{ "call": "pn5180_init", "args": ["{bus}", "{cs}", "{busy}", "{rst}"], "returns": "nfc", "ok": { "not": "NULL" } }],
            "setup": [{ "call": "pn5180_14443_init", "args": ["{nfc}"], "returns": "protocol", "for": "iso14443a" }],
            "standards": ["iso14443a", "iso15693"], "modes": ["reader"],
            "supports": { "mifare_classic": ["uid", "blocks_write", "ndef_read"] },
            "limits": { "iso14443a_cards_per_scan": 14 }
        }
    },
    "versions": {
        "0.0.2": { "platforms": { "esp_idf": ">=5.3.0" }, "requires": { "esp-idf/jef-sure/dgx": "^0.10.2" } },
        "0.0.1": { "platforms": { "esp_idf": ">=5.3.0" }, "requires": { "esp-idf/jef-sure/dgx": "^0.10.1" } }
    },
    "history": [
        { "before": "0.9.3", "chips": { "st77916": null } },
        { "before": "0.9.0", "chips": { "st7789": { "init": [{ "call": "dgx_st7789_init", "args": ["{bus}", "{rst}", "{depth}", "{color}"] }] } } },
        { "before": "0.5.0", "chips": { "jd9165": null } }
    ]
}
```

`chips` holds each supported chip apart: its header, its buses (`on`), Kconfig symbols
(`select`), the start (`init`), the first settings in order (`setup`), the calls of its
parameters (`controls`) and what it can do (`standards`, `modes`, `supports`, `limits`).
`{name}` in `args` is a value the caller gives, the rest goes into the call as it stands. A
step is a `call`, a `control` applied or a `line` set: a step `"line": "backlight"` says the
driver does not light it by itself. `transports` says how the library sets a bus up: `init`
creates it, `shared` joins one set up before.

An operation not listed in `supports` is one the library does not do:
`"mifare_classic": ["uid", "ndef_read"]` says it reads NDEF from such a card and does not write
it. A program that needs it says so in `needs`, and the rule `library_does_what_is_needed`
refuses a board whose library does not do it:

```json
"nfc": { "chip": "pn5180", "library": "esp-idf/jef-sure/pn5180", "needs": { "mifare_classic": ["ndef_write"] } }
```

`license` is the license of the version described, as an SPDX expression where it has one, and
a step of `history` says when it was another. For the `esp-idf` ecosystem
`tools/sync_versions.py` fills it from the registry, which writes `Custom` for a text of its own.

`ecosystem` says where a library is published: its registry and its name depend on that. What
its code is built against is in `platforms` of each version: `{ "esp_idf": ">=5.2.0" }`. These
are different things: a library of the Arduino registry may build with both `arduino-esp32` and
`esp-idf`, and then it has two keys. Both fields are open: a new ecosystem is a new directory in
`catalog/libraries/` and the schema stays as it is. `targets` lists the chips when a library
limits them; no list only says it declared none.

`install` lists the ways to get a library, from the one to prefer: `registry` (of its ecosystem),
`git` (`url`, `path` inside the repository and `ref`: a tag with `{version}` or a branch), `archive`
(`url`) and `platform` (it comes with the platform). The manifest of the component takes the
first way. A version that not all ways have names its own in `via`: that marks a version found
only in the tags of git.

A step with `call` must say how to tell it worked: `ok` follows the conventions of the library
itself. `{ "not": "NULL" }` for a pointer, `{ "equals": "ESP_OK" }` for ESP-IDF,
`{ "equals": "ESP_CODEC_DEV_OK" }` for the codec, `"none"` for a call with no result.

`versions` holds each version apart: `platforms`, `targets` and the other libraries it needs
(`requires`). For the `esp-idf` ecosystem `tools/sync_versions.py` fills it from the registry.

A record describes one version, named in `described`, and all it says is true of that one.
`history` says how the older ones differed: the fields of a step (`chips`, `transports`,
`interfaces`, `groups`, `values`) are Merge Patches for every version before `before`, and `null`
removes. All that changed goes there: chips, buses, abilities and the arguments of calls. When a
new version gains something, it is added to `chips`, `described` changes and
`history` gets a step without it. A device that stays on an older version names it in
`library_version`, the rules check `library` and `needs` against that version, and a refusal names
it: `esp-idf/jef-sure/pn5180 0.6.0 does not do ndef_write of mifare_classic`. A version newer than
`described` is refused: the catalog knows nothing about it. `tools/sync_versions.py` says when the
registry has a version newer than the one described.

`adapter` says how this component takes the library: the version its code is written against,
the symbol of the manifest rule, the components of the build and the files of
`adapters/<owner>__<name>/`: what the glue includes (`headers`), what a program includes
(`public`) and what is compiled by which symbol (`sources`). A record with no `adapter` only
describes: a chip with such a library stays data and the component does not start it, like the
PN532 of the terminal.

What a library requires is a field of the library, so DGX-LVGL has no chips and has versions.

### Audits

`catalog/libraries/` holds all that is known of libraries. `libraries.json` is the leading list, `chip_libraries.json` an
index into it, and each folder `<ecosystem>/<owner>/<name>/` a record and, when the library was read, `audit.json`.

An audit is about a library and not about a chip: a library can do an algorithm and drive nothing. `catalog/rubrics/<name>/rubric.json`
says what is asked: `sections` of items, `severity`, and `chips` when it is for chips. An item keeps its name, and one added
later has `since`. An entry of `audits` is one commit read against one version of a rubric: `commit`, `version` and `tag`
as far as they exist, `rubric`, `rubric_version`, `date`, `by`, `items` and `defects`. `blind` says the copy was read with the
names of its owners removed. `over` says the entry carries an older one: only what the changes touched was read again. A place is `file:line` at that commit. In a defect `judged` is the reason of a second reader, `read_as` what
the first said when they differ, `measured` where it was tried beyond reading. A newer version adds an entry and leaves the old ones.

The solver reads the last entry of each library. A library fits by its statuses, `yes` or `partly`, for the platform, the bus,
a second reader on it and the kind of card. Among those that fit: fewer `high`, then fewer `medium`, each counted with
all the library requires, then more of `frames`, `waiting` and `code_health` at `yes`, a `partly` as half, then the name. A
required library nobody read is an unknown. More readings find more defects, so only readings of one kind compare: one
blind reading of each library, against one version of a rubric. An entry of `checked` at level `hardware` that covers
`transports.spi` names the buses tried: the solver wires the chip on those first and says so of any other. Stars and downloads play no part. A kit shows the order
without counts; the line of the order holds its basis, which the page shows on hover: for each library the version
read, the defects counted with what it requires, the points of `frames`, `waiting` and `code_health`, the date and
the file of the audit. What was found goes to the model through the tool `library_audits` of `boards_mcp.py`.

## Firmware

Firmware inside a device changes what it can do too, so the file of a device has a `firmware`
block:

```json
"firmware": {
    "read": "command", "scheme": "hex", "described": "3.A",
    "history": [{ "before": "3.A", "controls": { "lpcd_reference": null } }]
}
```

`kept` says where it lives (`none`: the host writes it at every start), `set` who puts it there,
`read` how a program learns the version. A version number stays as the maker writes it, and
`scheme` says how it compares: with `hex` its parts are hexadecimal, so `3.A` is newer than `3.9`.
A pre-release is older than its release, `1.2.0~3` is newer than `1.2.0`, and `1.0` equals
`1.0.0`. `described` and `history` work as in a library: the file
describes one version and the steps patch `config`, `controls` and `provides` for the older ones.
A device names its own in `firmware_version`; that layer goes after the family variant and before
the board. What firmware a library takes is in `firmware` of the chip in its record.

## Connectors and images

```json
"connectors": { "P3": { "type": "HC 1.25 mm, 4 pins", "pins": [21, 22, 35, "GND"],
                        "at": { "image": "front", "x": 0.82, "y": 0.1 } } },
"images": { "front": { "file": "front.webp", "source": "own", "shows": "front", "up": { "x": 0, "y": -1 } } }
```

In a connector a number is a GPIO, a string a supply or a signal with no GPIO; a
string that is the `name` of a step of `power` is that line.
A connector repeats pins devices own, so it is not an owner of them.

A connector whose contacts a standard fixes names its entry in `of`, and then needs no
`type`:

```json
"J1": { "of": "stemma_qt", "pins": ["GND", "3V3", 8, 9] }
```

`catalog/connectors/<type>/connector.json` holds `pitch_mm`, `volts` and `pins`, what
each contact carries from contact 1, and the board gives as many contacts. `images` may
stand in any file of the catalog, the file beside the JSON; `source` is required,
and a vendor's photos are not copied. `at` places a mark in shares of the picture,
and `up` shows where the top of the screen points.

## Supply and levels

A module says what it takes and what it puts on its lines. A board or a project says where it takes
that from.

```json
"power": [{"name": "VCC", "source": "connector", "volts": [4.5, 5.5], "feeds": ["lcd"]}],
"devices": {"lcd": {"chip": "hd44780", "logic": "VCC"}}
```

| field | on | what |
|---|---|---|
| `volts` | a step of `power` | what a step with `source: connector` takes, one voltage or a range |
| `logic` | a device | the step a high level on its lines reaches: where its pull-ups go, or what its outputs drive |
| `supply` | a module in `modules` | the line of the board each such step takes from, as `"supply": {"VCC": "5V"}` |
| `gpio.high_mv_max` | a chip in `catalog/mcu/` | the most a pin takes as a high level, from the datasheet |

`logic` is `none` for a device that puts nothing on the lines of the chip, as a display with no line
back. A level above `high_mv_max` does not refuse a kit: the solver asks for a level shifter. A device with
no `logic`, or a chip with no `high_mv_max`, is an unknown of the kit.

`provides.emac` of a chip is the MAC alone. `ethernet` is a port: the device with the PHY provides
it, as a radio provides `wifi`.

A role in `catalog/roles.json` can have variants, and a chip says its own in `provides`, as `{"display": {"variant": "tft"}}`.
A part that does not say stays a candidate, and the kit counts that as an unknown. A variant with a `way` needs no part: the kit
gives it its `lines`, and those in `shared` are one line for all the blocks of that variant. `adc` is how many of the lines, the
first of the list, take pins of `gpio.adc1`. A variant with `needs.provides`, as a gamepad by Bluetooth, asks the board for it.
`bluetooth_classic` of a chip comes from `SOC_BT_CLASSIC_SUPPORTED` of ESP-IDF; every chip with `bluetooth` has BLE.

## Addons

`catalog/addons/<name>/addon.json` is a part that stands in the way of something and takes no pins. `stands` says what it
stands on: `lines`, `power` or `port`.

On lines, `channels` says how many lines one of them takes, and `both_ways` that a line works in both directions, as I2C needs.
A kit adds one by itself where a level needs it: a device or a way names `high_min_mv`, the lowest high level it reads, and
a chip drives 3.3 V. A chip whose `high_seen_mv`, the lowest high that drove it on hardware with its trial in `checked`, is
3.3 V or less gets a note instead (the judgement `level_seen_on_hardware`): the WS2812B takes 3.5 V by its datasheet, and
the 3.3 V of an ESP32 drove the 360 of Anton's garland.

On a port, `needs` names what a board must provide, and `gives` what the board then has: `provides`, and the `plug`, `mv` and
`ma` it hands over. A step of `power` names the `plug` it takes, so a PoE splitter comes with the plug of the board. A board
whose plug is not in the data stays an unknown of the kit.

## Platforms

`catalog/platforms/<name>/platform.json` says what a program is built on. `ecosystem` is the registry its libraries are
published in, `registry` its address, `project` what a project of it consists of, and `writes_projects` whether the page
writes one. Each of `versions` has its `targets`, `preview` for those it takes as a preview, and `on` for what it is built on.

A chip says the same from its side in `platforms` of `mcu.json`: `since`, `preview` and `revisions`, which `tools/make_mcu.py`
reads from COMPATIBILITY.md. `platforms` of a version of a library uses the same names. The choice in the top row of the page
limits the boards by their chip and the libraries by these names.

## Ways of wiring

A device with no bus lists its `ways`: the lines of each, the LEDC channels it takes and what it gives,
the fewest lines first.

```json
"ways": [
    {"lines": ["a"], "ledc": 1, "gives": {"swing_v": 3.3}, "do": "one leg to its GPIO, the other to ground"},
    {"lines": ["a", "b"], "ledc": 2, "gives": {"swing_v": 6.6}, "do": "the legs to two GPIOs in antiphase"}
]
```

So each piezo disc takes one pin and one channel, or two of each when a question asks for more swing.
The solver takes the first way that gives what is asked and counts its channels, with those the outputs of the page
take, against `frequency_sources.ledc.outputs` of the chip (the judgement `ledc_channels`).

## Chains

Chips that go in a chain on the same lines, the output of one into the input of the next, say so in `chain` of
their entry: `per`, the outputs of one chip by its datasheet, and `unit`, the outputs of one unit of `config.count`
where that unit is not the chip. A MAX7219 drives 64 LEDs, and its driver counts digits of 8; a WS2812B is one LED;
a 74HC595 has 8 outputs.

```json
"chain": {"per": 64, "unit": 8}
```

A product of such chips gives `config.count` × `unit` outputs: the four MAX7219 of `max7219_4in1` with
`config.count` 32 give 256. A block of LEDs or of shift registers asks how many outputs it drives
(`chain_outputs`; `"any_variant": false` of its `limit` keeps a block of any variant from asking it, as a display of
any kind), and the solver puts as many products in one chain as that takes; a project says it with
`count` of the module, on the wires of one:

```json
"modules": { "face": { "module": "max7219_4in1", "count": 2, "on": { "spi.spi2": { "cs": 15 } } } }
```

`count` above 1 is refused for a module none of whose parts chains. The driver of the whole chain takes `count` ×
`config.count`, worked out, not stored. The price and the list of goods count each product. A way that names its
chip in `part`, as the 74HC595 of LEDs on shift registers or the WS2812B of addressable LEDs, gives the number of
chips in the kit, and the project holds them as that chip with its `count`, so the price and the goods count them. A chain has no length
limit of its own: what limits it is the time an update takes along the whole of it. The bits of an update and the
speed of the bus join the data when a question asks how often the outputs change.

A chain of several products is `chain` of the use instead of `module`: the products and their counts in order from
the board. The wiring of the use is that of the first, and each next takes its input from the output of the one
before; the products chain one chip. A chain of one product keeps `module` and `count`.

```json
"modules": { "garland": { "chain": [{ "module": "ws2812b_strip_5m_60" }, { "module": "ws2812b_strip_1m_60" }], "pins": { "data": 14 } } }
```

A block says what the person already has with `part`: a name of a module, or for a chain a list of products and
their counts in order, `[{"part": "ws2812b_strip_5m_60", "count": 1}, {"part": "ws2812b_strip_1m_60"}]`. The kit
takes the list, and what the outputs asked take more of the first product. With nothing named, the solver makes the
chain of the products of the catalog that chain the same chip. Each joint of two products is one more to solder and
weighs as many outputs to spare as the block says in `joint_outputs`, by default as many as the shortest product has;
the chain is that of the least joints times the weight and outputs over those asked. With strips of 5 m and 1 m at 60
a metre, 360 WS2812B are a strip of 5 m and one of 1 m, 240 one strip of 5 m, cut, and 61 two strips of 1 m, or one
of 5 m when a joint weighs more than 180.

## Frequency sources

`frequency_sources` of a chip in `catalog/mcu/` lists where it gets a frequency, in the order to try
them. Each has `kind`, which picks the formula of the solver, `timers` (how many frequencies at once),
`outputs` (how many pins), `pairs` (two pins in antiphase) and `can`, what can be changed while it runs:
`frequency`, `duty`, `phase`, `fade`, `pause`, `dead_time`, `sync`, `carrier`, `loop`, `start_stop`,
`divider`. A crystal of a board is a device that provides `clock` with `freq_mhz`.

`tools/make_mcu.py` writes them for every chip from ESP-IDF, not by hand: the counts of timers and channels from
`soc_caps.h` and the low-level headers of LEDC, MCPWM and RMT, the clocks each can count from `clk_tree_defs.h`, the
dividers and the ranges from the low-level headers and the drivers, the crystal from the Kconfig of the chip. The
oscillators RC_FAST and RC_SLOW are left out of the clocks: they are not precise. MCPWM counts the clock its driver
takes by default divided by the prescale of a timer. The group has a prescale of its own, shared by its three timers:
the driver leaves it at 1 while the prescale of each timer fits and raises it for a slower timer, which the model does
not count, so a timer goes down to about 9.5 Hz here. The carrier of RMT counts the clock of the group. The ESP32 and
the S2 have no divider there; the other chips have one, shared by all channels and chosen by the driver from the
resolution of the first channel, and the model does not count on it: `prescale_max` is 1. The C5 finds its crystal at
boot, 40 or 48 MHz, so its XTAL is a fact of the module, not of the chip, and is not among its clocks.
What was tried on a board, as two LEDC pins in antiphase, is in `checked` of the chip at the level `hardware`.

## Mechanics

`mechanics` on a board or a module holds what a case needs: `outline_mm` and `holes` with `x_mm`, `y_mm`
and `d_mm` from the centre, y up. `do` beside it lists what a person does to fit the part, beyond the
wires, and the page shows it in a kit.
`window_mm` of a panel is the opening that shows it, for a panel whose area of pixels is not measured;
`mm_w` and `mm_h` are that area.

## Price

`price` lies on a board, a module or a device. It holds named offers, so a layer can add
one, as a project adds what it really paid.

```json
"price": {
    "amazon": {"shop": "amazon_de", "currency": "EUR", "range": [6, 6], "date": "2026-10-31", "source": "from memory"},
    "aliexpress": {"shop": "aliexpress", "currency": "EUR", "range": [0, 3], "date": "2026-10-31", "source": "from memory"}
}
```

| field | what |
|---|---|
| `shop` | where it is sold: a shop of `catalog/shops.json`. Absent when the source names no shop |
| `seller` | who sold it on a marketplace or classifieds, as written, when it is known |
| `currency` | the code, as `EUR` |
| `range` | lowest and highest price of one unit, never one number. "Less than 3" is `[0, 3]`, and a kit counts it as 3 |
| `qty` | the least quantity this price holds for, 1 when absent. Several offers of one shop give its prices by batch |
| `date`, `source` | when the price was seen and who says so: a price gets old |
| `notes` | anything else |

A price may be in any currency. The page shows them, and takes a budget, in the currency chosen, by `catalog/rates.json`, the reference
rates of the European Central Bank for one day, written by `tools/update_rates.py`. A currency with no
rate there counts as no price.

Delivery and duty are not here: they depend on the whole order, not on one board. See
[board_bom.py](tools.md#board_bompy).

`catalog/shops.json` names each shop once: its title, the domains it sells on and other names people write.

```json
"aliexpress": {"title": "AliExpress", "domains": ["aliexpress.com", "aliexpress.ru", "aliexpress.us"], "names": ["ali", "али"]},
"amazon_de": {"title": "Amazon.de", "domains": ["amazon.de"], "names": ["amazon"]}
```

A shop is one checkout. The stores of Amazon in two countries are two shops, while AliExpress and eBay are one shop on
all their domains. A name of two shops, as `amazon`, finds neither, so a report has to say which. `kind` says what
stands behind the checkout: `store` (when absent) sells its own stock; `marketplace` (AliExpress, Amazon, eBay) has
many sellers, and an offer there may name its `seller`; `classifieds` (Kleinanzeigen, Quoka) is a person selling one
thing, the price by agreement.

The offers of one shop at one quantity are kept all, each report its own: they are prices of different sellers, and
a seller is rarely remembered. The page and `board_bom.py` count a price the same way. What is sold by the pack is
bought by the pack, so the pieces bought are at least the smallest `qty` of the offers. Each shop gives its offers of
the largest `qty` the pieces bought reach, a named seller only by its newest report, and the median of their lows and
of their highs is the price of one piece there. The cheapest shop then gives the low of the item, the dearest its
high.

`tariff` is the customs tariff code of the goods, HS or CN, digits only. Duties on small
parcels are counted by it. `count` on a device says how many of it one product takes, for
what has no wiring of its own: screws, cables.

## Where the facts come from

`origin` says where an imported file came from. `checked` says what its facts
stand on. These are two questions.

```json
"origin": { "from": "rzeldent/platformio-espressif32-sunton", "ref": "a96fa42", "license": "GPL-3.0", "date": "2026-10-30" },
"checked": {
    "pins": { "level": "schematic", "source": "JC1060P470C_I_W_Y-V1.0.pdf", "date": "2026-10-28" },
    "touch": { "level": "hardware", "covers": ["devices.touch"], "by": "Anton", "date": "2026-10-30" },
    "sound": { "level": "schematic", "covers": ["devices.sound"], "result": "pending" }
}
```

The levels, most trusted first: `hardware`, `schematic`, `datasheet`,
`vendor-docs`, `vendor-code`, `community`, `extracted`, `unchecked`. `covers`
names what an entry is about, the whole file without it. `result` is `confirmed`
when absent, `pending` for what is still to be tried, `refuted` for a source that
disagrees. `unit` says which piece of the board was tried. A variant inherits the entries of its base marked `on_board`, because
they were earned on another board.

## Judgements of the solver

`catalog/judgements.json` holds how the solver chooses where the data leaves a choice open. A judgement has an `id`, a
`kind` and the fields of its kind, `says` (the line of a kit, `{0}` what it is about) and `why`. A kind is one function
of `editor/solver.js`, and the schema lists the kinds there are: a new judgement of a known kind is a record, a new kind
is code. A line of a kit that a judgement made carries its `id`: the page shows it on hover, the model gets it with the
kit, `selection.json` keeps it, and a case of `test/solver/` checks the `id`, not the text.

| kind | fields | what it does |
|---|---|---|
| `prefer_pins` | `bus`, `pins` (a field of the chip) | a new host of `bus` takes the pins the chip names for it when all are free; those pins go last for anything else |
| `keep_out` | `what` (`strapping`), `harm`, `unless`, `says_unless` | a strapping pin whose harm is listed, or which has no `boot`, is given to nothing; the others are given with a line. `unless` `{"logic": "none"}`: the lines of a way of a part that holds nothing on them take such a pin all the same, with the line `says_unless`; last, since a free pin asks nothing of reset and such a pin is often one of JTAG, a cost |
| `note_cost` | `note` | a pin with that note of the docs is given, with a line of what it costs; any other note keeps a pin out |
| `unnamed_variant` | | a part of the board of no named variant answers nothing for a variant asked when a module of the catalog names it, and stays a line |
| `resource_limit` | `resource` (`ledc`) | a kit that asks more of the resource than the chip has is refused |

The strapping pins of a chip are copied from its datasheet, not judged: `gpio.boot_modes` holds the rows of its table
of boot modes (the level of each pin, or `any`, for `spi_boot` and for each download mode), and each strapping pin has
`boot` in `gpio.pins`: `selects` (boot mode, flash voltage, rom messages, sdio timing, jtag source), `pull` at reset, the
`footnote` of the table and `decides: false` where that footnote says its level decides no mode. The harm is the
solver's to read: `run` where the row `spi_boot` names a level or the pin selects the voltage of the flash (the program
does not start), `download` where only another row names one, none otherwise.

`host_on_its_iomux` is the first: an SPI host on the pins of its IO MUX (`iomux` of `mcu.json`, from `spi_pins.h` of
ESP-IDF), as a wired board takes them.

## What is refused

Beyond the schema, by `catalog/rules.json`: a bus the board does not have; a bus
kind a device requires; a line through a device that cannot give it; a touch over
what is not a display; two touches over one display; two primary displays; two
owners of a GPIO, an expander bit or an I2C address; windows of a ladder that
overlap; one host named both `spi` and `qspi`; a calibration for another range or display size; a value outside what a
parameter takes; a GPIO the chip has not; an output on an input-only GPIO; a name
in `shared_pins`, `power`, `start` or `checked` that does not exist; two steps of
`power` with one name; a step that takes from no step before it; a connector whose
contacts do not match its entry.

`tools/boards_gen.py` also refuses what it cannot make glue for. The format can
describe more than the generator sets up yet, and the error names the device and what
it lacks: `chip_try`, `config.timing`, a `clock` of `bclk`, an I2S format other than
`std`, `sio`, a button on a ladder, a touch whose chip does not say its `fingers`, a
step of `power` with a `line`. Only displays, touch panels, sound and buttons are
started; any other device is kept as data.
