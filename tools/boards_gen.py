#!/usr/bin/env python3
"""Generate everything the data of the boards decides.

Usage: boards_gen.py [--data DIR] [--out DIR] BOARD
       boards_gen.py --all

For one board, reads catalog/boards/BOARD/board.json and writes into boards/BOARD/:
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

The board's sdkconfig.defaults is not generated: it is catalog/boards/BOARD/sdkconfig.defaults
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
             marks a placeholder); x_max and y_max are the largest coordinates, and
             esp_lcd_touch_config_t takes one more, the number of coordinates
  sound      a codec on a bus (es8311), an amplifier on I2S (i2s) or the chip's own DAC on a pin (dac)
  button     its pin, active_low
  sd         the slot, a device on a bus of the board, its cs its own
  module     true: not a board but a device any board's bus can carry (the 2004 backpack);
             no mcu, no buses, no button of its own

Run from the repository root:

    python3 tools/boards_gen.py --all
    python3 tools/boards_gen.py jc1060p470c
"""

import argparse
import collections
import json
import pathlib
import re
import sys

import resolve
import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORMAT_VERSION = 2
RULES = json.loads((ROOT / "catalog" / "rules.json").read_text())

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

I2C_HZ_DEFAULT = 400000
INPUT_LINES = ("in", "int", "irq", "te", "busy")  # lines of a device that only come in
STARTED_CLASSES = {"display", "touch", "audio", "button"}  # the rest is kept as data

MANIFEST_BEGIN = "  # boards: dependencies generated"
MANIFEST_END = "  # boards: end of generated"
LOCAL_CMAKE = """# The boards of this program, made by tools/board_select.py: do not edit by hand. A component only for
# its Kconfig.projbuild: jef-sure/boards compiles the glue of the chosen board with its own.
idf_component_register()
"""
CATALOG_INDEX = "index.json"
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


def fill_call(step, values):
    """A step of a library as a C call: its {names} replaced by the values of this board."""
    args = [re.sub(r"\{(\w+)\}", lambda m: str(values[m[1]]), arg) for arg in step["args"]]
    return f"{step['call']}({', '.join(args)})"


def transport_of(display):
    """What the library of a display says about the kind of its bus."""
    return resolve.library(display["library"])["transports"][bus_parts(display["bus"]["bus"])[0]]


def idf_name(record):
    """A library as a component of the build: one that is downloaded has its owner in the name."""
    return record["name"] if record["install"][0]["via"] == "platform" else f"{record['owner']}__{record['name']}"


def adapter_dir(record):
    """Where the code of a library lies in this component."""
    return f"adapters/{record['owner']}__{record['name']}"


def started(board):
    """What the glue starts: for each device the library, its entry for the chip and the libraries that come with it."""
    for device in (*(board.get("displays") or ()), *board["touches"], *board["sounds"]):
        record = resolve.library(device["library"])
        yield record, device["entry"], [resolve.library(name) for name in (record.get("adapter") or {}).get("with", ())]


def port_of(own, prefix):
    """i2c0 -> 0, i2s1 -> 1: the number of the chip's port a bus name claims."""
    digits = own[len(prefix):] if own and own.startswith(prefix) else ""
    return int(digits) if digits.isdigit() else 0


def i2c_address(value):
    """A 7-bit I2C address from the data (0x27, "0x27" or 39), None if it is not one."""
    try:
        address = int(value, 0) if isinstance(value, str) else value
    except ValueError:
        return None
    if not isinstance(address, int) or isinstance(address, bool) or not 0x08 <= address <= 0x77:
        return None
    return address


def is_character(display):
    return bool(display) and display.get("kind") == "character"


def is_pixel(display):
    return bool(display) and display.get("kind") == "graphics"


# ---------------------------------------------------------------------------------------------
# the parts of a board: what the glue starts, read from its devices; the rest stays data
# ---------------------------------------------------------------------------------------------

MODULE_BUS = "i2c.i2c0"  # a module leaves its bus to the board it is on; the glue names this one


def number(value):
    """A line as the number of its GPIO, None when it is not wired."""
    if value == "nc":
        return None
    return value["gpio"] if isinstance(value, dict) and "gpio" in value else value


def started_by(device):
    """The library that starts a device and its entry for the chip: the one named, or the only one with an adapter."""
    libraries = device.get("libraries") or {}
    able = [name for name, entry in libraries.items() if entry.get("adapter")]
    name = device.get("library") or (able[0] if len(able) == 1 else None)
    if not libraries.get(name, {}).get("adapter"):
        raise ValueError(f"{device.get('chip')}: no library this component can start it with: {name or ', '.join(libraries) or 'none in the catalog'}")
    return {"library": name, "entry": libraries[name]}


def display_part(name, device, module):
    key, connection = next(iter(device["on"].items()))
    pins, config = device.get("pins", {}), device["config"]
    part = {"name": name, "driver": device["chip"], "kind": config["kind"], "bus": {"bus": MODULE_BUS if module else key}, "primary": bool(config.get("primary")), **started_by(device)}
    for field in ("cs", "address"):
        if field in connection:
            part["bus"][field] = number(connection[field])
    if "dc" in pins:
        part["bus"]["dc"] = number(pins["dc"])
    if "rst" in pins:
        part["rst"] = number(pins["rst"])
    if "backlight" in pins:
        part["backlight"] = number(pins["backlight"])
        if isinstance(pins["backlight"], dict):
            part["backlight_on_high"] = pins["backlight"].get("active", "high") == "high"
    if config["kind"] == "character":
        part["geometry"] = config["geometry"]
        part["bus"]["pins"] = {line: number(value) for line, value in pins.items()}
    else:
        part["panel"] = config["panel"]
        part.update({field: config[field] for field in ("depth_bits", "color_order") if field in config})
        part["original_orientation"] = device["controls"]["orientation"]["start"]
    return part


def touch_part(name, device):
    key, connection = next(iter(device["on"].items()))
    pins, config = device.get("pins", {}), device["config"]
    started = started_by(device)
    entry = started["entry"]
    part = {"name": name, "kind": entry["adapter"]["kind"], "chip": device["chip"], "bus": key, "firmware": device.get("firmware") or {}, **started}
    if part["kind"] == "esp_lcd_touch":
        part.update({"component": started["library"].split("/", 1)[1], "header": entry["header"], "cs": number(connection["cs"]), "irq": number(pins["int"])})
    else:
        part.update({line: number(pins[line]) for line in ("rst", "int") if line in pins})
    part.update({field: connection[field] for field in ("hz", "address_try") if field in connection})
    part.update({field: config[field] for field in ("over", "x_max", "y_max", "fingers", "resistive", "calibrations") if field in config})
    return part


