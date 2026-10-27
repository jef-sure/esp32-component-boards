#!/usr/bin/env python3
"""Generate everything the data of the boards decides.

Usage: boards_gen.py [--data DIR] [--out DIR] (BOARD | --all)

For one board, reads boards-data/BOARD/board.json and writes into boards/BOARD/:
  - BOARD.c               the glue the component compiles when the board is chosen: every
                          function of boards.h, those for the parts the board has set up by
                          the data, those for the parts it has not answering false
  - board.cmake           what the glue needs at link, derived from what the board has

With --all, every board and module, and beside them what names them all:
  - boards/boards.cmake   the lists CMakeLists.txt compiles by
  - Kconfig               the choice of the board, the options of the modules, the hidden
                          symbols the rules of idf_component.yml look at
  - idf_component.yml     its dependencies between the markers "# boards: dependencies
                          generated" and "# boards: end of generated"
  - README.md, README.ru.md
                          the table of the boards between "<!-- boards:table -->" and
                          "<!-- boards:end -->"

The board's sdkconfig.defaults is not generated: it is boards-data/BOARD/sdkconfig.defaults
already, written by hand with its reasons (tools/check_boards.py checks that it chooses the
board and the chip: CONFIG_BOARD_SELECT_<BOARD>=y, CONFIG_IDF_TARGET).

board.json is the only source of truth: the editor edits it, this generates everything else,
tools/check_boards.py checks the generated is what the data says.

The shape of the data:

  buses      the board's buses, a name each, its pins and speed its own: two devices on one
             bus (two PN532, two cs) share the bus's pins; the name is the claim of the
             host: "spi.spi2" is the chip's SPI2. A kind the component sets not up itself
             is kept as data for the program (board_bus_get)
  display    the pixel panel (a driver of DGX) or the character LCD (hd44780), its bus a
             name from buses, its cs/dc/rst/backlight its own lines (a device's, not the bus's)
  touch      on a bus of the board, with the calibration measured on it (measured: false
             marks a placeholder)
  sound      a codec on a bus (es8311) or the chip's own DAC on a pin (dac)
  button     its pin, active_low
  sd         the slot, a device on a bus of the board, its cs its own
  module     true: not a board but a device any board's bus can carry (the 2004 backpack);
             no mcu, no buses, no button of its own

Run from the repository root:

    python3 tools/boards_gen.py --all
    python3 tools/boards_gen.py jc1060p470
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# what a display bus of a kind is in C: the header of dgx that makes it
BUS_HEADERS = {
    "dsi": "bus/dgx_dsi_esp32.h",
    "qspi": "bus/dgx_qspi_esp32.h",
    "spi": "bus/dgx_spi_esp32.h",
    "p8": "bus/dgx_p8_esp32.h",
}

# the SPI buses a chip has: the name of the data ("spi2", "spi3") is the claim of
# the host, and a chip that has fewer refuses more names (a C-series joins here
# when a board with one arrives)
SPI_BUSES = {
    "esp32": ("spi2", "spi3"),
    "esp32s3": ("spi2", "spi3"),
    "esp32p4": ("spi2", "spi3"),
}

# the GPIOs a chip has, and the ones that are input only (an output on them is an
# error of the data, not of the board)
GPIOS = {
    "esp32": (range(0, 40), (34, 35, 36, 37, 38, 39)),
    "esp32s3": (range(0, 49), ()),
    "esp32p4": (range(0, 55), ()),
}

# a panel driver: the header of dgx that inits it, the pixel depths it takes (as its
# header says: 16 RGB565 everywhere, 24 on the DSI panels), and the symbols of dgx's
# Kconfig the choice of a board with it selects
PANEL_HEADERS = {
    "jd9165": "drivers/jd9165.h",
    "jd9365": "drivers/jd9365.h",
    "nv3041a": "drivers/nv3041a.h",
    "ili9341": "drivers/ili9341.h",
}
PANEL_DEPTHS = {
    "jd9165": (16, 24),
    "jd9365": (16, 24),
    "nv3041a": (16,),
    "ili9341": (16,),
}
PANEL_SELECTS = {
    "jd9165": ("DGX_ENABLE_DSI", "DGX_ENABLE_JD9165"),
    "jd9365": ("DGX_ENABLE_DSI", "DGX_ENABLE_JD9365"),
    "nv3041a": ("DGX_ENABLE_SPI", "DGX_ENABLE_NV3041A"),
    "ili9341": ("DGX_ENABLE_SPI", "DGX_ENABLE_SPI_ILI_9341"),
}

# the character family: a driver of jef-sure/hd44780, on a board's I2C bus or GPIOs; the
# geometries it takes, as its header names them (an HD44780_GEOMETRY_*)
CHARACTER_DRIVERS = {
    "hd44780": ("8x2", "16x2", "16x4", "20x2", "20x4", "40x2"),
}

ORIENT_X = {"left-right": "DgxScreenLeftRight", "right-left": "DgxScreenRightLeft"}
ORIENT_Y = {"top-bottom": "DgxScreenTopBottom", "bottom-top": "DgxScreenBottomTop"}

# the touch of a kind: the header of its device in DGX-DI, the vendor's beside it
TOUCH_KINDS = {
    "gt911": ("dgx_di_esp_lcd_touch.h", "esp_lcd_touch_gt911.h"),
    "gsl3680": ("dgx_di_gsl3680.h", None),
    # any other driver of ESP-IDF's esp_lcd_touch interface on SPI (an XPT2046 resistive
    # panel): the data names the component and its header, the glue calls the interface
    "esp_lcd_touch": ("dgx_di_esp_lcd_touch.h", None),
}

# what the rules of idf_component.yml bring, by the hidden symbol a board or a module
# raises: the component and the version the glue is written against. A touch of the
# esp_lcd_touch kind raises BOARD_TOUCH_<DRIVER> for the component its data names; its
# version is in COMPONENT_VERSIONS.
FEATURE_DEPS = [
    ("BOARD_DISPLAY_FRAMEBUFFER", "jef-sure/dgx", "^0.8.2"),
    ("BOARD_TOUCH", "jef-sure/dgx-di", "^0.1.2"),
    ("BOARD_TOUCH_GT911", "espressif/esp_lcd_touch_gt911", "^1"),
    ("BOARD_SOUND_ES8311", "espressif/esp_codec_dev", "~1.5"),
    ("BOARD_DISPLAY_HD44780", "jef-sure/hd44780", "^0.1.2"),
]
COMPONENT_VERSIONS = {
    "atanisoft/esp_lcd_touch_xpt2046": "^1.0.6",
}

I2C_HZ_DEFAULT = 400000
TOUCH_SPI_HZ_DEFAULT = 1000000  # what the XPT2046 driver recommends for its reads

MANIFEST_BEGIN = "  # boards: dependencies generated"
MANIFEST_END = "  # boards: end of generated"
TABLE_BEGIN = "<!-- boards:table -->"
TABLE_END = "<!-- boards:end -->"


def bus_parts(bus_name):
    """spi.spi2 -> ("spi", "spi2"); i2c.i2c0 -> ("i2c", "i2c0")."""
    kind, _, own = str(bus_name).partition(".")
    return kind, own or None


def bus_of(board, bus_name):
    """The board's bus by its name: {"hz": ..., "mosi": ..., ...}."""
    kind, own = bus_parts(bus_name)
    return (board.get("buses", {}).get(kind, {}) or {}).get(own) if own else None


def port_of(own, prefix):
    """i2c0 -> 0, i2s1 -> 1: the number of the chip's port a bus name claims."""
    digits = own[len(prefix):] if own and own.startswith(prefix) else ""
    return int(digits) if digits.isdigit() else 0


def touch_driver(touch):
    """esp_lcd_touch_xpt2046.h -> xpt2046: the driver of a touch of the esp_lcd_touch kind."""
    return touch["header"].replace("esp_lcd_touch_", "").replace(".h", "").replace(".", "_")


def is_character(display):
    return bool(display) and display.get("driver") in CHARACTER_DRIVERS


def is_pixel(display):
    return bool(display) and display.get("driver") in PANEL_HEADERS


def lying(display):
    """The display as it lies: (width, height, mm_w, mm_h) after the swap of its orientation."""
    panel = display["panel"]
    if display["original_orientation"].get("swap", False):
        return panel["height"], panel["width"], panel["mm_h"], panel["mm_w"]
    return panel["width"], panel["height"], panel["mm_w"], panel["mm_h"]