def sound_part(name, device):
    pins, config = device.get("pins", {}), device["config"]
    started = started_by(device)
    part = {"name": name, "kind": started["entry"]["adapter"]["kind"], **started, **{key: config[key] for key in ("sample_rate", "pa_voltage", "codec_dac_voltage") if key in config}}
    if part["kind"] == "dac":
        part.update({"out": number(pins["out"]), "pa": number(pins["pa"])})
    elif part["kind"] == "i2s":
        part["i2s_bus"] = next(iter(device["on"]))
    else:
        bus = next(key for key in device["on"] if key.startswith("i2c."))
        part.update({"bus": bus, "i2s_bus": next(key for key in device["on"] if key.startswith("i2s.")), "address": device["on"][bus]["address"], "pa": number(pins["pa"]),
                     "volume": device["controls"]["volume"]["start"]})
    return part


def kept_numbers(device):
    """The numbers of a device the component does not set up: its cs and its pins, for board_bus_get."""
    numbers = {}
    for connection in (device.get("on") or {}).values():
        if isinstance(connection.get("cs"), dict) and "gpio" in connection["cs"]:
            numbers["cs"] = connection["cs"]["gpio"]
    numbers.update({line: value["gpio"] for line, value in (device.get("pins") or {}).items() if isinstance(value, dict) and "gpio" in value})
    return numbers


def parts_of(resolved):
    """A resolved board with the devices the glue starts as lists: displays, touches, sounds, buttons; kept for the rest."""
    module = resolved["kind"] == "module"
    board = {**resolved, "touches": [], "sounds": [], "buttons": [], "kept": {}}
    if module:
        board["module"] = True
    board["buses"] = {kind: {own: {key: number(value) for key, value in bus.items()} for own, bus in named.items()} for kind, named in (resolved.get("buses") or {}).items()}
    displays = []
    for name, device in resolved["devices"].items():
        classes = device["classes"]
        if "display" in classes:
            displays.append(display_part(name, device, module))
        elif "touch" in classes:
            board["touches"].append(touch_part(name, device))
        elif "audio" in classes:
            board["sounds"].append(sound_part(name, device))
        elif "button" in classes:
            line = device["pins"]["in"]
            board["buttons"].append({"name": name, "pin": line["gpio"], "active_low": line.get("active") == "low"})
        else:
            board["kept"][name] = kept_numbers(device)
    if displays:
        board["displays"] = [d for d in displays if d["primary"]] + [d for d in displays if not d["primary"]]
        board["display"] = board["displays"][0]
    if "connectors" in resolved:
        board["connectors"] = {name: {**connector, "pins": [number(line) for line in connector["pins"]]} for name, connector in resolved["connectors"].items()}
    return board


def lying(display):
    """The display as it lies: (width, height, mm_w, mm_h) after the swap of its orientation."""
    panel = display["panel"]
    mm_w, mm_h = panel.get("mm_w", 0), panel.get("mm_h", 0)
    if display["original_orientation"].get("swap", False):
        return panel["height"], panel["width"], mm_h, mm_w
    return panel["width"], panel["height"], mm_w, mm_h


def not_started(device):
    """What the data of a device says and the glue cannot do yet."""
    config = device.get("config") or {}
    connections = (device.get("on") or {}).values()
    found = []
    if "chip_try" in device:
        found.append("chip_try: a chip found at start")
    if "timing" in config:
        found.append("config.timing")
    if config.get("clock", "mclk") != "mclk":
        found.append("config.clock of bclk")
    if any(connection.get("format", "std") != "std" for connection in connections):
        found.append("an I2S format other than std")
    if any(connection.get("sio") for connection in connections):
        found.append("SPI with one data line")
    if any(isinstance(line, dict) and "analog" in line for line in (device.get("pins") or {}).values()):
        found.append("a button on a resistor ladder")
    if "touch" in device["classes"] and "fingers" not in config:
        found.append("a touch whose chip does not say its fingers")
    return found


def read_board(path):
    """The data of a board, checked: what the generator needs is there and of a kind it knows."""
    data = json.loads(path.read_text())
    if data.get("format") != "jef-sure/boards":
        raise ValueError(f'not of the format jef-sure/boards: "{data.get("format")}"')
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f'format_version {data.get("format_version")} is not {FORMAT_VERSION}')
    try:
        resolved = resolve.resolve(data)
    except resolve.Refused as err:
        raise ValueError(f"{path}: {err}") from err
    found = rules.check(resolved, RULES)
    if found:
        raise ValueError(f"{path}: " + "; ".join(item["message"] for item in found))
    switched = [step.get("name", f"step {at}") for at, step in enumerate(resolved.get("power") or []) if "line" in step]
    if switched:
        raise ValueError(f"{path}: the glue cannot set the lines of power yet: {', '.join(switched)}")
    for name, device in resolved["devices"].items():
        if STARTED_CLASSES & set(device["classes"]) and not_started(device):
            raise ValueError(f"{path}: {name}: the glue cannot start this yet: {', '.join(not_started(device))}")
        if "touch" in device["classes"] and (device.get("config") or {}).get("over") == "none":
            raise ValueError(f"{path}: {name}: a touch with no display: DGX-DI has no pointer for it yet")
    characters = [name for name, device in resolved["devices"].items() if (device.get("config") or {}).get("kind") == "character"]
    if characters and len([d for d in resolved["devices"].values() if "display" in d["classes"]]) > 1:
        raise ValueError(f"{path}: a character display beside another display is not set up yet: {', '.join(characters)}")
    data = parts_of(resolved)
    kinds = [sound["kind"] for sound in data["sounds"]]
    if len(set(kinds)) != len(kinds):
        raise ValueError(f"{path}: the adapter of a kind of sound drives one output yet: {', '.join(kinds)}")
    name = data.get("name")
    if not name or not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("the name is lowercase letters, digits and _ only")
    if not data.get("title"):
        raise ValueError("no title")
    is_module = bool(data.get("module"))
    if is_module and (data["buttons"] or data["touches"] or data["sounds"]):
        raise ValueError("a module set up on its own is a display for now: name the others in modules of the board")
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
                signals = ("mosi", "sclk") if kind == "spi" else ("d0", "d1", "d2", "d3", "sclk")  # a display may have no miso
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
                for signal in ("bclk", "ws", "dout"):
                    if not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus i2s.{own} lacks its "{signal}" pin')
                for signal in ("mclk", "din"):
                    if bus.get(signal) is not None and not isinstance(bus.get(signal), int):
                        raise ValueError(f'the bus i2s.{own} has a {signal} that is not a pin')
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
    if len(buses.get("i2c") or {}) > 1:
        raise ValueError("only one I2C bus per board is supported: the glue creates a single I2C master")

    # the display: a pixel panel of dgx or a character LCD of hd44780
    display = data.get("display")
    if is_module and not is_character(display):
        raise ValueError("a module is a character display (hd44780) for now")
    for display in data.get("displays") or ([display] if display is not None else []):
        driver = display.get("driver")
        if is_character(display):
            geometry = display.get("geometry")
            geometries = display["entry"]["supports"]["geometry"]
            if geometry not in geometries:
                raise ValueError(f'the geometry {geometry} is not one the driver {driver} takes ({", ".join(geometries)})')
            transport = display.get("bus", {})
            bus_name = transport.get("bus", "") if isinstance(transport, dict) else transport
            kind = bus_parts(bus_name)[0] if isinstance(bus_name, str) else None
            if kind == "i2c":
                if i2c_address(transport.get("address")) is None:
                    raise ValueError('a character LCD on I2C needs the 7-bit address of its backpack, e.g. "0x27"')
                if not is_module and bus_of(data, bus_name) is None:
                    raise ValueError(f'the character LCD is on the board\'s bus "{bus_name}", which the board does not wire')
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
                raise ValueError('a character LCD is on one of three transports: "i2c.<own>" (a PCF8574 backpack), "gpio.4bit", "gpio.8bit"')
        elif is_pixel(display):
            bus_name = display.get("bus", {}).get("bus")
            if not bus_name or bus_parts(bus_name)[0] not in display["entry"]["on"]:
                raise ValueError('the display\'s bus is a name from buses: "spi.spi2", "qspi.spi2", "dsi.dsi0", "p8.i80"')
            if bus_of(data, bus_name) is None:
                raise ValueError(f'the display\'s bus "{bus_name}" is not among the board\'s buses')
            panel = display.get("panel")
            if not panel or not all(isinstance(panel.get(k), int) for k in ("width", "height")):
                raise ValueError("the panel of the display lacks its size in pixels")
            depth = display.get("depth_bits", 16)
            depths = display["entry"]["supports"]["depth_bits"]
            if depth not in depths:
                raise ValueError(f'depth_bits {depth} is not one the driver {driver} takes ({", ".join(map(str, depths))})')
            if "mm_w" in panel:
                if panel["width"] > panel["height"] and panel["mm_w"] < panel["mm_h"] or \
                   panel["width"] < panel["height"] and panel["mm_w"] > panel["mm_h"]:
                    raise ValueError("the panel's pixels and its millimetres lie different ways: both are the glass as the controller scans it")
                ratio_px = panel["width"] / panel["height"]
                ratio_mm = panel["mm_w"] / panel["mm_h"]
                if abs(ratio_px - ratio_mm) / max(ratio_px, ratio_mm) > 0.2:
                    raise ValueError(f"the panel's pixels ({panel['width']}x{panel['height']}) and its millimetres ({panel['mm_w']}x{panel['mm_h']}) are not near one proportion")
            orientation = display.get("original_orientation")
            names = resolve.library(display["library"])["values"]
            if not orientation or orientation.get("x") not in names["dir_x"] or orientation.get("y") not in names["dir_y"]:
                raise ValueError("the original_orientation of the display is not left-right/right-left x top-bottom/bottom-top")
            kind = bus_parts(bus_name)[0]
            for line in display["entry"]["supports"].get("lines") or {"spi": ("cs", "dc"), "qspi": ("cs",), "p8": ("cs",), "dsi": ()}[kind]:
                if line not in display["bus"]:
                    raise ValueError(f'the display lacks its "{line}" line')
        else:
            raise ValueError(f'panel driver not known: "{driver}"')

    # the touch, the sound, the button, the sd slot
    for touch in data["touches"]:
        display = next((shown for shown in data.get("displays") or [] if shown["name"] == touch.get("over")), None)
        if not is_pixel(display):
            raise ValueError("a touch panel needs a graphics display: the board has none")
        if not touch.get("calibrations"):
            raise ValueError("the touch has no calibration: measure the board (dgx_di_calibrate_measure) and put it in the data; measured: false marks a placeholder")
        calibration = touch["calibration"] = touch["calibrations"][-1]  # the newest: one for the versions in use is for later
        for key in ("x_max", "y_max", "width", "height", "left_up", "right_up", "left_down", "right_down"):
            if key not in calibration:
                raise ValueError(f'the calibration lacks its "{key}"')
        if "measured" in calibration and not isinstance(calibration["measured"], bool):
            raise ValueError("calibration.measured is true or false")
        if not isinstance(touch.get("x_max"), int) or not isinstance(touch.get("y_max"), int):
            raise ValueError("the touch lacks its x_max and y_max, the range of its coordinates")
        # the glue compares these with the device and the display, and refuses a calibration that differs
        if (calibration["x_max"], calibration["y_max"]) != (touch["x_max"], touch["y_max"]):
            raise ValueError("the calibration is for another panel: its x_max/y_max differ from the touch's")
        panel = display["panel"]
        if (calibration["width"], calibration["height"]) != (panel["width"], panel["height"]):
            raise ValueError("the calibration is for another display: its width/height differ from the panel's")
        if not touch.get("bus") or bus_of(data, touch["bus"]) is None:
            raise ValueError(f'the touch\'s bus "{touch.get("bus")}" is not among the board\'s buses')
        if touch["kind"] in ("gt911", "gsl3680") and bus_parts(touch["bus"])[0] != "i2c":
            raise ValueError(f'a {touch["kind"]} is on an I2C bus of the board: bus is its name, "i2c.i2c0"')
        if touch["kind"] == "gt911":
            for address in touch.get("address_try") or ["0x5d"]:
                if i2c_address(address) not in (0x5D, 0x14):
                    raise ValueError(f'a GT911 has address 0x5d or 0x14, not {address}')
        if touch["kind"] == "esp_lcd_touch":
            if bus_parts(touch["bus"])[0] != "spi":
                raise ValueError('a touch of the esp_lcd_touch kind is on an SPI bus of the board: bus is its name, "spi.spi3"')
            for line in ("cs", "irq"):
                if not isinstance(touch.get(line), int):
                    raise ValueError(f'the touch lacks its "{line}" pin')
    for sound in data["sounds"]:
        if sound.get("kind") not in ("es8311", "dac", "i2s"):
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
        elif sound["kind"] == "i2s":
            if bus_of(data, sound.get("i2s_bus", "")) is None or bus_parts(sound.get("i2s_bus", ""))[0] != "i2s":
                raise ValueError('the amplifier streams over a board\'s I2S bus: i2s_bus is its name, "i2s.i2s0"')
        else:
            if bus_of(data, sound.get("bus", "")) is None or bus_parts(sound.get("bus", ""))[0] != "i2c":
                raise ValueError('the codec comes on a board\'s I2C bus: bus is its name, "i2c.<own>"')
            if bus_of(data, sound.get("i2s_bus", "")) is None or bus_parts(sound.get("i2s_bus", ""))[0] != "i2s":
                raise ValueError('the codec streams over a board\'s I2S bus: i2s_bus is its name, "i2s.i2s0"')
            if not isinstance(bus_of(data, sound["i2s_bus"]).get("mclk"), int):
                raise ValueError(f'the codec needs the mclk of {sound["i2s_bus"]}')
            if i2c_address(sound.get("address")) is None:
                raise ValueError('the codec needs its 7-bit I2C address, e.g. "0x18"')
            if not isinstance(sound.get("volume"), int):
                raise ValueError("the codec needs its volume, 0..100")
    return data


# ---------------------------------------------------------------------------------------------
# the pins of a board, each with its owner: for the map of pins and the check of conflicts
# ---------------------------------------------------------------------------------------------