def read_board(path):
    """The data of a board, checked: what the generator needs is there and of a kind it knows."""
    data = json.loads(path.read_text())
    if data.get("format") != "jef-sure/boards":
        raise ValueError(f'not of the format jef-sure/boards: "{data.get("format")}"')
    if data.get("format_version") != 1:
        raise ValueError(f'format_version {data.get("format_version")} is not 1')
    name = data.get("name")
    if not name or not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("the name is lowercase letters, digits and _ only")
    if not data.get("title"):
        raise ValueError("no title")
    is_module = bool(data.get("module"))
    if is_module and data.get("mcu"):
        raise ValueError("a module rides a board's buses: no mcu of its own")
    if is_module and data.get("buses"):
        raise ValueError("a module rides the carrier board's buses: no buses of its own to wire")
    if is_module and data.get("button"):
        raise ValueError("a module has no button of its own")
    if is_module and (data.get("touch") or data.get("sound") or data.get("sd")):
        raise ValueError("a module is a display for now: no touch, sound or sd of its own")
    target = data.get("mcu", {}).get("target")
    if not is_module and target not in SPI_BUSES:
        raise ValueError(f'the target is one of {", ".join(SPI_BUSES)}, not "{target}"')

    # the buses: a name a bus, its pins its own; an spi name is the claim of the host
    buses = data.get("buses") or {}
    if not isinstance(buses, dict):
        raise ValueError("buses is not a dictionary")
    for kind, named in buses.items():
        for own, bus in (named or {}).items():
            if kind in ("spi", "qspi"):
                if own not in SPI_BUSES[target]:
                    raise ValueError(f'the chip {target} has no "{own}" to wire: {", ".join(SPI_BUSES[target])}')
                signals = ("mosi", "miso", "sclk") if kind == "spi" else ("d0", "d1", "d2", "d3", "sclk")
                for signal in signals:
                    if not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus {kind}.{own} lacks its "{signal}" pin')
            elif kind == "i2c":
                if not (own.startswith("i2c") and own[3:].isdigit()):
                    raise ValueError(f'the name of an i2c bus is its port: "i2c.i2c0", not "{own}"')
                for signal in ("sda", "scl"):
                    if not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus i2c.{own} lacks its "{signal}" pin')
            elif kind == "i2s":
                if not (own.startswith("i2s") and own[3:].isdigit()):
                    raise ValueError(f'the name of an i2s bus is its port: "i2s.i2s0", not "{own}"')
                for signal in ("mclk", "bclk", "ws", "dout"):
                    if not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus i2s.{own} lacks its "{signal}" pin')
                if bus.get("din") is not None and not isinstance(bus.get("din"), int):
                    raise ValueError(f'the bus i2s.{own} has a din that is not a pin')
            elif kind == "dsi":
                for key in ("lanes", "lane_mbps", "phy_ldo_chan", "phy_ldo_mv"):
                    if not isinstance(bus.get(key), int):
                        raise ValueError(f'the bus dsi.{own} lacks its "{key}"')
            elif kind == "p8":
                for signal in ("d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "wr", "dc", "hz"):
                    if not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus p8.{own} lacks its "{signal}"')
                if bus.get("rd") is not None and not isinstance(bus.get("rd"), int):
                    raise ValueError(f'the bus p8.{own} has an rd that is not a pin')
            else:
                # a kind the component knows not how to set up: still the board's data, kept
                # for the program (an sdio of a radio, the SD pins no host is left for)
                if not bus or not isinstance(bus, dict):
                    raise ValueError(f"the bus {kind}.{own} is nothing")
                for key, value in bus.items():
                    if value is not None and not isinstance(value, (int, str)):
                        raise ValueError(f'the bus {kind}.{own} has a "{key}" that is neither a pin nor a parameter')

    # the display: a pixel panel of dgx or a character LCD of hd44780
    display = data.get("display")
    if is_module and not is_character(display):
        raise ValueError("a module is a character display (hd44780) for now")
    if display is not None:
        driver = display.get("driver")
        if driver in CHARACTER_DRIVERS:
            geometry = display.get("geometry")
            if geometry not in CHARACTER_DRIVERS[driver]:
                raise ValueError(f'the geometry {geometry} is not one the driver {driver} takes ({", ".join(CHARACTER_DRIVERS[driver])})')
            transport = display.get("bus", {})
            bus_name = transport.get("bus", "") if isinstance(transport, dict) else transport
            kind = bus_parts(bus_name)[0] if isinstance(bus_name, str) else None
            if kind == "i2c":
                if "address" not in transport:
                    raise ValueError("a character LCD on I2C names the backpack's address beside the bus")
                if not is_module and bus_of(data, bus_name) is None:
                    raise ValueError(f'the character LCD rides the board\'s bus "{bus_name}", which the board does not wire')
            elif kind == "gpio":
                width = bus_parts(bus_name)[1]
                pins = transport.get("pins", {})
                need = ("rs", "en", "d4", "d5", "d6", "d7") if width == "4bit" else ("rs", "en", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7") if width == "8bit" else ()
                if not need:
                    raise ValueError('a character LCD on GPIOs is "gpio.4bit" or "gpio.8bit"')
                for signal in need:
                    if not isinstance(pins.get(signal), int):
                        raise ValueError(f'the character LCD on gpio.{width} lacks its "{signal}" pin')
            else:
                raise ValueError('a character LCD rides one of three transports: "i2c.<own>" (a PCF8574 backpack), "gpio.4bit", "gpio.8bit"')
        elif driver in PANEL_HEADERS:
            bus_name = display.get("bus", {}).get("bus")
            if not bus_name or bus_parts(bus_name)[0] not in ("spi", "qspi", "dsi", "p8"):
                raise ValueError('the display\'s bus is a name from buses: "spi.spi2", "qspi.spi2", "dsi.dsi0", "p8.i80"')
            if bus_of(data, bus_name) is None:
                raise ValueError(f'the display\'s bus "{bus_name}" is not among the board\'s buses')
            panel = display.get("panel")
            if not panel or not all(isinstance(panel.get(k), int) for k in ("width", "height", "mm_w", "mm_h")):
                raise ValueError("the panel of the display lacks its size, in pixels or millimetres")
            depth = display.get("depth_bits", 16)
            if depth not in PANEL_DEPTHS[driver]:
                raise ValueError(f'depth_bits {depth} is not one the driver {driver} takes ({", ".join(str(d) for d in PANEL_DEPTHS[driver])})')
            if panel["width"] > panel["height"] and panel["mm_w"] < panel["mm_h"] or \
               panel["width"] < panel["height"] and panel["mm_w"] > panel["mm_h"]:
                raise ValueError("the panel's pixels and its millimetres lie different ways: both are the glass as the controller scans it")
            ratio_px = panel["width"] / panel["height"]
            ratio_mm = panel["mm_w"] / panel["mm_h"]
            if abs(ratio_px - ratio_mm) / max(ratio_px, ratio_mm) > 0.2:
                raise ValueError(f"the panel's pixels ({panel['width']}x{panel['height']}) and its millimetres ({panel['mm_w']}x{panel['mm_h']}) are not near one proportion")
            orientation = display.get("original_orientation")
            if not orientation or orientation.get("x") not in ORIENT_X or orientation.get("y") not in ORIENT_Y:
                raise ValueError("the original_orientation of the display is not left-right/right-left x top-bottom/bottom-top")
            kind = bus_parts(bus_name)[0]
            for line in {"spi": ("cs", "dc"), "qspi": ("cs",), "p8": ("cs",), "dsi": ()}[kind]:
                if not isinstance(display["bus"].get(line), int):
                    raise ValueError(f'the display lacks its "{line}" line')
        else:
            raise ValueError(f'panel driver not known: "{driver}"')

    # the touch, the sound, the button, the sd slot
    touch = data.get("touch")
    if touch is not None:
        if touch.get("kind") not in TOUCH_KINDS:
            raise ValueError(f'touch of a kind not known: "{touch.get("kind")}"')
        if not is_pixel(display):
            raise ValueError("a touch panel lies on a frame buffer display: the board has none")
        calibration = touch.get("calibration")
        if not calibration:
            raise ValueError("the touch has no calibration: measure the board (dgx_di_calibrate_measure) and put it in the data; measured: false marks a placeholder")
        for key in ("x_min", "x_max", "y_min", "y_max", "width", "height", "flags", "knots_x", "knots_y", "rounds", "affine", "x", "y",
                    "down_ms", "up_ms", "blink_ms", "gap_ms", "off_tenths", "worst_tenths", "left_tenths", "left_worst_tenths"):
            if key not in calibration:
                raise ValueError(f'the calibration lacks its "{key}"')
        if "measured" in calibration and not isinstance(calibration["measured"], bool):
            raise ValueError("calibration.measured is true or false")
        if not isinstance(touch.get("x_max"), int) or not isinstance(touch.get("y_max"), int):
            raise ValueError("the touch lacks its x_max and y_max, the range of its coordinates")
        if not touch.get("bus") or bus_of(data, touch["bus"]) is None:
            raise ValueError(f'the touch\'s bus "{touch.get("bus")}" is not among the board\'s buses')
        if touch["kind"] in ("gt911", "gsl3680") and bus_parts(touch["bus"])[0] != "i2c":
            raise ValueError(f'a {touch["kind"]} rides a board\'s I2C bus: bus is its name, "i2c.i2c0"')
        if touch["kind"] == "esp_lcd_touch":
            component = touch.get("component")
            if not component or not touch.get("header"):
                raise ValueError('a touch of the esp_lcd_touch kind names its component and its header (atanisoft/esp_lcd_touch_xpt2046, esp_lcd_touch_xpt2046.h)')
            if component.count("/") != 1:
                raise ValueError(f'the component is named with its namespace, "atanisoft/esp_lcd_touch_xpt2046", not "{component}"')
            if component not in COMPONENT_VERSIONS:
                raise ValueError(f"the component {component} has no version in COMPONENT_VERSIONS of the generator: add the one the glue is written against")
            if bus_parts(touch["bus"])[0] != "spi":
                raise ValueError('a touch of the esp_lcd_touch kind rides a board\'s SPI bus: bus is its name, "spi.spi3"')
            for line in ("cs", "irq"):
                if not isinstance(touch.get(line), int):
                    raise ValueError(f'the touch lacks its "{line}" pin')
    sound = data.get("sound")
    if sound is not None:
        if sound.get("kind") not in ("es8311", "dac"):
            raise ValueError(f'sound of a kind not known: "{sound.get("kind")}"')
        if not isinstance(sound.get("sample_rate"), int):
            raise ValueError("the sound lacks its sample_rate")
        if sound["kind"] == "dac":
            if target != "esp32":
                raise ValueError("the DAC kind of sound is the ESP32's own: no other chip here has one")
            if sound.get("out") not in (25, 26):
                raise ValueError(f'the DAC of an ESP32 is on GPIO 25 or 26, not {sound.get("out")}')
            if sound.get("pa") is not None and not isinstance(sound.get("pa"), int):
                raise ValueError("the pa of the sound is a pin or null")
        else:
            if bus_of(data, sound.get("bus", "")) is None or bus_parts(sound.get("bus", ""))[0] != "i2c":
                raise ValueError('the codec comes on a board\'s I2C bus: bus is its name, "i2c.<own>"')
            if bus_of(data, sound.get("i2s_bus", "")) is None or bus_parts(sound.get("i2s_bus", ""))[0] != "i2s":
                raise ValueError('the codec streams over a board\'s I2S bus: i2s_bus is its name, "i2s.i2s0"')
            if not sound.get("address"):
                raise ValueError("the codec needs its address on the I2C bus")
            if not isinstance(sound.get("volume"), int):
                raise ValueError("the codec needs its volume, 0..100")
    button = data.get("button")
    if button is not None and not isinstance(button.get("pin"), int):
        raise ValueError("the button lacks its pin")
    sd = data.get("sd")
    if sd is not None:
        if bus_parts(sd.get("bus", ""))[0] != "spi" or bus_of(data, sd.get("bus", "")) is None:
            raise ValueError('the sd slot is a device on a board\'s SPI bus: bus is its name, "spi.spi2"')
        if not isinstance(sd.get("cs"), int):
            raise ValueError("the sd slot lacks its cs pin")
    return data


# ---------------------------------------------------------------------------------------------
# the pins of a board, each with its owner: for the map of pins and the check of conflicts
# ---------------------------------------------------------------------------------------------

def pins_of(board):
    """Every pin the data names, as (pin, owner, direction): direction "out", "in" or "bus"."""
    pins = []
    buses = board.get("buses") or {}
    for kind, named in buses.items():
        for own, bus in (named or {}).items():
            for key, value in sorted((bus or {}).items()):
                if key in ("hz", "lanes", "lane_mbps", "phy_ldo_chan", "phy_ldo_mv") or not isinstance(value, int):
                    continue
                direction = "in" if key in ("miso", "din", "rd", "d1") and kind in ("spi", "i2s", "p8") else "bus"
                pins.append((value, f"{kind}.{own}.{key}", direction))
    display = board.get("display")
    if is_pixel(display):
        for line in ("cs", "dc"):
            if isinstance(display["bus"].get(line), int):
                pins.append((display["bus"][line], f"display.{line}", "out"))
        for line in ("rst", "backlight"):
            if isinstance(display.get(line), int):
                pins.append((display[line], f"display.{line}", "out"))
    elif is_character(display):
        transport = display.get("bus", {})
        for key, value in sorted((transport.get("pins") or {}).items()):
            if isinstance(value, int):
                pins.append((value, f"display.{key}", "out"))
    touch = board.get("touch")
    if touch:
        for line, direction in (("cs", "out"), ("irq", "in"), ("rst", "out"), ("int", "in")):
            if isinstance(touch.get(line), int):
                pins.append((touch[line], f"touch.{line}", direction))
    sound = board.get("sound")
    if sound:
        for line in ("out", "pa"):
            if isinstance(sound.get(line), int):
                pins.append((sound[line], f"sound.{line}", "out"))
    if board.get("button"):
        pins.append((board["button"]["pin"], "button", "in"))
    if board.get("sd") and isinstance(board["sd"].get("cs"), int):
        pins.append((board["sd"]["cs"], "sd.cs", "out"))
    return pins


def pin_problems(board):
    """What the map of pins says is wrong: two owners of one pin, an output on an input-only GPIO, a GPIO the chip has not."""
    problems = []
    target = board.get("mcu", {}).get("target")
    if target not in GPIOS:
        return problems
    valid, input_only = GPIOS[target]
    owners = {}
    for pin, owner, direction in pins_of(board):
        if pin not in valid:
            problems.append(f"GPIO {pin} ({owner}) is no GPIO of an {target}")
        if direction != "in" and pin in input_only:
            problems.append(f"GPIO {pin} ({owner}) is input only on an {target}, and {owner} drives it")
        owners.setdefault(pin, []).append(owner)
    for pin, names in sorted(owners.items()):
        if len(names) > 1:
            problems.append(f"GPIO {pin} has two owners: {', '.join(names)}")
    return problems


# ---------------------------------------------------------------------------------------------
# what a board raises: the hidden symbols of the Kconfig the rules of the manifest look at
# ---------------------------------------------------------------------------------------------

def features_of(board):
    """The hidden symbols a board or a module raises when chosen."""
    features = set()
    display = board.get("display")
    if is_pixel(display):
        features.add("BOARD_DISPLAY_FRAMEBUFFER")
    if is_character(display):
        features.add("BOARD_DISPLAY_HD44780")
        if board.get("module"):
            features.add("BOARD_MODULE_CHARACTER_DISPLAY")
    touch = board.get("touch")
    if touch:
        features.add("BOARD_TOUCH")
        if touch["kind"] == "gt911":
            features.add("BOARD_TOUCH_GT911")
        elif touch["kind"] == "esp_lcd_touch":
            features.add(f"BOARD_TOUCH_{touch_driver(touch).upper()}")
    sound = board.get("sound")
    if sound and sound["kind"] == "es8311":
        features.add("BOARD_SOUND_ES8311")
    return features


def feature_deps(boards):
    """The dependencies the rules bring, (symbol, component, version), those of the known features and of the touch components the data names."""
    deps = list(FEATURE_DEPS)
    for board in boards:
        touch = board.get("touch")
        if touch and touch["kind"] == "esp_lcd_touch":
            entry = (f"BOARD_TOUCH_{touch_driver(touch).upper()}", touch["component"], COMPONENT_VERSIONS[touch["component"]])
            if entry not in deps:
                deps.append(entry)
    return deps


def choice_symbol(board):
    return f"BOARD_SELECT_{board['name'].upper()}"


def module_symbol(board):
    return f"BOARD_MODULE_{board['name'].upper()}"


def derive_requires(board):
    """What the glue needs at link, derived from what the board has."""
    requires = set()
    display = board.get("display")
    touch = board.get("touch")
    sound = board.get("sound")
    for kind in (board.get("buses") or {}):
        requires.add({"i2c": "esp_driver_i2c", "i2s": "esp_driver_i2s", "spi": "esp_driver_spi", "qspi": "esp_driver_spi"}.get(kind, "esp_driver_gpio"))
    if is_character(display):
        requires.update(("esp_driver_gpio", "jef-sure__hd44780"))
        if bus_parts(display.get("bus", {}).get("bus", ""))[0] == "i2c":
            requires.add("esp_driver_i2c")
    elif is_pixel(display):
        requires.update(("esp_driver_gpio", "jef-sure__dgx"))
    if touch:
        requires.add("jef-sure__dgx-di")
        if touch["kind"] == "gt911":
            requires.update(("esp_lcd", "espressif__esp_lcd_touch_gt911"))
        elif touch["kind"] == "esp_lcd_touch":
            requires.update(("esp_lcd", "esp_driver_spi", touch["component"].replace("/", "__")))
    if sound:
        if sound["kind"] == "dac":
            requires.update(("esp_driver_dac", "esp_driver_gpio"))
        else:
            requires.update(("esp_driver_i2s", "espressif__esp_codec_dev"))
    if board.get("button"):
        requires.add("esp_driver_gpio")
    requires.update(board.get("extra_requires", []))
    return sorted(requires)


# ---------------------------------------------------------------------------------------------
# the C glue
# ---------------------------------------------------------------------------------------------

def c_calibration(cal):
    """The calibration as a C initializer, the fields of dgx_di_calibration_t in order."""
    def knot(points, count):
        return ", ".join("{%d, %d}" % (p[0], p[1]) for p in points[:count])
    return (
        f".version = 1, .size = sizeof(dgx_di_calibration_t), "
        f".x_min = {cal['x_min']}, .x_max = {cal['x_max']}, .y_min = {cal['y_min']}, .y_max = {cal['y_max']}, "
        f".width = {cal['width']}, .height = {cal['height']}, .flags = {cal['flags']}, "
        f".knots_x = {cal['knots_x']}, .knots_y = {cal['knots_y']}, .rounds = {cal['rounds']}, "
        f".affine = {{{', '.join(str(v) for v in cal['affine'])}}}, "
        f".x = {{{knot(cal['x'], cal['knots_x'])}}}, .y = {{{knot(cal['y'], cal['knots_y'])}}}, "
        f".down_ms = {cal['down_ms']}, .up_ms = {cal['up_ms']}, .blink_ms = {cal['blink_ms']}, .gap_ms = {cal['gap_ms']}, "
        f".off_tenths = {cal['off_tenths']}, .worst_tenths = {cal['worst_tenths']}, "
        f".left_tenths = {cal['left_tenths']}, .left_worst_tenths = {cal['left_worst_tenths']}"
    )


def c_gpio(num):
    return "GPIO_NUM_NC" if num is None else f"GPIO_NUM_{num}"


def gen_c(board):
    """The C glue of the board: every function of boards.h, by the data or answering false."""
    name = board["name"]
    buses = board.get("buses") or {}
    display = board.get("display")
    touch = board.get("touch")
    sound = board.get("sound")
    button = board.get("button")
    sd = board.get("sd")
    is_module = bool(board.get("module"))
    pixel = is_pixel(display)
    character = is_character(display)
    i2c_buses = sorted((buses.get("i2c") or {}).items())
    i2c_port = port_of(i2c_buses[0][0], "i2c") if i2c_buses else 0
    touch_own_spi = bool(touch) and touch["kind"] == "esp_lcd_touch" and (not pixel or touch["bus"] != display["bus"]["bus"])
    L = []
    out = L.append
    out("/*")
    out(f" * The glue of {name}, made by tools/boards_gen.py from boards-data/{name}/board.json: do not")
    out(" * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).")
    if is_module:
        out(" * A module: not a board but a device the chosen board's bus carries; it gives the function of")
        out(" * its kind, and the board's glue leaves that one out (CONFIG_BOARD_MODULE_CHARACTER_DISPLAY).")
    else:
        out(" * Every function of boards.h is here: by the data for the parts the board has, answering")
        out(" * false for the parts it has not, so the contract of boards.h holds at link.")
    out(" */")
    out("#include \"boards.h\"")
    out("#include \"board_glue.h\"")
    out("")
    out("#include \"sdkconfig.h\"")
    out("")
    headers = ["stdlib.h", "string.h", "esp_log.h"]
    if character:
        headers.append("hd44780.h")
        if bus_parts(display["bus"]["bus"])[0] == "gpio":
            headers.append("driver/gpio.h")
    elif pixel:
        kind = bus_parts(display["bus"]["bus"])[0]
        headers.append(BUS_HEADERS[kind])
        headers.append(PANEL_HEADERS[display["driver"]])
        if kind == "dsi" and display.get("backlight") is not None:
            headers.append("driver/gpio.h")
    if touch:
        t = TOUCH_KINDS[touch["kind"]]
        headers.append(t[0])
        if t[1]:
            headers.append(t[1])
        if touch["kind"] == "esp_lcd_touch":
            headers.append(touch["header"])
            headers.append("esp_lcd_panel_io.h")
            if touch_own_spi:
                headers.append("driver/spi_common.h")
        if touch["kind"] == "gt911":
            headers.append("esp_lcd_panel_io.h")
        headers.append("dgx_di.h")
    if sound:
        headers.append("freertos/FreeRTOS.h")
        headers.append("freertos/task.h")
        if sound["kind"] == "dac":
            headers.append("driver/dac_continuous.h")
            if sound.get("pa") is not None:
                headers.append("driver/gpio.h")
        else:
            headers.append("driver/i2s_std.h")
            headers.append("esp_codec_dev.h")          # the device: open, write, volume
            headers.append("esp_codec_dev_defaults.h") # the interfaces and the ES8311's own
    if button:
        headers.append("driver/gpio.h")
    for header in sorted(set(headers)):
        out(f"#include <{header}>" if header in ("stdlib.h", "string.h") else f"#include \"{header}\"")
    out("")
    out(f"/* {board['title']}: {board['description']}. */")
    out("")

    # ---- the pins of the board, each named by the part it serves ----
    if not is_module:
        out("/* The pins of the board, each named by the part it serves: a bus's own, a device's")
        out(" * strobes (cs, dc, rst, backlight, an amplifier's pa). */")
        for own, bus in sorted((buses.get("spi") or {}).items()):
            hz = f", .hz = {bus['hz']}" if bus.get("hz") is not None else ""
            out(f"static const struct board_spi_bus board_spi_{own} = {{.host = {own.upper()}_HOST, .mosi = {c_gpio(bus['mosi'])}, .miso = {c_gpio(bus['miso'])}, .sclk = {c_gpio(bus['sclk'])}{hz}}};")
        for own, bus in i2c_buses[:1]:
            out(f"static const struct board_i2c_pins board_i2c_pins_of = {{.port = I2C_NUM_{port_of(own, 'i2c')}, .sda = {c_gpio(bus['sda'])}, .scl = {c_gpio(bus['scl'])}}}; /* i2c.{own} */")
        for own, bus in sorted((buses.get("i2s") or {}).items()):
            out(f"static const struct board_i2s_bus board_i2s_{own} = {{.port = I2S_NUM_{port_of(own, 'i2s')}, .mclk = {c_gpio(bus['mclk'])}, .bclk = {c_gpio(bus['bclk'])}, .ws = {c_gpio(bus['ws'])}, .dout = {c_gpio(bus['dout'])}, .din = {c_gpio(bus.get('din'))}}};")
        # the strobes as macros of gpio_num_t constants: the exact type the drivers take (an enum
        # of the glue's own would convert, with a warning ESP-IDF makes an error)
        if pixel:
            db = display["bus"]
            for line, pin in (("CS", db.get("cs")), ("DC", db.get("dc"))):
                if pin is not None:
                    out(f"#define PIN_{line} {c_gpio(pin)}")
            if display.get("rst") is not None:
                out(f"#define PIN_LCD_RST {c_gpio(display['rst'])}")
            if display.get("backlight") is not None:
                out(f"#define PIN_LCD_BACKLIGHT {c_gpio(display['backlight'])}")
        if touch:
            out(f"#define PIN_TOUCH_RST {c_gpio(touch.get('rst'))}")
            out(f"#define PIN_TOUCH_INT {c_gpio(touch.get('int') if touch['kind'] != 'esp_lcd_touch' else touch.get('irq'))}")
            if touch["kind"] == "esp_lcd_touch":
                out(f"#define PIN_TOUCH_CS {c_gpio(touch['cs'])}")
        if sound and sound["kind"] == "dac":
            out(f"#define PIN_SOUND_OUT {c_gpio(sound.get('out'))}")
        if sound and sound.get("pa") is not None:
            out(f"#define PIN_SOUND_PA {c_gpio(sound.get('pa'))}")
        if button:
            out(f"#define PIN_BUTTON {c_gpio(button['pin'])}")
        if sd:
            out(f"#define PIN_SD_CS {c_gpio(sd.get('cs'))}")
        out("")

        # ---- every bus of the board, its numbers by name: the universal table ----
        rows = []
        for kind, named in buses.items():
            for own, bus in named.items():
                for key, value in sorted((bus or {}).items()):
                    if isinstance(value, int):
                        rows.append((f"{kind}.{own}", key, value))
        out("/* Every bus of the board, its numbers by name: the kinds the component sets up and the")
        out(" * kinds it only keeps for the program, for a program that sets its own hardware up on the")
        out(" * board's wiring instead of copying pins. */")
        if rows:
            entries = ", ".join(f'{{"{bus}", "{key}", {value}}}' for bus, key, value in rows)
            out(f"static const struct board_bus_field board_bus_table[] = {{{entries}}};")
        else:
            out("static const struct board_bus_field board_bus_table[] = {{0, 0, 0}}; /* the board wires no bus of numbers */")
        out("")
        out("bool board_bus_get(const char *bus, const char *field, long *out)")
        out("{")
        out("    for (size_t i = 0; i < sizeof(board_bus_table) / sizeof(board_bus_table[0]); ++i) {")
        out("        if (board_bus_table[i].bus && strcmp(board_bus_table[i].bus, bus) == 0 && strcmp(board_bus_table[i].field, field) == 0) {")
        out("            if (out) *out = board_bus_table[i].value;")
        out("            return true;")
        out("        }")
        out("    }")
        out("    return false;")
        out("}")
        out("")

        # ---- the shared buses as the program sees them ----
        spi_hosts = sorted(set(list(buses.get("spi") or {}) + list(buses.get("qspi") or {})))
        if buses.get("spi"):
            entries = ", ".join(f"&board_spi_{own}" for own in sorted(buses["spi"]))
            out("/* The board's SPI buses by host: a device the program adds takes one of them or a free host. */")
            out(f"static const struct board_spi_bus *const board_spi_buses[] = {{{entries}}};")
            out("")
            out("const struct board_spi_bus *board_spi_bus(int host)")
            out("{")
            out("    for (size_t i = 0; i < sizeof(board_spi_buses) / sizeof(board_spi_buses[0]); ++i)")
            out("        if (board_spi_buses[i]->host == host) return board_spi_buses[i];")
            out("    return NULL;")
            out("}")
        else:
            out("/* The board wires no SPI bus of the plain kind: none to hand out. */")
            out("const struct board_spi_bus *board_spi_bus(int host)")
            out("{")
            out("    (void)host;")
            out("    return NULL;")
            out("}")
        out("")
        if spi_hosts:
            taken = ", ".join(f"{own.upper()}_HOST" for own in spi_hosts)
            out(f"/* The hosts the board's buses claim, SPI and QSPI alike: {', '.join(spi_hosts)}. */")
            out("bool board_spi_taken(int host)")
            out("{")
            out(f"    static const int taken[] = {{{taken}}};")
            out("    for (size_t i = 0; i < sizeof(taken) / sizeof(taken[0]); ++i)")
            out("        if (taken[i] == host) return true;")
            out("    return false;")
            out("}")
        else:
            out("bool board_spi_taken(int host)")
            out("{")
            out("    (void)host;")
            out("    return false;")
            out("}")
        out("")
        if i2c_buses:
            out("/* The board's I2C: one master, made by whoever asks first (board_glue_i2c). */")
            out("const struct board_i2c_pins *board_i2c_pins(void)")
            out("{")
            out("    return &board_i2c_pins_of;")
            out("}")
        else:
            out("/* The board wires no I2C bus: nothing for board_glue_i2c to make. */")
            out("const struct board_i2c_pins *board_i2c_pins(void)")
            out("{")
            out("    return NULL;")
            out("}")
        out("")

    # ---- the display ----
    if character:
        transport = display["bus"]
        bus_name = transport["bus"]
        kind, width = bus_parts(bus_name)
        address = transport.get("address")
        gpins = transport.get("pins", {})
        cols, rows = display["geometry"].split("x")
        where = "the board's I2C bus" if kind == "i2c" else f"GPIOs ({width})"
        out(f"/* The character display: a {display['geometry']} {display['driver']} on {where} (jef-sure/hd44780). */")
        out("static hd44780_t *character_lcd;")
        out("")
        out("bool board_character_display_init(struct board_character_display *out)")
        out("{")
        out("    if (!out) return false;")
        out("    if (!character_lcd) {")
        if kind == "i2c":
            out("        i2c_master_bus_handle_t bus = board_glue_i2c();")
            out("        if (!bus) return false;")
            out(f"        lcd_bus_hd44780_t *backpack = lcd_bus_pcf8574_i2c_create_on_bus(bus, {address or '0x27'}, 0);")
            out("        if (!backpack) {")
            out('            ESP_LOGE("board", "no PCF8574 backpack at the address of the data");')
            out("            return false;")
            out("        }")
        elif width == "4bit":
            out(f"        lcd_bus_hd44780_t *backpack = lcd_bus_gpio4_create({c_gpio(gpins.get('rs'))}, {c_gpio(gpins.get('en'))}, {c_gpio(gpins.get('d4'))}, {c_gpio(gpins.get('d5'))}, {c_gpio(gpins.get('d6'))}, {c_gpio(gpins.get('d7'))});")
            out("        if (!backpack) {")
            out('            ESP_LOGE("board", "no GPIOs of the character LCD");')
            out("            return false;")
            out("        }")
        else:
            out(f"        lcd_bus_hd44780_t *backpack = lcd_bus_gpio8_create({c_gpio(gpins.get('rs'))}, {c_gpio(gpins.get('en'))}, {', '.join(c_gpio(gpins.get('d%d' % i)) for i in range(8))});")
            out("        if (!backpack) {")
            out('            ESP_LOGE("board", "no GPIOs of the character LCD");')
            out("            return false;")
            out("        }")
        out(f"        character_lcd = lcd_init(backpack, HD44780_GEOMETRY_{cols}X{rows}, true); /* the controller owns the backpack: gone with a failed init */")
        out("        if (!character_lcd) {")
        out('            ESP_LOGE("board", "the character LCD did not take its init sequence");')
        out("            return false;")
        out("        }")
        out("        lcd_clear_screen(character_lcd);")
        out("        lcd_backlight_on(character_lcd);")
        out("    }")
        out("    out->lcd = character_lcd;")
        out(f"    out->cols = {cols}, out->rows = {rows};")
        out("    return true;")
        out("}")
        out("")
    elif pixel:
        db = display["bus"]
        bus_name = db["bus"]
        kind, own = bus_parts(bus_name)
        bus = bus_of(board, bus_name)
        panel = display["panel"]
        orientation = display["original_orientation"]
        swap = "true" if orientation.get("swap", False) else "false"
        w, h, mm_w, mm_h = lying(display)
        out(f"/* The display: a {panel['width']}x{panel['height']} {display['driver']} on {bus_name}, the glass {panel['mm_w']}x{panel['mm_h']} mm as the controller")
        out(f" * scans it; lying as the board shows it, {w}x{h}, {mm_w}x{mm_h} mm. */")
        if kind == "dsi":
            out(f"enum {{ DSI_LANES = {bus.get('lanes', 2)}, DSI_LANE_MBPS = {bus.get('lane_mbps', 750)}, DSI_PHY_LDO_CHAN = {bus.get('phy_ldo_chan', 3)}, DSI_PHY_LDO_MV = {bus.get('phy_ldo_mv', 2500)} }};")
        out(f"enum {{ GLASS_W = {panel['width']}, GLASS_H = {panel['height']}, GLASS_MM_W = {panel['mm_w']}, GLASS_MM_H = {panel['mm_h']} }};")
        out("")
        out("/* How the display lies after an orientation call: its size follows the swap of its axes. */")
        out("static void display_lies(struct board_display *d, int dir_x, int dir_y, bool swap_xy)")
        out("{")
        out("    d->dir_x = dir_x, d->dir_y = dir_y, d->swap_xy = swap_xy;")
        out("    d->width = swap_xy ? GLASS_H : GLASS_W, d->height = swap_xy ? GLASS_W : GLASS_H;")
        out("    d->mm_w = swap_xy ? GLASS_MM_H : GLASS_MM_W, d->mm_h = swap_xy ? GLASS_MM_W : GLASS_MM_H;")
        out("}")
        out("")
        out("bool board_display_init(struct board_display *out)")
        out("{")
        out("    if (!out) return false;")
        if kind == "dsi":
            out("    dgx_bus_protocols_t *bus = dgx_dsi_init(0, DSI_LANES, DSI_LANE_MBPS, DSI_PHY_LDO_CHAN, DSI_PHY_LDO_MV);")
        elif kind == "p8":
            out(f"    dgx_bus_protocols_t *bus = dgx_p8_init({', '.join(c_gpio(bus['d%d' % i]) for i in range(8))}, {c_gpio(bus['wr'])}, {c_gpio(bus.get('rd'))}, PIN_CS, {c_gpio(bus['dc'])}, {bus['hz']}); /* {bus_name} */")
        elif kind == "qspi":
            out(f"    dgx_bus_protocols_t *bus = dgx_qspi_init({own.upper()}_HOST, SPI_DMA_CH_AUTO, {c_gpio(bus['d0'])}, {c_gpio(bus['d1'])}, {c_gpio(bus['d2'])}, {c_gpio(bus['d3'])}, {c_gpio(bus['sclk'])}, PIN_CS, {bus.get('hz', 40000000)}, 0); /* {bus_name} */")
        else:
            out(f"    dgx_bus_protocols_t *bus = dgx_spi_init({own.upper()}_HOST, SPI_DMA_CH_AUTO, {c_gpio(bus['mosi'])}, {c_gpio(bus['miso'])}, {c_gpio(bus['sclk'])}, PIN_CS, PIN_DC, {bus.get('hz', 40000000)}, 0); /* {bus_name} */")
        out("    if (!bus) return false;")
        init = f"dgx_{display['driver']}_init"
        depth = display.get("depth_bits", 16)
        rst = "PIN_LCD_RST" if display.get("rst") is not None else "GPIO_NUM_NC"
        if kind == "dsi":
            out(f"    dgx_screen_t *screen = {init}(bus, {rst}, {depth}, DgxScreenRGB, DgxDsiTwoFrames);")
        else:
            backlight = "PIN_LCD_BACKLIGHT" if display.get("backlight") is not None else "GPIO_NUM_NC"
            out(f"    dgx_screen_t *screen = {init}(bus, {rst}, {backlight}, {depth}, DgxScreenRGB);")
        out("    if (!screen) {")
        out("        bus->dispose(bus);")
        out("        return false;")
        out("    }")
        out(f"    dgx_{display['driver']}_orientation(screen, {ORIENT_X[orientation['x']]}, {ORIENT_Y[orientation['y']]}, {swap}); /* as the board shows it; a program turns it its own way after */")
        if kind == "dsi" and display.get("backlight") is not None:
            on = "1" if display.get("backlight_on_high", True) else "0"
            out("    /* the light goes on over a black frame buffer, not over what the panel had before */")
            out("    gpio_set_direction(PIN_LCD_BACKLIGHT, GPIO_MODE_OUTPUT);")
            out(f"    gpio_set_level(PIN_LCD_BACKLIGHT, {on});")
        out("    out->screen = screen;")
        out("    out->bus = bus;")
        out(f"    display_lies(out, {ORIENT_X[orientation['x']]}, {ORIENT_Y[orientation['y']]}, {swap});")
        out("    return true;")
        out("}")
        out("")
        out("bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)")
        out("{")
        out("    if (!display || !display->screen) return false;")
        out(f"    dgx_{display['driver']}_orientation((dgx_screen_t *)display->screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);")
        out("    display_lies(display, dir_x, dir_y, swap_xy);")
        out("    return true;")
        out("}")
        out("")

    # ---- the touch ----
    if touch:
        kind = touch["kind"]
        cal = touch["calibration"]
        measured = cal.get("measured", True)
        if kind == "esp_lcd_touch":
            fingers = touch.get("fingers", 1)
            out(f"/* The touch: a {touch_driver(touch).upper()} of {touch['component']} on {touch['bus']}, its own cs and irq,")
            out(f" * {'one finger of a resistive panel' if touch.get('resistive') else str(fingers) + ' fingers'}, the calibration of its measured board. */")
        else:
            out(f"/* The touch: a {kind.upper()} on the board's I2C bus, {touch['fingers']} fingers, the calibration of its measured board. */")
        if not measured:
            out("/* The calibration below is a placeholder, not measured on a board: the touch works, only not")
            out(" * straight; board_touch_start says so. Measure the board (dgx_di_calibrate_measure) and put the")
            out(" * numbers in the data. */")
        out(f"static const dgx_di_calibration_t touch_calibration = {{{c_calibration(cal)}}};")
        out(f"static {'dgx_di_gsl3680_t' if kind == 'gsl3680' else 'dgx_di_esp_lcd_touch_t'} touch_panel;")
        out("")
        out("bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)")
        out("{")
        out("    if (!display || !display->screen) return false;")
        if kind == "esp_lcd_touch":
            own = bus_parts(touch["bus"])[1]
            out(f"    const struct board_spi_bus *bus = board_spi_bus({own.upper()}_HOST);")
            out("    if (!bus) return false;")
            if touch_own_spi:
                out("    /* the host is the touch's own, no display on it: taken here, once */")
                out("    static bool host_up;")
                out("    if (!host_up) {")
                out("        const spi_bus_config_t host = {.mosi_io_num = bus->mosi, .miso_io_num = bus->miso, .sclk_io_num = bus->sclk, .quadwp_io_num = GPIO_NUM_NC, .quadhd_io_num = GPIO_NUM_NC, .max_transfer_sz = 0};")
                out("        if (spi_bus_initialize((spi_host_device_t)bus->host, &host, SPI_DMA_CH_AUTO) != ESP_OK) {")
                out('            ESP_LOGE("board", "the SPI host of the touch could not be taken");')
                out("            return false;")
                out("        }")
                out("        host_up = true;")
                out("    }")
            out("    const esp_lcd_panel_io_spi_config_t config = {")
            out(f"        .cs_gpio_num = PIN_TOUCH_CS, .dc_gpio_num = GPIO_NUM_NC, .spi_mode = 0, .pclk_hz = {touch.get('hz', TOUCH_SPI_HZ_DEFAULT)},")
            out("        .trans_queue_depth = 3, .lcd_cmd_bits = 8, .lcd_param_bits = 8,")
            out("    };")
            out("    esp_lcd_panel_io_handle_t io;")
            out("    if (esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)(intptr_t)bus->host, &config, &io) != ESP_OK) return false;")
            out(f"    const esp_lcd_touch_config_t tconfig = {{.x_max = {touch['x_max']}, .y_max = {touch['y_max']}, .rst_gpio_num = PIN_TOUCH_RST, .int_gpio_num = PIN_TOUCH_INT}};")
            out("    esp_lcd_touch_handle_t handle = NULL;")
            out(f"    if (esp_lcd_touch_new_spi_{touch_driver(touch)}(io, &tconfig, &handle) != ESP_OK || !handle) {{")
            out('        ESP_LOGE("board", "no touch panel answers on the board\'s SPI bus");')
            out("        esp_lcd_panel_io_del(io);")
            out("        return false;")
            out("    }")
            out(f"    dgx_di_esp_lcd_touch_init(&touch_panel, handle, {fingers}, {'false' if touch.get('resistive') else 'true'});")
        elif kind == "gt911":
            out("    i2c_master_bus_handle_t bus = board_glue_i2c();")
            out("    if (!bus) return false;")
            addresses = ", ".join(gt911_address_symbol(a) for a in (touch.get("address_try") or ["0x5d"]))
            out(f"    static const uint8_t address[] = {{{addresses}}};")
            out(f"    const esp_lcd_touch_config_t config = {{.x_max = {touch['x_max']}, .y_max = {touch['y_max']}, .rst_gpio_num = PIN_TOUCH_RST, .int_gpio_num = PIN_TOUCH_INT}};")
            out("    esp_lcd_touch_handle_t handle = NULL;")
            out("    for (int i = 0; i < (int)(sizeof(address) / sizeof(address[0])) && !handle; ++i) {")
            out("        esp_lcd_panel_io_handle_t io;")
            out("        esp_lcd_panel_io_i2c_config_t io_config = ESP_LCD_TOUCH_IO_I2C_GT911_CONFIG();")
            out(f"        io_config.dev_addr = address[i], io_config.scl_speed_hz = {I2C_HZ_DEFAULT};")
            out("        if (esp_lcd_new_panel_io_i2c(bus, &io_config, &io) != ESP_OK) continue;")
            out("        if (esp_lcd_touch_new_i2c_gt911(io, &config, &handle) != ESP_OK) esp_lcd_panel_io_del(io); /* off the bus: the next address */")
            out("    }")
            out("    if (!handle) {")
            out('        ESP_LOGE("board", "no touch panel answers on the board\'s I2C bus");')
            out("        return false;")
            out("    }")
            out(f"    dgx_di_esp_lcd_touch_init(&touch_panel, handle, {touch['fingers']}, true);")
        else:  # gsl3680
            out("    i2c_master_bus_handle_t bus = board_glue_i2c();")
            out("    if (!bus) return false;")
            out("    const uint8_t *fw_start;")
            out("    size_t         fw_size;")
            out("    if (!board_touch_firmware(&fw_start, &fw_size)) {")
            out('        ESP_LOGE("board", "no firmware embedded for the touch panel: the program defines board_touch_firmware, see the docs");')
            out("        return false;")
            out("    }")
            out("    if (!dgx_di_gsl3680_init(&touch_panel, bus, PIN_TOUCH_RST, PIN_TOUCH_INT, 0, fw_start, fw_size)) {")
            out('        ESP_LOGE("board", "no GSL3680 answers");')
            out("        return false;")
            out("    }")
        out("    dgx_di_pointer_t *pointer = board_glue_pointer(); /* the one pointer of the core */")
        out("    dgx_di_pointer_init(pointer, &touch_panel.device, 0, (const dgx_screen_t *)display->screen);")
        out("    if (!dgx_di_pointer_calibrate(pointer, &touch_calibration))")
        out('        ESP_LOGW("board", "the calibration is not this board\'s: the touch works, only not as straight");')
        if not measured:
            out('    ESP_LOGW("board", "the touch calibration of this board is a placeholder, not measured: measure the board and put the numbers in the data");')
        out("    if (device_out) *device_out = &touch_panel.device;")
        out("    if (pointer_out) *pointer_out = pointer;")
        out("    return true;")
        out("}")
        out("")

    # ---- the sound ----
    if sound:
        rate = sound["sample_rate"]
        out(f"enum {{ SOUND_FRAMES = 256 }}; /* samples a write: {256 * 1000 // rate} ms at {rate} */")
        out("")
        out("static board_sound_source_t sound_source;")
        out("")
        out("void board_sound_source(board_sound_source_t source)")
        out("{")
        out("    sound_source = source;")
        out("}")
        out("")
    if sound and sound["kind"] == "dac":
        mask = "DAC_CHANNEL_MASK_CH0" if sound["out"] == 25 else "DAC_CHANNEL_MASK_CH1"
        out("/* The sound: the chip's own DAC, 8 bits on a pin, fed by DMA (dac_continuous); the writes wait")
        out(" * for the DMA, which sets the pace. A task of its own takes the program's next samples and")
        out(f" * writes them{'; the amplifier is on PIN_SOUND_PA' if sound.get('pa') is not None else ''}. */")
        out("static dac_continuous_handle_t dac;")
        out("")
        out("static void sound_task(void *arg)")
        out("{")
        out("    (void)arg;")
        out("    static int16_t samples[SOUND_FRAMES];")
        out("    static uint8_t bytes[SOUND_FRAMES];")
        out("    bool           told = false;")
        out("    for (;;) {")
        out("        if (sound_source) sound_source(samples, SOUND_FRAMES);")
        out("        else memset(samples, 0, sizeof(samples));")
        out("        for (int i = 0; i < SOUND_FRAMES; ++i) bytes[i] = (uint8_t)((samples[i] >> 8) + 128);")
        out("        size_t loaded = 0;")
        out("        if (dac_continuous_write(dac, bytes, sizeof(bytes), &loaded, -1) == ESP_OK) continue;")
        out("        if (!told) {")
        out('            ESP_LOGE("board", "the DAC takes no samples");')
        out("            told = true;")
        out("        }")
        out(f"        vTaskDelay(pdMS_TO_TICKS(SOUND_FRAMES * 1000 / {rate}) + 1);")
        out("    }")
        out("}")
        out("")
        out("bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)")
        out("{")
        out("    if (!dac) {")
        out(f"        const dac_continuous_config_t config = {{.chan_mask = {mask}, .desc_num = 4, .buf_size = SOUND_FRAMES, .freq_hz = {rate}, .offset = 0, .clk_src = DAC_DIGI_CLK_SRC_DEFAULT, .chan_mode = DAC_CHANNEL_MODE_SIMUL}};")
        out("        if (dac_continuous_new_channels(&config, &dac) != ESP_OK || dac_continuous_enable(dac) != ESP_OK) {")
        out('            ESP_LOGE("board", "no DAC");')
        out("            dac = NULL;")
        out("            return false;")
        out("        }")
        if sound.get("pa") is not None:
            out("        gpio_set_direction(PIN_SOUND_PA, GPIO_MODE_OUTPUT);")
            out("        gpio_set_level(PIN_SOUND_PA, 1);")
        out("        sound_source = source;")
        out('        if (xTaskCreate(sound_task, "sound", 3072, NULL, 6, NULL) != pdPASS) {')
        out('            ESP_LOGE("board", "no task for the sound");')
        out("            return false;")
        out("        }")
        out(f'        ESP_LOGI("board", "the DAC at {rate} Hz");')
        out("    }")
        out(f"    if (rate_out) *rate_out = {rate};")
        out("    return true;")
        out("}")
        out("")
    elif sound:
        bus_name = sound.get("i2s_bus", "")
        iown = bus_parts(bus_name)[1] or "i2s0"
        i2s_port = port_of(iown, "i2s")
        out(f"/* The sound: an {sound['kind'].upper()} on {bus_name}, set up over the board's I2C bus{', its amplifier on PIN_SOUND_PA' if sound.get('pa') is not None else ''};")
        out(" * a task of its own takes the program's next samples and writes them; the writes wait for the I2S, which sets the pace. */")
        out(f"enum {{ SOUND_VOLUME = {sound['volume']} }}; /* of the codec, 0..100 */")
        out("")
        out("static esp_codec_dev_handle_t speaker;")
        out("")
        out("static void sound_task(void *arg)")
        out("{")
        out("    (void)arg;")
        out("    static int16_t samples[SOUND_FRAMES];")
        out("    bool           told = false;")
        out("    for (;;) {")
        out("        if (sound_source) sound_source(samples, SOUND_FRAMES);")
        out("        else memset(samples, 0, sizeof(samples));")
        out("        if (esp_codec_dev_write(speaker, samples, sizeof(samples)) == ESP_CODEC_DEV_OK) continue;")
        out("        if (!told) {")
        out('            ESP_LOGE("board", "the codec takes no samples");')
        out("            told = true;")
        out("        }")
        out(f"        vTaskDelay(pdMS_TO_TICKS(SOUND_FRAMES * 1000 / {rate}) + 1);")
        out("    }")
        out("}")
        out("")
        out("bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)")
        out("{")
        out("    if (!speaker) {")
        out("        i2c_master_bus_handle_t i2c = board_glue_i2c();")
        out("        if (!i2c) {")
        out('            ESP_LOGE("board", "no I2C bus for the codec");')
        out("            return false;")
        out("        }")
        out("        i2s_chan_handle_t tx;")
        out(f"        i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_{i2s_port}, I2S_ROLE_MASTER);")
        out("        chan.dma_frame_num = SOUND_FRAMES;")
        out("        const i2s_std_config_t std = {")
        out(f"            .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG({rate}),")
        out("            .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),")
        out(f"            .gpio_cfg = {{.mclk = board_i2s_{iown}.mclk, .bclk = board_i2s_{iown}.bclk, .ws = board_i2s_{iown}.ws, .dout = board_i2s_{iown}.dout, .din = board_i2s_{iown}.din}}, /* {bus_name} */")
        out("        };")
        out("        /* on from the start: esp_codec_dev turns it off to set the format, and off before ever on is an error in the log */")
        out("        if (i2s_new_channel(&chan, &tx, NULL) != ESP_OK || i2s_channel_init_std_mode(tx, &std) != ESP_OK || i2s_channel_enable(tx) != ESP_OK) {")
        out('            ESP_LOGE("board", "no I2S");')
        out("            return false;")
        out("        }")
        out(f"        const audio_codec_data_if_t *data = audio_codec_new_i2s_data(&(audio_codec_i2s_cfg_t){{.port = I2S_NUM_{i2s_port}, .tx_handle = tx}});")
        out(f"        const audio_codec_ctrl_if_t *ctrl = audio_codec_new_i2c_ctrl(&(audio_codec_i2c_cfg_t){{.port = I2C_NUM_{i2c_port}, .addr = {sound['address']}, .bus_handle = i2c}});")
        out("        const audio_codec_gpio_if_t *gpio = audio_codec_new_gpio();")
        pa_pin = "PIN_SOUND_PA" if sound.get("pa") is not None else "GPIO_NUM_NC"
        out(f"        es8311_codec_cfg_t           es   = {{.ctrl_if = ctrl, .gpio_if = gpio, .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC, .pa_pin = {pa_pin}, .use_mclk = true}};")
        out(f"        es.hw_gain.pa_voltage = {sound.get('pa_voltage', 5.0)}, es.hw_gain.codec_dac_voltage = {sound.get('codec_dac_voltage', 3.3)};")
        out("        const audio_codec_if_t *codec = data && ctrl && gpio ? es8311_codec_new(&es) : NULL;")
        out("        speaker = codec ? esp_codec_dev_new(&(esp_codec_dev_cfg_t){.dev_type = ESP_CODEC_DEV_TYPE_OUT, .codec_if = codec, .data_if = data}) : NULL;")
        out(f"        esp_codec_dev_sample_info_t format = {{.sample_rate = {rate}, .channel = 1, .bits_per_sample = 16}};")
        out("        if (!speaker || esp_codec_dev_open(speaker, &format) != ESP_CODEC_DEV_OK) {")
        out('            ESP_LOGE("board", "no ES8311");')
        out("            speaker = NULL;")
        out("            return false;")
        out("        }")
        out("        esp_codec_dev_set_out_vol(speaker, SOUND_VOLUME);")
        out("        sound_source = source;")
        out('        if (xTaskCreate(sound_task, "sound", 3072, NULL, 6, NULL) != pdPASS) {')
        out('            ESP_LOGE("board", "no task for the sound");')
        out("            return false;")
        out("        }")
        out(f'        ESP_LOGI("board", "ES8311 at {rate} Hz");')
        out("    }")
        out(f"    if (rate_out) *rate_out = {rate};")
        out("    return true;")
        out("}")
        out("")

    # ---- the button ----
    if button:
        active_low = button.get("active_low", True)
        out(f"/* The button of the board, {'low' if active_low else 'high'} when pressed. */")
        out("bool board_button(bool *pressed)")
        out("{")
        out("    if (!pressed) return false;")
        out("    static bool set_up;")
        out("    if (!set_up) {")
        pull = "GPIO_PULLUP_ENABLE" if active_low else "GPIO_PULLUP_DISABLE"
        pulldown = "GPIO_PULLDOWN_DISABLE" if active_low else "GPIO_PULLDOWN_ENABLE"
        out(f"        const gpio_config_t config = {{.pin_bit_mask = 1ULL << PIN_BUTTON, .mode = GPIO_MODE_INPUT, .pull_up_en = {pull}, .pull_down_en = {pulldown}}};")
        out("        gpio_config(&config);")
        out("        set_up = true;")
        out("    }")
        out(f"    *pressed = gpio_get_level((gpio_num_t)PIN_BUTTON) {'==' if active_low else '!='} 0;")
        out("    return true;")
        out("}")
        out("")

    # ---- what the board has not: the rest of boards.h, answering false ----
    if not is_module:
        out("/* What the board has not: the rest of boards.h, answering false, so that the same program")
        out(" * links and runs on every board. */")
        if not pixel:
            out("bool board_display_init(struct board_display *out)")
            out("{")
            out("    (void)out;")
            out("    return false;")
            out("}")
            out("")
            out("bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)")
            out("{")
            out("    (void)display, (void)dir_x, (void)dir_y, (void)swap_xy;")
            out("    return false;")
            out("}")
            out("")
        if not character:
            out("#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY /* a module on the board's bus gives this one instead */")
            out("bool board_character_display_init(struct board_character_display *out)")
            out("{")
            out("    (void)out;")
            out("    return false;")
            out("}")
            out("#endif")
            out("")
        if not touch:
            out("bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)")
            out("{")
            out("    (void)display, (void)device_out, (void)pointer_out;")
            out("    return false;")
            out("}")
            out("")
        if not sound:
            out("bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)")
            out("{")
            out("    (void)source, (void)rate_out;")
            out("    return false;")
            out("}")
            out("")
            out("void board_sound_source(board_sound_source_t source)")
            out("{")
            out("    (void)source;")
            out("}")
            out("")
        if not button:
            out("bool board_button(bool *pressed)")
            out("{")
            out("    (void)pressed;")
            out("    return false;")
            out("}")
            out("")
        target = board.get("mcu", {}).get("target", "any")
        out("/* What the board is, for board_info(). */")
        out(f"const struct board_data board_data = {{.name = \"{name}\", .title = \"{board['title']}\", .target = \"{target}\"}};")
    return "\n".join(L) + "\n"


def gt911_address_symbol(address):
    return "ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS_BACKUP" if str(address).lower() == "0x14" else "ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS"


def gen_cmake(board):
    """board.cmake: what the glue needs, derived from what the board has."""
    name = board["name"]
    requires = derive_requires(board)
    L = [f"# The glue of {name}, made by tools/boards_gen.py from its data: the components it needs,",
         f"# derived from what the board has (the components of ESP-IDF 5.3 and later; extra_requires",
         f"# in boards-data/{name}/board.json adds what the structure cannot say). Do not edit by hand.",
         "# Added after idf_component_register, when the configuration is known: a requirement that",
         "# depends on the board chosen cannot stand in REQUIRES. Optional: a component the rules of the",
         "# manifest did not bring is simply not there, and the glue that needs it is not compiled either.",
         "# PUBLIC: a program draws with DGX and reads DGX-DI through the headers this brings."]
    if requires:
        L.append(f"idf_component_optional_requires(PUBLIC {' '.join(requires)})")
    else:
        L.append("# nothing beside the component itself")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------
# what names them all: boards.cmake, Kconfig, the dependencies of the manifest, the table
# ---------------------------------------------------------------------------------------------

def gen_boards_cmake(boards, modules):
    L = ["# The boards and the modules the component has glue for, made by tools/boards_gen.py --all",
         "# from boards-data/: CMakeLists.txt compiles the chosen board's glue (CONFIG_BOARD_<BOARD>)",
         "# and every module turned on (CONFIG_BOARD_MODULE_<MODULE>). Do not edit by hand.",
         f"set(BOARDS_LIST {' '.join(b['name'] for b in boards)})",
         f"set(BOARDS_MODULES {' '.join(m['name'] for m in modules)})"]
    return "\n".join(L) + "\n"


def menu_text(board):
    """What the menu shows for a board: its title and what it has, in a line."""
    parts = []
    display = board.get("display")
    if is_pixel(display):
        w, h, _, _ = lying(display)
        parts.append(f"{w}x{h} {display['driver'].upper()}")
    elif is_character(display):
        parts.append(f"{display['geometry']} {display['driver'].upper()}")
    touch = board.get("touch")
    if touch:
        parts.append((touch_driver(touch) if touch["kind"] == "esp_lcd_touch" else touch["kind"]).upper() + " touch")
    sound = board.get("sound")
    if sound:
        parts.append("ES8311 sound" if sound["kind"] == "es8311" else "DAC sound")
    return f"{board['title']}: {', '.join(parts)}" if parts else board["title"]


def kconfig_help(text, indent="        "):
    """A help text wrapped to the width of a Kconfig."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) + 1 > 72:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return "\n".join(indent + l for l in lines)


def gen_kconfig(boards, modules):
    L = []
    out = L.append
    out("# The Kconfig of the boards, made by tools/boards_gen.py --all from boards-data/: do not edit")
    out("# by hand. One choice of the board, one option a module, and beside them the hidden symbols")
    out("# the rules of idf_component.yml look at, so that the parts a board needs others than this")
    out("# component come only with the board that needs them (the model of esp-bsp's bsp_selector).")
    out("menu \"Boards\"")
    out("")
    out("choice BOARD_SELECT")
    out("    prompt \"Board the program runs on\"")
    out("    default BOARD_SELECT_NONE")
    out("    help")
    out(kconfig_help("One board of boards-data/, or none (the program sets its hardware up itself). "
                     "The board's own sdkconfig.defaults carries the line that chooses it here "
                     "(CONFIG_BOARD_SELECT_<BOARD>=y, tools/board_select.py puts the file into the "
                     "project); what the choice takes with it, the drivers of DGX its panel needs, comes "
                     "as selects, and the parts others than DGX (a touch driver, a codec) by the rules of "
                     "idf_component.yml on the symbols below."))
    out("")
    out("config BOARD_SELECT_NONE")
    out("    bool \"None: the program sets its hardware up itself\"")
    out("")
    for board in boards:
        out(f"config {choice_symbol(board)}")
        out(f"    bool \"{menu_text(board)}\"")
        out(f"    depends on IDF_TARGET_{board['mcu']['target'].upper()}")
        display = board.get("display")
        if is_pixel(display):
            for symbol in PANEL_SELECTS[display["driver"]]:
                out(f"    select {symbol}")
        out("    help")
        out(kconfig_help(board["description"] + "."))
        out("")
    out("endchoice")
    out("")
    if modules:
        out("# A module is not a board of its own: it rides whichever board the choice above picked, and")
        out("# its glue comes in beside the board's (its sdkconfig.defaults turns it on, read after the board's).")
        for module in modules:
            out(f"config {module_symbol(module)}")
            out(f"    bool \"{menu_text(module)}\"")
            out("    depends on !BOARD_SELECT_NONE")
            out("    help")
            out(kconfig_help(module["description"] + "."))
            out("")
    out("# Hidden symbols the rules of idf_component.yml and CMakeLists.txt look at: the board chosen,")
    out("# as a number (a number is easier for a rule to compare).")
    for board in boards:
        out(f"config BOARD_{board['name'].upper()}")
        out("    int")
        out(f"    default 1 if {choice_symbol(board)}")
        out("    default 0")
        out("")
    out("# What the chosen board and the modules have, as the rules need it: a frame buffer display")
    out("# brings DGX, a touch brings DGX-DI and its driver, sound with an ES8311 brings esp_codec_dev,")
    out("# a character display brings hd44780. Derived from the data, so the data of a board and the")
    out("# rules cannot drift apart.")
    all_features = {}
    for board in boards:
        for feature in features_of(board):
            all_features.setdefault(feature, []).append(choice_symbol(board))
    for module in modules:
        for feature in features_of(module):
            all_features.setdefault(feature, []).append(module_symbol(module))
    for symbol, _, _ in feature_deps(boards):
        all_features.setdefault(symbol, [])
    all_features.setdefault("BOARD_MODULE_CHARACTER_DISPLAY", [])
    for feature in sorted(all_features):
        out(f"config {feature}")
        out("    int")
        if all_features[feature]:
            out(f"    default 1 if {' || '.join(all_features[feature])}")
        out("    default 0")
        out("")
    out("endmenu")
    return "\n".join(L) + "\n"


def gen_manifest_block(boards):
    L = [MANIFEST_BEGIN,
         "  # What a board needs beside this component comes only with the board that needs it: the",
         "  # rules look at the symbols the Kconfig of the boards defines beside the choice (the model of",
         "  # esp-bsp's bsp_selector). Made by tools/boards_gen.py --all from the data: do not edit here."]
    for symbol, component, version in feature_deps(boards):
        L.append(f"  {component}:")
        L.append(f"    version: \"{version}\"")
        L.append("    matches:")
        L.append(f"      - if: \"$CONFIG{{{symbol}}} == 1\"")
    L.append(MANIFEST_END)
    return "\n".join(L)


def replace_between(text, begin, end, block, what):
    """The text with what lies between the marker lines begin and end replaced by block (which carries both markers)."""
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop < start:
        raise ValueError(f"{what}: the markers {begin!r} and {end!r} are not there, in that order")
    stop += len(end)
    return text[:start] + block + text[stop:]


def gen_table(boards, lang="en"):
    """The table of the boards for the README, between its markers."""
    head = {"en": ("board", "chip", "display", "touch", "sound", "button"),
            "ru": ("плата", "чип", "дисплей", "тач", "звук", "кнопка")}[lang]
    none = {"en": "none", "ru": "нет"}[lang]
    L = [TABLE_BEGIN, "| " + " | ".join(head) + " |", "|---|---|---|---|---|---|"]
    for board in boards:
        display = board.get("display")
        if is_pixel(display):
            w, h, mm_w, mm_h = lying(display)
            bus = bus_parts(display["bus"]["bus"])[0]
            bus_name = {"dsi": "MIPI-DSI", "qspi": "QSPI", "spi": "SPI", "p8": "i80"}[bus]
            disp = f"{w}x{h} {display['driver'].upper()}, {bus_name}, {mm_w}x{mm_h} mm"
        elif is_character(display):
            disp = f"{display['geometry']} {display['driver'].upper()}"
        else:
            disp = none
        touch = board.get("touch")
        if touch:
            t = (touch_driver(touch) if touch["kind"] == "esp_lcd_touch" else touch["kind"]).upper()
            if touch.get("resistive"):
                t += {"en": " (resistive)", "ru": " (резистивный)"}[lang]
            if touch["kind"] == "gsl3680":
                t += {"en": " (firmware embedded by the program)", "ru": " (прошивку встраивает программа)"}[lang]
            if not touch["calibration"].get("measured", True):
                t += {"en": "; calibration a placeholder", "ru": "; калибровка-заглушка"}[lang]
        else:
            t = none
        sound = board.get("sound")
        s = ("ES8311" if sound["kind"] == "es8311" else f"DAC, GPIO{sound['out']}") if sound else none
        b = {"en": "yes", "ru": "да"}[lang] if board.get("button") else none
        L.append(f"| {board['title']} | {board['mcu']['target'].upper().replace('ESP32', 'ESP32-').rstrip('-')} | {disp} | {t} | {s} | {b} |")
    L.append(TABLE_END)
    return "\n".join(L)


def read_all(data_dir):
    """Every board and module of the data, boards first, in the order of their directories."""
    boards, modules = [], []
    for board_file in sorted(data_dir.glob("*/board.json")):
        board = read_board(board_file)
        if board["name"] != board_file.parent.name:
            raise ValueError(f'{board_file}: the board names itself "{board["name"]}", its directory is "{board_file.parent.name}"')
        (modules if board.get("module") else boards).append(board)
    return boards, modules


def generated_texts(root, boards, modules):
    """Every file --all writes, path -> text, the files with markers made from their current text."""
    texts = {}
    for board in boards + modules:
        texts[root / "boards" / board["name"] / f"{board['name']}.c"] = gen_c(board)
        texts[root / "boards" / board["name"] / "board.cmake"] = gen_cmake(board)
    texts[root / "boards" / "boards.cmake"] = gen_boards_cmake(boards, modules)
    texts[root / "Kconfig"] = gen_kconfig(boards, modules)
    manifest = root / "idf_component.yml"
    texts[manifest] = replace_between(manifest.read_text(), MANIFEST_BEGIN, MANIFEST_END, gen_manifest_block(boards), str(manifest))
    for readme, lang in (("README.md", "en"), ("README.ru.md", "ru")):
        path = root / readme
        if path.exists() and TABLE_BEGIN in path.read_text():
            texts[path] = replace_between(path.read_text(), TABLE_BEGIN, TABLE_END, gen_table(boards, lang), readme)
    return texts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=pathlib.Path, default=ROOT / "boards-data")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "boards")
    parser.add_argument("--all", action="store_true", help="every board and module, and Kconfig, boards.cmake, the manifest's dependencies, the README tables")
    parser.add_argument("board", nargs="?", help="the board's directory name in boards-data/")
    args = parser.parse_args()
    if not args.all and not args.board:
        parser.error("a board, or --all")
    if args.all:
        boards, modules = read_all(args.data)
        for path, text in generated_texts(ROOT, boards, modules).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text() != text:
                path.write_text(text)
                print(f"{path.relative_to(ROOT)}: written")
        print(f"{len(boards)} boards, {len(modules)} modules")
        return 0
    board_path = args.data / args.board / "board.json"
    if not board_path.exists():
        print(f"{board_path}: no such board", file=sys.stderr)
        return 1
    board = read_board(board_path)
    glue_dir = args.out / board["name"]
    glue_dir.mkdir(parents=True, exist_ok=True)
    (glue_dir / f"{board['name']}.c").write_text(gen_c(board))
    (glue_dir / "board.cmake").write_text(gen_cmake(board))
    print(f"{glue_dir}: the glue of {board['name']} generated (Kconfig and the lists: --all)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