def pins_of(board):
    """Every pin the data names, as (pin, owner, direction): direction "out", "in" or "bus"."""
    pins = []
    for kind, named in (board.get("buses") or {}).items():
        for own, bus in (named or {}).items():
            for key, value in sorted((bus or {}).items()):
                if key in resolve.NOT_LINES or not isinstance(value, int):
                    continue
                # only MISO and I2S DIN are inputs; data lines are bidirectional and RD is driven by the chip
                pins.append((value, f"{kind}.{own}.{key}", "in" if key in ("miso", "din") else "bus"))
    for step in board.get("power") or []:
        if isinstance(step.get("line"), dict) and "gpio" in step["line"]:
            pins.append((step["line"]["gpio"], f"power.{step.get('name', 'strobe')}", "out"))
    for name, device in board["devices"].items():
        for line, value in sorted((device.get("pins") or {}).items()):
            if isinstance(value, dict) and "gpio" in value:
                pins.append((value["gpio"], f"{name}.{line}", "in" if line in INPUT_LINES else "out"))
        divider = (device.get("config") or {}).get("divider") or {}
        if isinstance(divider.get("switch"), dict) and "gpio" in divider["switch"]:
            pins.append((divider["switch"]["gpio"], f"{name}.divider", "out"))
        for connection in (device.get("on") or {}).values():
            if isinstance(connection.get("cs"), dict) and "gpio" in connection["cs"]:
                pins.append((connection["cs"]["gpio"], f"{name}.cs", "out"))
    return pins


def pin_map(board):
    """Every GPIO of the chip of a board: what it can do, who has it, where it comes out and when it is free."""
    gpio = board["mcu"]["facts"]["gpio"]
    owners = {}
    for pin, owner, _ in pins_of(board):
        owners.setdefault(pin, []).append(owner)
    outside = {}
    for name, connector in (board.get("connectors") or {}).items():
        for pin in connector["pins"]:
            if isinstance(pin, int):
                outside.setdefault(pin, []).append(name)
    shared = {group["line"]["gpio"]: group for group in (board.get("shared_pins") or {}).values() if isinstance(group["line"], dict)}
    out = {}
    for pin in gpio["valid"]:
        entry = {"owners": owners.get(pin, []), "connectors": outside.get(pin, []), "strapping": pin in gpio.get("strapping", ()), "input_only": pin in gpio["input_only"]}
        entry.update(gpio.get("pins", {}).get(str(pin), {}))
        if pin in shared and "only_while" in shared[pin]:
            when = shared[pin]["only_while"]
            entry["free_while"] = f"{when['device']}.{when['control']} is {when['value']}"
        entry["state"] = "free" if not entry["owners"] else "shared" if pin in shared else "taken"
        out[pin] = entry
    return out


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
    shared = {group["line"].get("gpio") for group in (board.get("shared_pins") or {}).values() if isinstance(group["line"], dict)}
    for pin, names in sorted(owners.items()):
        if pin in shared:
            continue
        if len(names) > 1:
            problems.append(f"GPIO {pin} has two owners: {', '.join(names)}")
    return problems


# ---------------------------------------------------------------------------------------------
# what a board raises: the hidden symbols of the Kconfig the rules of the manifest look at
# ---------------------------------------------------------------------------------------------

def features_of(board):
    """The hidden symbols a board or a module raises when chosen."""
    features = set()
    if board.get("display_groups"):
        features.add("BOARD_DISPLAY_GROUP")
    if is_character(board.get("display")) and board.get("module"):
        features.add("BOARD_MODULE_CHARACTER_DISPLAY")
    for record, entry, also in started(board):
        features.update(used["adapter"]["symbol"] for used in (record, *also))
        features.update(entry["adapter"].get("symbols", ()))
    return features


def install_lines(way, version):
    """How the manifest gets a library: the way it is taken, for the version the adapter asks."""
    if way["via"] == "registry":
        return [f'version: "{version}"']
    if way["via"] != "git":
        raise ValueError(f'a manifest cannot take a library through "{way["via"]}"')
    if version[0] in "^~<>=" and "{version}" in way.get("ref", ""):
        raise ValueError(f"a tag of git is one version, not the range {version}")
    lines = [f"git: {way['url']}"] + ([f"path: {way['path']}"] if "path" in way else [])
    return lines + ([f'version: "{way["ref"].replace("{version}", version)}"'] if "ref" in way else [])


def feature_deps():
    """The dependencies the rules bring, (symbol, component, its lines in the manifest): the libraries the adapters are written against."""
    deps = []
    for record in resolve.all_libraries(tuple(resolve.ROOTS)).values():
        adapter = record.get("adapter") or {}
        if "version" in adapter:
            deps.append((adapter["symbol"], f"{record['owner']}/{record['name']}", install_lines(record["install"][0], adapter["version"])))
    return deps


def choice_symbol(board):
    return f"BOARD_SELECT_{board['name'].upper()}"


def module_symbol(board):
    return f"BOARD_MODULE_{board['name'].upper()}"


def derive_requires(board):
    """What the glue needs at link, derived from what the board has."""
    requires = set()
    for kind in (board.get("buses") or {}):
        requires.add({"i2c": "esp_driver_i2c", "i2s": "esp_driver_i2s", "spi": "esp_driver_spi", "qspi": "esp_driver_spi"}.get(kind, "esp_driver_gpio"))
    for record, _, also in started(board):
        requires.update(idf_name(used) for used in (record, *also))
        requires.update(record["adapter"].get("requires", ()))
    for shown in board.get("displays") or ():
        requires.update(resolve.library(shown["library"])["transports"].get(bus_parts(shown["bus"]["bus"])[0], {}).get("requires", ()))
    if board["buttons"]:
        requires.add("esp_driver_gpio")
    requires.update(board.get("extra_requires", []))
    return sorted(requires)


# ---------------------------------------------------------------------------------------------
# the C glue
# ---------------------------------------------------------------------------------------------

def c_aims(cal):
    """The places of a calibration as the initializers of dgx_di_aim_t."""
    places = [value for value in cal.values() if isinstance(value, dict) and "meant" in value]
    return [f"{{.meant_x = {p['meant'][0]}, .meant_y = {p['meant'][1]}, .x = {p['device'][0]}, .y = {p['device'][1]}}}" for p in places]


def c_gpio(num):
    return "GPIO_NUM_NC" if num is None else f"GPIO_NUM_{num}"


def gen_c(board):
    """The C glue of the board: every function of boards.h, by the data or returning false."""
    name = board["name"]
    buses = board.get("buses") or {}
    display = board.get("display")
    touches, sounds, buttons = board["touches"], board["sounds"], board["buttons"]
    is_module = bool(board.get("module"))
    pixel = is_pixel(display)
    character = is_character(display)
    i2c_buses = sorted((buses.get("i2c") or {}).items())
    i2c_port = port_of(i2c_buses[0][0], "i2c") if i2c_buses else 0
    # dgx_spi_init() keeps its host for the display: a device beside the display needs a host
    # set up here and dgx_spi_init_on_bus(), and a display alone leaves no bus for the program
    displays = [shown for shown in board.get("displays") or [] if is_pixel(shown)]
    groups = board.get("display_groups") or {}
    display_buses = {shown["bus"]["bus"] for shown in displays}
    beside = [key for part, device in board["devices"].items() if part not in {shown["name"] for shown in displays} for key in device.get("on") or ()]
    beside += [name for name in display_buses if sum(shown["bus"]["bus"] == name for shown in displays) > 1]
    shared = {name for name in display_buses if bus_parts(name)[0] == "spi" and name in beside}
    plain_spi = {own: bus for own, bus in (buses.get("spi") or {}).items() if f"spi.{own}" in shared or f"spi.{own}" not in display_buses}
    L = []
    out = L.append
    out("/*")
    out(f" * The glue of {name}, made by tools/boards_gen.py from {data_path(board)}: do not")
    out(" * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).")
    if is_module:
        out(" * A module: not a board but a device the chosen board's bus carries; it gives the function of")
        out(" * its kind, and the board's glue leaves that one out (CONFIG_BOARD_MODULE_CHARACTER_DISPLAY).")
    else:
        out(" * Every function of boards.h is here: by the data for the parts the board has, returning")
        out(" * false for the parts it has not, so the contract of boards.h holds at link.")
    out(" */")
    out("#include \"boards.h\"")
    out("#include \"board_glue.h\"")
    out("")
    out("#include \"sdkconfig.h\"")
    out("")
    headers = ["stdlib.h", "string.h", "esp_log.h"]
    for record, entry, also in started(board):
        headers += [header for used in (record, *also) for header in used["adapter"].get("headers", ())] + entry["adapter"].get("headers", [])
    if character and bus_parts(display["bus"]["bus"])[0] == "gpio":
        headers.append("driver/gpio.h")
    for shown in displays:
        headers.append(transport_of(shown)["header"])
        headers.append(shown["entry"]["header"])
    for touch in touches:
        if touch["kind"] == "esp_lcd_touch":
            headers.append(touch["header"])
            headers.append("driver/spi_common.h")
    if any(sound["kind"] != "dac" for sound in sounds):
        headers.append("driver/i2s_std.h")  # I2S_NUM_* of the table of buses
    if plain_spi:
        headers.append("driver/spi_common.h")  # SPI2_HOST of the table of buses
    for header in sorted(set(headers)):
        out(f"#include <{header}>" if header in ("stdlib.h", "string.h") else f"#include \"{header}\"")
    out("")
    out(f"/* {board['title']}: {board['description']}. */")
    out("")

    # ---- the pins of the board, each named by the part it serves ----
    if not is_module:
        out("/* The buses of the board. */")
        for own, bus in sorted(plain_spi.items()):
            hz = f", .hz = {bus['hz']}" if bus.get("hz") is not None else ""
            out(f"static const struct board_spi_bus board_spi_{own} = {{.host = {own.upper()}_HOST, .mosi = {c_gpio(bus['mosi'])}, .miso = {c_gpio(bus['miso'])}, .sclk = {c_gpio(bus['sclk'])}{hz}}};")
        for own, bus in i2c_buses[:1]:
            out(f"static const struct board_i2c_pins board_i2c_pins_of = {{.port = I2C_NUM_{port_of(own, 'i2c')}, .sda = {c_gpio(bus['sda'])}, .scl = {c_gpio(bus['scl'])}}}; /* i2c.{own} */")
        for own, bus in sorted((buses.get("i2s") or {}).items()):
            out(f"static const struct board_i2s_bus board_i2s_{own} = {{.port = I2S_NUM_{port_of(own, 'i2s')}, .mclk = {c_gpio(bus['mclk'])}, .bclk = {c_gpio(bus['bclk'])}, .ws = {c_gpio(bus['ws'])}, .dout = {c_gpio(bus['dout'])}, .din = {c_gpio(bus.get('din'))}}};")
        out("")

        # ---- every bus of the board, its numbers by name: the universal table ----
        rows = []
        for kind, named in buses.items():
            for own, bus in named.items():
                for key, value in sorted((bus or {}).items()):
                    if isinstance(value, int):
                        rows.append((f"{kind}.{own}", key, value))
        for own, numbers in board["kept"].items():
            rows.extend((own, key, value) for key, value in sorted(numbers.items()))
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
        if plain_spi:
            entries = ", ".join(f"&board_spi_{own}" for own in sorted(plain_spi))
            out("/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */")
            out(f"static const struct board_spi_bus *const board_spi_buses[] = {{{entries}}};")
            out("")
            out("const struct board_spi_bus *board_spi_bus(int host)")
            out("{")
            out("    for (size_t i = 0; i < sizeof(board_spi_buses) / sizeof(board_spi_buses[0]); ++i)")
            out("        if (board_spi_buses[i]->host == host) return board_spi_buses[i];")
            out("    return NULL;")
            out("}")
        else:
            out("/* The board has no SPI bus open to the program's devices. */")
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
        kind, width = bus_parts(transport["bus"])
        gpins = transport.get("pins", {})
        cols, rows = display["geometry"].split("x")
        out(f"/* The character display: a {display['geometry']} {display['driver']} on {transport['bus']}. */")
        out("static lcd_bus_hd44780_t *character_bus(void)")
        out("{")
        library = resolve.library(display["library"])
        if kind == "i2c":
            step = library["transports"]["i2c"]["shared"]
            out("    i2c_master_bus_handle_t bus = board_glue_i2c();")
            out(f"    return bus ? {fill_call(step, {'i2c_bus': 'bus', 'address': format(i2c_address(transport.get('address')), '#04x'), **library['transports']['i2c']['defaults']})} : NULL;")
        else:
            out(f"    return {fill_call(library['transports'][transport['bus']]['init'], collections.defaultdict(lambda: c_gpio(None), {pin: c_gpio(num) for pin, num in gpins.items()}))};")
        out("}")
        out("")
        out(f"static const struct board_character_panel character_panel = {{.geometry = HD44780_GEOMETRY_{cols}X{rows}, .cols = {cols}, .rows = {rows}, .bus = character_bus}};")
        out("")
        out("bool board_character_display_init(struct board_character_display *out)")
        out("{")
        out("    return board_glue_character_init(&character_panel, out);")
        out("}")
        out("")
    elif pixel:
        rows, group_rows = [], []
        for name, group in sorted(groups.items(), key=lambda item: not item[1].get("primary")):
            group_rows.append((name, group))
        first = len(group_rows) if any(group.get("primary") for _, group in group_rows) else 0  # a primary group stands first
        place = {shown["name"]: first + i for i, shown in enumerate(displays)}
        for i, shown in enumerate(displays):
            db = shown["bus"]
            bus_name = db["bus"]
            kind, own = bus_parts(bus_name)
            bus = bus_of(board, bus_name)
            panel = shown["panel"]
            orientation = shown["original_orientation"]
            driver = shown["driver"]
            entry = shown["entry"]
            library = resolve.library(shown["library"])
            transport = transport_of(shown)
            out(f"/* {shown['name']}: a {panel['width']}x{panel['height']} {driver} on {bus_name}. */")
            out(f"static dgx_bus_protocols_t *display{i}_bus(void)")
            out("{")
            values = {**transport.get("defaults", {}), **{key: value if key in resolve.NOT_LINES else c_gpio(value) for key, value in bus.items()}, "host": f"{(own or '').upper()}_HOST"}
            own_select = "{cs}" in entry["init"][0]["args"]  # the driver of such a chip holds its select itself, so the bus has none
            values.update({"dc": "GPIO_NUM_NC", **{line: c_gpio(db[line]) for line in ("cs", "dc") if line in db and not (own_select and line == "cs")}})
            values.setdefault("cs", "GPIO_NUM_NC")
            if bus_name in shared:
                out(f"    if (!board_glue_spi_host(&board_spi_{own})) return NULL;")
                out(f"    return {fill_call(transport['shared'], values)};")
            else:
                out(f"    return {fill_call(transport['init'], values)};")
            out("}")
            out("")
            backlight = c_gpio(shown.get("backlight"))
            order = "bgr" if shown.get("color_order") == "bgr" else "rgb"
            values = {"bus": "bus", "rst": c_gpio(shown.get("rst")), "cs": c_gpio(db.get("cs")), "backlight": backlight, "depth": shown.get("depth_bits", 16),
                      "color": library["values"]["color_order"][order], "width": panel["width"], "height": panel["height"]}
            out(f"static dgx_screen_t *display{i}_screen(dgx_bus_protocols_t *bus)")
            out("{")
            out(f"    return {fill_call(entry['init'][0], values)};")
            out("}")
            out("")
            light = backlight if any(step.get("line") == "backlight" for step in entry.get("setup", ())) else "GPIO_NUM_NC"
            rows.append(f"    {{.name = \"{shown['name']}\", .glass_w = {panel['width']}, .glass_h = {panel['height']}, .mm_w = {panel.get('mm_w', 0)}, .mm_h = {panel.get('mm_h', 0)}, "
                        f".dir_x = {library['values']['dir_x'][orientation['x']]}, .dir_y = {library['values']['dir_y'][orientation['y']]}, .swap_xy = {'true' if orientation.get('swap', False) else 'false'}, "
                        f".backlight = {light}, .backlight_on = {1 if shown.get('backlight_on_high', True) else 0}, .bus = display{i}_bus, .screen = display{i}_screen, .orientation = {entry['controls']['orientation']['call']}}},")
        grouped = [f"    {{.name = \"{name}\", .group = true, .left = {place[group['left']]}, .right = {place[group['right']]}}}," for name, group in group_rows]
        table = grouped + rows if first else rows + grouped
        out("static const struct board_display_panel display_panels[] = {")
        for row in table:
            out(row)
        out("};")
        out(f"static struct board_display_started displays_started[{len(table)}];")
        out(f"const struct board_display_table board_display_table = {{.panels = display_panels, .started = displays_started, .count = {len(table)}}};")
        out("")

    # ---- the touch panels, the sound, the buttons: tables src/ starts from ----
    if not is_module:
        entries = []
        for i, touch in enumerate(touches):
            kind = touch["kind"]
            cal = touch["calibration"]
            measured = cal.get("measured", True)
            out(f"/* {touch['name']}: {touch.get('component', kind)} on {touch['bus']}, the calibration of its measured board. */")
            if not measured:
                out("/* The calibration below is a placeholder, not measured on a board: the touch works, only not")
                out(" * straight; board_touch_start says so. Measure the board (dgx_di_calibrate_measure) and put the")
                out(" * numbers in the data. */")
            aims = c_aims(cal)
            takers = (touch["library"], *resolve.library(touch["library"]).get("adapter", {}).get("with", ()))
            own = next((part for name, part in (cal.get("libraries") or {}).items() if name in takers), {})
            out(f"static const dgx_di_aim_t touch{i}_aims[] = {{{', '.join(aims)}}};")
            out(f"static const struct board_touch_calibration touch{i}_calibrated = {{.aims = touch{i}_aims, .count = {len(aims)}, .width = {cal['width']}, .height = {cal['height']}, "
                f".blink_ms = {own.get('blink_ms', 0)}, .gap_ms = {own.get('gap_ms', 0)}, .placeholder = {'false' if measured else 'true'}}};")
            irq = touch.get("irq") if kind == "esp_lcd_touch" else touch.get("int")
            out(f"static const struct board_touch_panel touch{i}_panel = {{.x_max = {touch['x_max'] + 1}, .y_max = {touch['y_max'] + 1}, .rst = {c_gpio(touch.get('rst'))}, .irq = {c_gpio(irq)}, .fingers = {touch.get('fingers', 1)}}};")
            if kind == "gt911":
                addresses = [f"{i2c_address(a):#04x}" for a in (touch.get("address_try") or ["0x5d"])]
                out(f"static const uint8_t touch{i}_addresses[] = {{{', '.join(addresses)}}};")
                out(f"static const struct board_touch_gt911 touch{i}_driver = {{.panel = &touch{i}_panel, .addresses = touch{i}_addresses, .address_count = {len(addresses)}, .i2c_hz = {I2C_HZ_DEFAULT}}};")
            elif kind == "esp_lcd_touch":
                own = bus_parts(touch["bus"])[1]
                out(f"static const struct board_touch_spi touch{i}_driver = {{.panel = &touch{i}_panel, .host = {own.upper()}_HOST, .cs = {c_gpio(touch['cs'])}, .hz = {touch.get('hz', touch['entry']['defaults']['hz'])}, "
                    f".create = {touch['entry']['init'][0]['call']}}};")
            device_type = "dgx_di_gsl3680_t" if kind == "gsl3680" else "dgx_di_esp_lcd_touch_t"
            out(f"static {device_type} touch{i}_device;")
            out("")
            out(f"static bool touch{i}_start(int index, const struct board_display *display, struct board_touch *out)")
            out("{")
            if kind == "gsl3680":
                out(f"    return board_glue_touch_gsl3680_start(&touch{i}_device, index, &touch{i}_panel, &touch{i}_calibrated, display, out);")
            else:
                make = "gt911" if kind == "gt911" else "spi"
                numbered = "false" if touch.get("resistive") else "true"
                out("    if (!board_dgx_screen(display)) return false;")
                out(f"    esp_lcd_touch_handle_t handle = board_glue_touch_{make}_new(&touch{i}_driver);")
                out(f"    return handle && board_glue_touch_lcd_attach(&touch{i}_device, index, handle, {numbered}, &touch{i}_panel, &touch{i}_calibrated, display, out);")
            out("}")
            out("")
            entries.append(f'{{.name = "{touch["name"]}", .over = "{touch["over"]}", .start = touch{i}_start}}')
        if touches:
            out(f"static const struct board_touch_entry touch_entries[] = {{{', '.join(entries)}}};")
            out(f"static struct board_touch touches_started[{len(touches)}];")
            out(f"static struct board_touch_slot touch_slots[{len(touches)}];")
            out(f"const struct board_touch_slots board_touch_slots = {{.slots = touch_slots, .count = {len(touches)}}};")
            out(f"const struct board_touch_table board_touch_table = {{.entries = touch_entries, .started = touches_started, .count = {len(touches)}}};")
        else:
            out("const struct board_touch_table board_touch_table = {.count = 0};")
        out("")
        entries = []
        for i, sound in enumerate(sounds):
            rate = sound["sample_rate"]
            pa = c_gpio(sound.get("pa"))
            iown = bus_parts(sound.get("i2s_bus", ""))[1]
            out(f"/* {sound['name']}: {sound['kind']} at {rate} Hz. */")
            if sound["kind"] == "es8311":
                out(f"static const struct board_sound_es8311 sound{i}_codec = {{.i2s = &board_i2s_{iown}, .i2c_port = I2C_NUM_{i2c_port}, .address = {i2c_address(sound['address']):#04x}, .pa = {pa},")
                out(f"                                                     .pa_voltage = {float(sound.get('pa_voltage', 5.0))}f, .codec_dac_voltage = {float(sound.get('codec_dac_voltage', 3.3))}f, .volume = {sound['volume']}, .rate = {rate}}};")
                out("")
            out(f"static bool sound{i}_start(int index, board_sound_source_t source)")
            out("{")
            if sound["kind"] == "es8311":
                out(f"    return board_glue_sound_es8311_start(index, &sound{i}_codec, source);")
            elif sound["kind"] == "i2s":
                out(f"    return board_glue_sound_i2s_start(index, &board_i2s_{iown}, {rate}, source);")
            else:
                out(f"    return board_glue_sound_dac_start(index, {c_gpio(sound.get('out'))}, {pa}, {rate}, source);")
            out("}")
            out("")
            entries.append(f'{{.name = "{sound["name"]}", .rate = {rate}, .start = sound{i}_start}}')
        if sounds:
            out(f"static const struct board_sound_entry sound_entries[] = {{{', '.join(entries)}}};")
            out(f"static struct board_sound_stream sound_streams[{len(sounds)}];")
            out(f"const struct board_sound_table board_sound_table = {{.entries = sound_entries, .streams = sound_streams, .count = {len(sounds)}}};")
        else:
            out("const struct board_sound_table board_sound_table = {.count = 0};")
        out("")
        if buttons:
            entries = ", ".join(f'{{.name = "{button["name"]}", .pin = {button["pin"]}, .active_low = {"true" if button["active_low"] else "false"}}}' for button in buttons)
            out(f"static const struct board_button_entry button_entries[] = {{{entries}}};")
            out(f"const struct board_button_table board_button_table = {{.entries = button_entries, .count = {len(buttons)}}};")
        else:
            out("const struct board_button_table board_button_table = {.count = 0};")
        out("")

    # ---- what the board has not: the rest of boards.h, returning false ----
    if not is_module:
        out("/* What the board has not: the rest of boards.h, returning false, so that the same program")
        out(" * links and runs on every board. */")
        if not pixel:
            out("int board_display_count(void)")
            out("{")
            out("    return 0;")
            out("}")
            out("")
            out("bool board_display_init(struct board_display *out)")
            out("{")
            out("    (void)out;")
            out("    return false;")
            out("}")
            out("")
            out("bool board_display_init_at(int index, struct board_display *out)")
            out("{")
            out("    (void)index, (void)out;")
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
        target = board.get("mcu", {}).get("target", "any")
        out("/* What the board is, for board_info(). */")
        out(f"const struct board_data board_data = {{.name = \"{name}\", .title = \"{board['title']}\", .target = \"{target}\"}};")
    return "\n".join(L) + "\n"


def gen_cmake(board):
    """board.cmake: what the glue needs, derived from what the board has."""
    name = board["name"]
    requires = derive_requires(board)
    L = [f"# The glue of {name}, made by tools/boards_gen.py from its data: the components it needs,",
         f"# derived from what the board has (the components of ESP-IDF 5.3 and later; extra_requires",
         f"# in {data_path(board)} adds what the structure cannot say). Do not edit by hand.",
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
         "# from catalog/: CMakeLists.txt compiles the chosen board's glue (CONFIG_BOARD_<BOARD>)",
         "# and every module turned on (CONFIG_BOARD_MODULE_<MODULE>). Do not edit by hand.",
         f"set(BOARDS_LIST {' '.join(b['name'] for b in boards)})",
         f"set(BOARDS_MODULES {' '.join(m['name'] for m in modules)})"]
    adapters = [record for record in resolve.all_libraries(tuple(resolve.ROOTS)).values() if record.get("adapter", {}).keys() & {"headers", "public", "sources"}]
    L.append(f"set(BOARDS_ADAPTER_DIRS {' '.join(adapter_dir(record) for record in adapters)})")
    L.append(f"set(BOARDS_ADAPTER_INCLUDES {' '.join(adapter_dir(record) + '/include' for record in adapters if 'public' in record['adapter'])})")
    sources = [f"{symbol}={adapter_dir(record)}/{source}" for record in adapters for symbol, files in record["adapter"].get("sources", {}).items() for source in files]
    L.append(f"set(BOARDS_ADAPTER_SOURCES {' '.join(sources)})")
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
    parts += [touch["chip"].upper() + " touch" for touch in board["touches"]]
    parts += [{"es8311": "ES8311 sound", "i2s": "I2S amplifier sound"}.get(sound["kind"], "DAC sound") for sound in board["sounds"]]
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


def kconfig_board(board):
    """The entry of a board in the choice."""
    L = [f"config {choice_symbol(board)}", f"    bool \"{menu_text(board)}\"", f"    depends on IDF_TARGET_{board['mcu']['target'].upper()}"]
    selects = [symbol for shown in board.get("displays") or [] if is_pixel(shown) for symbol in transport_of(shown)["select"] + shown["entry"]["select"]]
    for group in (board.get("display_groups") or {}).values():
        selects += resolve.library(board["display"]["library"])["groups"][group["how"]]["select"]
    L.extend(f"    select {symbol}" for symbol in dict.fromkeys(selects))
    L.extend(["    help", kconfig_help(board["description"] + "."), ""])
    return L


def gen_local_kconfig(boards):
    """Kconfig.projbuild of the component local-boards: ESP-IDF reads it before the Kconfig of the component, so its defaults come first."""
    L = ["# The boards of this program, made by tools/board_select.py from boards/: do not edit by hand.",
         "# They join the choice of jef-sure/boards and raise the same hidden symbols.",
         "choice BOARD_SELECT", "    prompt \"Board the program runs on\"", ""]
    for board in boards:
        L.extend(kconfig_board(board))
    L.extend(["endchoice", ""])
    features = {}
    for board in boards:
        L.extend([f"config BOARD_{board['name'].upper()}", "    int", f"    default 1 if {choice_symbol(board)}", "    default 0", ""])
        for feature in features_of(board):
            features.setdefault(feature, []).append(choice_symbol(board))
    for feature in sorted(features):
        L.extend([f"config {feature}", "    int", f"    default 1 if {' || '.join(features[feature])}", ""])
    return "\n".join(L)


def read_local(local):
    """The boards of a program. A board of the catalog cannot be one of them: they would meet in the choice."""
    boards = []
    for path in sorted(local.glob("boards/*/board.json")):
        board = read_board(path)
        if board["name"] != path.parent.name:
            raise ValueError(f'{path}: the board names itself "{board["name"]}", its directory is "{path.parent.name}"')
        if (ROOT / "catalog" / "boards" / board["name"]).exists():
            raise ValueError(f'{path}: the catalog has a board "{board["name"]}", give yours another name')
        board["local"] = True
        boards.append(board)
    return boards


def write_local(local):
    """Everything generated of the component local-boards: its boards stay in its own directory, not in the catalog."""
    boards = read_local(local)
    texts = {local / "Kconfig.projbuild": gen_local_kconfig(boards), local / "CMakeLists.txt": LOCAL_CMAKE}
    for board in boards:
        texts[local / "boards" / board["name"] / f"{board['name']}.c"] = gen_c(board)
        texts[local / "boards" / board["name"] / "board.cmake"] = gen_cmake(board)
    for path, text in texts.items():
        path.write_text(text)


def gen_kconfig(boards, modules):
    L = []
    out = L.append
    out("# The Kconfig of the boards, made by tools/boards_gen.py --all from catalog/: do not edit")
    out("# by hand. One choice of the board, one option a module, and beside them the hidden symbols")
    out("# the rules of idf_component.yml look at, so that the parts a board needs others than this")
    out("# component come only with the board that needs them (the model of esp-bsp's bsp_selector).")
    out("menu \"Boards\"")
    out("")
    out("choice BOARD_SELECT")
    out("    prompt \"Board the program runs on\"")
    out("    default BOARD_SELECT_NONE")
    out("    help")
    out(kconfig_help("One board of catalog/boards/, or none (the program sets its hardware up itself). "
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
        L.extend(kconfig_board(board))
    out("endchoice")
    out("")
    if modules:
        out("# A module is not a board of its own: it is on whichever board the choice above picked, and")
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
    out("# What the chosen board and the modules have, as the rules need it: a graphics display")
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
    for symbol, _, _ in feature_deps():
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
    for symbol, component, lines in feature_deps():
        L.append(f"  {component}:")
        L.extend(f"    {line}" for line in lines)
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
            disp = f"{w}x{h} {display['driver'].upper()}, {bus_name}" + (f", {mm_w}x{mm_h} mm" if mm_w else "")
        elif is_character(display):
            disp = f"{display['geometry']} {display['driver'].upper()}"
        else:
            disp = none
        cells = []
        for touch in board["touches"]:
            t = touch["chip"].upper()
            if touch.get("resistive"):
                t += {"en": " (resistive)", "ru": " (резистивный)"}[lang]
            if touch["firmware"].get("set") == "program":
                t += {"en": " (firmware embedded by the program)", "ru": " (прошивку встраивает программа)"}[lang]
            if not touch["calibration"].get("measured", True):
                t += {"en": "; calibration a placeholder", "ru": "; калибровка-заглушка"}[lang]
            cells.append(t)
        t = ", ".join(cells) or none
        s = ", ".join({"es8311": "ES8311", "i2s": {"en": "I2S amplifier", "ru": "усилитель I2S"}[lang]}.get(sound["kind"], f"DAC, GPIO{sound.get('out')}") for sound in board["sounds"]) or none
        b = {"en": "yes", "ru": "да"}[lang] if board["buttons"] else none
        L.append(f"| {board['title']} | {board['mcu']['target'].upper().replace('ESP32', 'ESP32-').rstrip('-')} | {disp} | {t} | {s} | {b} |")
    L.append(TABLE_END)
    return "\n".join(L)


def has_glue(module_file):
    """A module the component sets up with --module: a chip of it has an adapter. A panel takes its wires from a project."""
    devices = json.loads(module_file.read_text())["devices"].values()
    return any(entry.get("adapter", {}).get("kind") not in (None, "panel") for device in devices for entry in resolve.libraries_of(device.get("chip")).values())


def data_path(board):
    """Where the data of a board or a module lies, for the comments of what is generated."""
    if board.get("local"):
        return f"{resolve.LOCAL_BOARDS}/boards/{board['name']}/board.json"
    return f"catalog/modules/{board['name']}/module.json" if board.get("module") else f"catalog/boards/{board['name']}/board.json"


def read_all(data_dir):
    """Every board and module of the data, boards first, in the order of their directories."""
    boards, modules = [], []
    for board_file in sorted(data_dir.glob("boards/*/board.json")) + sorted(data_dir.glob("modules/*/module.json")):
        if board_file.name == "module.json" and not has_glue(board_file):
            continue  # a module of the catalog only: nothing in it the component sets up yet
        board = read_board(board_file)
        if board["name"] != board_file.parent.name:
            raise ValueError(f'{board_file}: the board names itself "{board["name"]}", its directory is "{board_file.parent.name}"')
        (modules if board.get("module") else boards).append(board)
    return boards, modules


def gen_catalog_index(root):
    """The files of the catalog, for the page of the editor to fetch: a server gives no listing to rely on."""
    catalog = root / "catalog"
    return resolve.dump(sorted(path.relative_to(catalog).as_posix() for path in catalog.rglob("*.json") if path.name != CATALOG_INDEX)) + "\n"


def generated_texts(root, boards, modules):
    """Every file --all writes, path -> text, the files with markers made from their current text."""
    texts = {}
    for board in boards + modules:
        texts[root / "boards" / board["name"] / f"{board['name']}.c"] = gen_c(board)
        texts[root / "boards" / board["name"] / "board.cmake"] = gen_cmake(board)
    texts[root / "boards" / "boards.cmake"] = gen_boards_cmake(boards, modules)
    texts[root / "catalog" / CATALOG_INDEX] = gen_catalog_index(root)
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
    parser.add_argument("--data", type=pathlib.Path, help="directory of a single board's data (default: this repository's catalog/boards)")
    parser.add_argument("--out", type=pathlib.Path, help="output directory of a single board's glue (default: this repository's boards/)")
    parser.add_argument("--all", action="store_true", help="every board and module, and Kconfig, boards.cmake, the manifest's dependencies, the README tables")
    parser.add_argument("board", nargs="?", help="the board's directory name in catalog/boards/")
    args = parser.parse_args()
    if not args.all and not args.board:
        parser.error("a board, or --all")
    if args.all and (args.data or args.out):
        parser.error("--all regenerates this repository's own files: no --data or --out with it")
    args.data = args.data or ROOT / "catalog" / "boards"
    args.out = args.out or ROOT / "boards"
    if args.all:
        boards, modules = read_all(ROOT / "catalog")
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
