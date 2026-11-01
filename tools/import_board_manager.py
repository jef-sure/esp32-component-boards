#!/usr/bin/env python3
"""
Imports the boards of esp_board_manager packs into imported/: esp_boards, guition_boards and the like.

A pack is data from the net: its YAML goes through the safe loader and nothing in it runs. A value the pack does not
give stays absent: what the format then refuses goes to the report with its reason, and what the format has no place
for is counted there. DSI timings and init commands are not taken, shared_pins is not written. A board the catalog
has is not copied: its pins are compared and the differences go to the report.

Needs PyYAML and jsonschema, as in the Python of ESP-IDF.

Usage: import_board_manager.py NAME=PACK_DIR ... [--out DIR] [--date YYYY-MM-DD]
"""
import argparse
import collections
import copy
import datetime
import json
import pathlib
import re
import shutil
import sys

import jsonschema
import yaml

import boards_gen
import resolve
import rules

ROOT = resolve.ROOT
SCHEMA = json.loads((ROOT / "catalog" / "format.schema.json").read_text())
HEAD = {"format": "jef-sure/boards", "format_version": 2}
LEVEL = "extracted"
TOOL = "tools/import_board_manager.py"
PLACEHOLDER = re.compile(r"\$\{[^}]*\}")  # a value the pack fills in at build time
SEVEN_BITS = 0x77
NOT_WIRED = (None, -1, "-1", "GPIO_NUM_NC", "NC")
NOT_A_CHIP = ("none", "auto", "internal")
I2S_LINES = ("mclk", "bclk", "ws", "dout", "din")
# the same board in a pack and in the catalog
OURS = {"guition_boards/jc1060p470": "jc1060p470c", "guition_boards/jc8012p4a1": "jc8012p4a1c", "guition_boards/jc4827w543": "jc4827w543c", "guition_boards/esp32_2432s028": "cyd_s028r"}
# a device the pack leaves to C code: its class, from the chip
CUSTOM_CLASS = {"xpt2046": "touch", "axp2101": "pmic", "axp2602": "pmic", "bq27220": "fuel_gauge", "bmi270": "imu", "bmi270_sensor": "imu", "bmi270_sensor_hub": "imu",
                "lp5562": "led", "lr1121": "radio", "ssd1309": "display", "pcf85063a": "rtc", "ssd16xx_290": "display", "es8311_es7210": "audio"}
# the audio with no codec chip: the end of the bus it is
GENERIC_AUDIO = (("i2s:pdm-in", "pdm_mic"), ("i2s:pdm-out", "pdm_out"), ("i2s:std-in", "i2s_mic"), ("i2s:std-out", "i2s_amp"), ("adc:None", "adc_mic"))


class Loader(yaml.SafeLoader):
    """The safe loader, with the !tags of a pack read as plain data."""


def plain(loader, _suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    return loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode) else loader.construct_mapping(node)


Loader.add_multi_constructor("!", plain)


def read_yaml(path):
    if not path.exists():
        return {}
    return yaml.load(PLACEHOLDER.sub("null", path.read_text(errors="ignore")), Loader=Loader) or {}


def word(text):
    text = re.sub(r"[^a-z0-9_]", "_", str(text).lower()).strip("_")
    return text if re.match(r"[a-z]", text) else "x" + text


def line(value):
    return value if isinstance(value, int) and value not in NOT_WIRED else "nc"


def wired(mapping):
    return {key: line(value) for key, value in mapping.items() if line(value) != "nc"}


def given(mapping):
    return {key: value for key, value in mapping.items() if value is not None}


def address(value):
    value = value[0] if isinstance(value, list) else value
    if not isinstance(value, int):
        return None
    return f"{value >> 1 if value > SEVEN_BITS else value:#04x}"


def orientation(flags):
    return {"how": "driver", "start": {"x": "right-left" if flags.get("mirror_x") else "left-right", "y": "bottom-top" if flags.get("mirror_y") else "top-bottom", "swap": bool(flags.get("swap_xy"))}}


class Import:
    """What one run gathers over all boards."""

    def __init__(self):
        self.chips = {}
        self.no_place = collections.Counter()
        self.libraries = collections.defaultdict(set)

    def chip(self, name, kind, buses=()):
        """The stub of a chip the catalog does not have: what the boards say of it."""
        if (ROOT / "catalog" / "devices" / name).exists():
            return
        entry = self.chips.setdefault(name, {**HEAD, "kind": "device", "name": name, "title": name, "class": [], "checked": {"facts": {"level": LEVEL, "source": "the boards that use it"}}})
        entry["class"] = sorted({*entry["class"], kind})
        if buses:
            entry["on"] = {**entry.get("on", {}), **{bus: {} for bus in buses}}


class Board:
    """One board of a pack while it is read."""

    def __init__(self, run, info, devices, peripherals):
        self.run = run
        self.target = info.get("chip", "esp32")
        self.listed = [item for item in devices.get("devices") or [] if isinstance(item, dict)]
        self.peripherals = {item.get("name"): item for item in peripherals.get("peripherals") or [] if isinstance(item, dict)}
        self.buses = {}
        self.names = {}  # a peripheral of the pack -> our bus
        self.rates = {}
        self.of_type = collections.defaultdict(dict)
        self.devices = {}
        self.power = []
        self.lcd = None
        self.rate = None
        self.codecs = {}
        self.merged = {}

    def read_peripherals(self):
        for name, item in self.peripherals.items():
            kind, config = item.get("type"), item.get("config") or {}
            reader = getattr(self, f"peripheral_{kind}", None)
            if reader:
                reader(name, item, config)
            elif kind in ("ldo", "gpio", "ledc", "adc"):
                self.of_type[kind][name] = config
            else:
                self.run.no_place[f"peripheral.{kind}"] += 1
        for own in self.buses.get("dsi", {}).values():
            for config in self.of_type["ldo"].values():
                own.update(given({"phy_ldo_chan": config.get("chan_id"), "phy_ldo_mv": config.get("voltage_mv")}))

    def peripheral_i2c(self, name, _item, config):
        own = f"i2c{config.get('port', 0)}"
        pins = config.get("pins") or {}
        self.buses.setdefault("i2c", {})[own] = {"sda": line(pins.get("sda")), "scl": line(pins.get("scl"))}
        self.names[name] = f"i2c.{own}"

    def peripheral_spi(self, name, _item, config):
        bus = config.get("spi_bus_config") or config
        host = bus.get("spi_port") or config.get("spi_port") or "SPI2_HOST"
        digit = re.search(r"(\d)", str(host))
        own = f"spi{int(host) + 1}" if isinstance(host, int) else f"spi{digit[1] if digit else 2}"
        wp, hd = bus.get("quadwp_io_num", -1), bus.get("quadhd_io_num", -1)
        if isinstance(wp, int) and wp >= 0:
            self.buses.setdefault("qspi", {})[own] = {"d0": line(bus.get("mosi_io_num")), "d1": line(bus.get("miso_io_num")), "d2": wp, "d3": hd, "sclk": line(bus.get("sclk_io_num"))}
            self.names[name] = f"qspi.{own}"
        else:
            self.buses.setdefault("spi", {})[own] = {"mosi": line(bus.get("mosi_io_num")), "miso": line(bus.get("miso_io_num")), "sclk": line(bus.get("sclk_io_num"))}
            self.names[name] = f"spi.{own}"

    def peripheral_i2s(self, name, item, config):
        own = f"i2s{config.get('port', 0)}"
        pins = config.get("pins") or {}
        bus = self.buses.setdefault("i2s", {}).setdefault(own, {})
        for key in I2S_LINES:
            if key in pins and (line(pins[key]) != "nc" or key not in bus):
                bus[key] = line(pins[key])
        for key in ("clk", "dout2"):
            if key in pins:
                bus[key] = line(pins[key])
        if "pdm" in str(item.get("format")) and "clk" not in bus and "bclk" not in bus:
            bus["clk"] = "nc"
        for key in pins:
            if key not in (*I2S_LINES, "clk", "dout2"):
                self.run.no_place[f"i2s.pins.{key}"] += 1
        self.names[name] = f"i2s.{own}"
        self.rates[name] = config.get("sample_rate_hz")

    def peripheral_uart(self, name, _item, config):
        own = f"uart{config.get('uart_num', 0)}"
        self.buses.setdefault("uart", {})[own] = {key: line(config.get(f"{key}_io_num")) for key in ("tx", "rx", "rts", "cts")}
        self.names[name] = f"uart.{own}"

    def peripheral_dsi(self, name, _item, config):
        own = f"dsi{config.get('bus_id', 0)}"
        self.buses.setdefault("dsi", {})[own] = given({"lanes": config.get("data_lanes"), "lane_mbps": config.get("lane_bit_rate_mbps")})
        self.names[name] = f"dsi.{own}"

    def bus_of(self, parts, kinds):
        """The first bus of these kinds a device names, and the entry that names it."""
        for part in parts:
            for key in ("i2c_name", "spi_name", "i2s_name", "dsi_name", "name"):
                bus = self.names.get(part.get(key))
                if bus and bus.split(".")[0] in kinds:
                    return bus, part
        return None, None

    def gpio_of(self, parts):
        for part in parts:
            config = self.of_type["gpio"].get(part.get("gpio_name") or part.get("name"))
            if config:
                return config
        return {}

    def gpio_of_adc(self, config):
        pins = json.loads((ROOT / "catalog" / "mcu" / self.target / "mcu.json").read_text())["gpio"]["pins"]
        unit, channel = re.search(r"(\d)$", str(config.get("unit_id"))), re.search(r"(\d+)$", str(config.get("channel_id")))
        wanted = f"ADC{unit[1] if unit else 1}_CH{channel[1] if channel else 0}"
        found = [int(pin) for pin, about in pins.items() if wanted in json.dumps(about)]
        if not found:
            self.run.no_place[f"adc channel with no pin: {self.target} {wanted}"] += 1
            return "nc"
        return found[0]

    def read_devices(self):
        for item in self.listed:
            kind, parts = item.get("type"), [part for part in item.get("peripherals") or [] if isinstance(part, dict)]
            if self.same_codec(item, parts):
                continue
            chip = item.get("chip")
            chip = word(chip) if chip and chip not in NOT_A_CHIP else None
            name = word(item.get("name"))
            device = {}
            reader = getattr(self, f"device_{kind}", None)
            if not reader:
                self.run.no_place[f"type {kind}"] += 1
                continue
            chip = reader(name, device, item, item.get("config") or {}, chip, parts)
            if device.pop("skip", False):
                continue
            if item.get("depends_on"):
                after = item["depends_on"] if isinstance(item["depends_on"], list) else [item["depends_on"]]
                device["start"] = {"after": [word(other) for other in after]}
            if chip:
                device["chip"] = chip
                for library in (item.get("dependencies") or {}):
                    if library != "idf":
                        self.run.libraries[library].add(chip)
            self.devices[name] = device

    def same_codec(self, item, parts):
        """Two entries of one codec chip, one for each direction: the second joins the first."""
        if item.get("type") != "audio_codec" or item.get("chip") in (*NOT_A_CHIP, None):
            return False
        reach = next((part.get("address", part.get("i2c_addr")) for part in parts if part.get("address") is not None or part.get("i2c_addr") is not None), None)
        twin = self.codecs.get((item["chip"], str(reach)))
        if twin is None:
            self.codecs[(item["chip"], str(reach))] = word(item.get("name"))
            return False
        first = self.devices[twin]
        for part in parts:
            bus = self.names.get(part.get("i2s_name") or part.get("name"))
            if bus and bus.startswith("i2s"):
                first["on"].setdefault(bus, {})
        first["config"]["direction"] = "both"
        self.merged[word(item.get("name"))] = twin
        self.run.no_place["one codec chip is two devices there"] += 1
        return True

    def device_display_lcd(self, name, device, item, config, chip, _parts):
        device["class"] = "display"
        io, panel = config.get("io_spi_config") or {}, config.get("lcd_panel_config") or {}
        sub = item.get("sub_type")
        bus, _ = self.bus_of(_parts, {"spi": ("spi", "qspi"), "dsi": ("dsi",)}.get(sub, ()))
        device["on"] = {}
        if bus:
            device["on"][bus] = {}
            if bus.split(".")[0] in ("spi", "qspi"):
                device["on"][bus] = given({"cs": line(io.get("cs_gpio_num")), "hz": io.get("pclk_hz") if isinstance(io.get("pclk_hz"), int) else None, "mode": io.get("spi_mode") if io.get("spi_mode") in (0, 1, 2, 3) else None})
                if (io.get("flags") or {}).get("sio_mode"):
                    device["on"][bus]["sio"] = True
        elif sub in ("rgb", "rgb_3wire_spi"):
            self.rgb(name, device, config, sub)
        elif sub == "i80":
            self.parallel(name, device, config)
        elif sub == "parlio":
            pins = config.get("io_parl_config") or {}
            self.buses.setdefault("parlio", {})[name] = {"clk": line(pins.get("clk_gpio_num")), "dc": line(pins.get("dc_gpio_num")), **{f"d{at}": line(pin) for at, pin in enumerate(pins.get("data_gpio_nums") or []) if line(pin) != "nc"}}
            device["on"][f"parlio.{name}"] = {"cs": line(pins.get("cs_gpio_num"))}
        device["pins"] = wired({"dc": io.get("dc_gpio_num"), "rst": panel.get("reset_gpio_num", config.get("reset_gpio_num"))})
        video = (config.get("dpi_config") or {}).get("video_timing") if isinstance(config.get("dpi_config"), dict) else None
        rgb = (config.get("rgb_panel_config") or {}).get("timings") or {}
        size = given({"width": config.get("x_max") or rgb.get("h_res") or (video or {}).get("h_size"), "height": config.get("y_max") or rgb.get("v_res") or (video or {}).get("v_size")})
        device["config"] = {"kind": "graphics", "panel": size, "primary": self.lcd is None}
        depth = config.get("bits_per_pixel") or panel.get("bits_per_pixel")
        if depth:
            device["config"]["depth_bits"] = depth
        device["controls"] = {"orientation": orientation(config)}
        if "invert_color" in config:
            device["config"]["invert"] = bool(config["invert_color"])
        order = str(config.get("rgb_ele_order") or panel.get("rgb_ele_order") or "").lower()
        if order:
            device["config"]["color_order"] = "bgr" if "bgr" in order else "rgb"
        if (config.get("reset_active_high") or (panel.get("flags") or {}).get("reset_active_high")) and "rst" in device["pins"]:
            device["pins"]["rst"] = {"gpio": device["pins"]["rst"], "active": "high"}
        if rgb:
            self.rgb_timing(device, rgb)
        if video:
            self.run.no_place["display: DSI timings, measured on a board and not taken from a pack"] += 1
        if chip:
            self.run.chip(chip, "display", [bus.split(".")[0]] if bus else [])
        self.lcd = self.lcd or name
        return chip

    def rgb(self, name, device, config, sub):
        panel = config.get("rgb_panel_config") or {}
        self.buses.setdefault("rgb", {})[name] = {"de": line(panel.get("de_gpio_num")), "vsync": line(panel.get("vsync_gpio_num")), "hsync": line(panel.get("hsync_gpio_num")),
                                                  "pclk": line(panel.get("pclk_gpio_num")), "data": [line(pin) for pin in panel.get("data_gpio_nums") or []]}
        pixel_clock = (panel.get("timings") or {}).get("pclk_hz")
        if pixel_clock:
            self.buses["rgb"][name]["hz"] = pixel_clock
        device["on"][f"rgb.{name}"] = {}
        if sub == "rgb_3wire_spi":
            three = config.get("io_3wire_spi_config") or {}
            lines = three.get("line_config") or {}
            wire = {}
            for pin, gpio_key, expander_key in (("cs", "cs_gpio_num", "cs_expander_pin"), ("scl", "scl_gpio_num", "scl_expander_pin"), ("sda", "sda_gpio_num", "sda_expander_pin")):
                if "EXPANDER" in str(lines.get(f"{pin}_io_type")):
                    bit = re.search(r"(\d+)$", str(lines[expander_key]))
                    wire[pin] = {"via": word(three.get("io_expander_name")), "bit": int(bit[1]) if bit else 0}
                elif lines.get(gpio_key) is not None:
                    wire[pin] = line(lines[gpio_key])
            self.buses.setdefault("spi", {})["soft0"] = {"mosi": wire.get("sda", "nc"), "miso": "nc", "sclk": wire.get("scl", "nc")}
            device["on"][f"rgb.{name}"] = {"role": "data"}
            device["on"]["spi.soft0"] = {"role": "control", "cs": wire.get("cs", "nc")}

    def parallel(self, name, device, config):
        bus, io = config.get("bus_config") or {}, config.get("io_config") or {}
        data = bus.get("data_gpio_nums") or []
        if len(data) > 8:
            self.run.no_place["display.i80 of 16 bits"] += 1
        self.buses.setdefault("p8", {})[name] = given({**{f"d{at}": line(pin) for at, pin in enumerate(data[:8])}, "wr": line(bus.get("wr_gpio_num")), "dc": line(bus.get("dc_gpio_num")), "hz": io.get("pclk_hz")})
        device["on"][f"p8.{name}"] = {"cs": line(io.get("cs_gpio_num"))}

    @staticmethod
    def rgb_timing(device, timing):
        device["config"]["timing"] = {"pclk_hz": timing.get("pclk_hz"), "hsync_pulse": timing["hsync_pulse_width"], "hsync_back": timing["hsync_back_porch"], "hsync_front": timing["hsync_front_porch"],
                                      "vsync_pulse": timing["vsync_pulse_width"], "vsync_back": timing["vsync_back_porch"], "vsync_front": timing["vsync_front_porch"]}
        if (timing.get("flags") or {}).get("pclk_active_neg"):
            device["config"]["timing"]["pclk_edge"] = "falling"

    def device_lcd_touch(self, _name, device, item, config, chip, parts):
        touch = config.get("touch_config") or {}
        device["class"] = "touch"
        bus, part = self.bus_of(parts, ("i2c",) if item.get("sub_type") == "i2c" else ("spi",))
        device["on"] = {bus: given({"address": address(part.get("i2c_addr"))})} if bus else {}
        device["pins"] = wired({"int": touch.get("int_gpio_num"), "rst": touch.get("rst_gpio_num")})
        levels = touch.get("levels") or {}
        for pin, level in (("int", "interrupt"), ("rst", "reset")):
            if pin in device["pins"] and level in levels:
                device["pins"][pin] = {"gpio": device["pins"][pin], "active": "high" if levels[level] else "low"}
        if touch.get("flags"):
            device["controls"] = {"orientation": orientation(touch["flags"])}
        device["config"] = given({"over": self.lcd or "none", "x_max": touch.get("x_max"), "y_max": touch.get("y_max")})
        if chip:
            self.run.chip(chip, "touch", [bus.split(".")[0]] if bus else [])
        if item.get("chip") == "auto":
            tries = sorted({word(key.rsplit("_", 1)[-1]) for key in item.get("dependencies") or {} if re.search(r"touch_[a-z]+\d", key)})
            for other in tries:
                self.run.chip(other, "touch", ["i2c"])
            device["chip_try"] = tries
        return chip

    def device_audio_codec(self, _name, device, _item, config, chip, parts):
        chip = chip or self.generic_audio(config, parts)
        device["class"] = "audio"
        device["on"] = {}
        for part in parts:
            reference = part.get("i2s_name") or part.get("i2c_name") or part.get("name")
            bus = self.names.get(reference)
            if bus and bus.startswith("i2s"):
                form = str(self.peripherals.get(reference, {}).get("format") or "std").split("-")[0]
                device["on"][bus] = {} if form == "std" else {"format": form}
                self.rate = self.rates.get(reference) or self.rate
            elif bus and bus.startswith("i2c"):
                device["on"][bus] = given({"address": address(part.get("address", part.get("i2c_addr")))})
            elif reference in self.of_type["gpio"]:
                device.setdefault("pins", {})["pa"] = line(self.of_type["gpio"][reference].get("pin"))
            elif reference in self.of_type["adc"]:
                device.setdefault("pins", {})["in"] = self.gpio_of_adc(self.of_type["adc"][reference])
            elif reference is not None and "dac" in str(reference):
                self.run.no_place["audio on the internal DAC"] += 1
        both, heard = config.get("adc_enabled") and config.get("dac_enabled"), config.get("adc_enabled")
        device["config"] = given({"direction": "both" if both else "in" if heard else "out", "sample_rate": self.rate})
        system = config.get("sys_cfg")
        if isinstance(system, dict):
            if "pa_pin" in system:
                device.setdefault("pins", {})["pa"] = line(system.get("pa_pin"))
            if system.get("no_mclk"):
                device["config"]["clock"] = "bclk"
        if chip:
            self.run.chip(chip, "audio", [bus.split(".")[0] for bus in device["on"]])
        return chip

    def generic_audio(self, config, parts):
        forms = {f"{item.get('type')}:{item.get('format')}" for item in (self.peripherals.get(part.get("i2s_name") or part.get("adc_name") or part.get("name")) or {} for part in parts)}
        chip = next((name for form, name in GENERIC_AUDIO if form in forms), None)
        if not chip and config.get("adc_local_cfg"):
            chip = "adc_mic"
        if not chip and config.get("dac_enabled"):
            out = next((name for name, item in self.peripherals.items() if item.get("format") == "pdm-out"), None)
            if out:
                parts.append({"name": out})
                chip = "pdm_out"
        if chip:
            self.run.no_place["audio with no codec: a generic end of the bus"] += 1
        return chip

    def device_button(self, name, device, item, config, _chip, parts):
        device["class"] = "button"
        if item.get("sub_type") == "adc_multi":
            self.ladder(name, config, parts)
            device["skip"] = True
            return None
        gpio = self.gpio_of(parts)
        level = config.get("active_level", next((part.get("active_level") for part in parts if "active_level" in part), 0))
        pin = line(gpio.get("pin", config.get("gpio_num")))
        device["pins"] = {"in": "nc" if pin == "nc" else {"gpio": pin, "active": "high" if level else "low"}}
        return None

    def ladder(self, name, config, parts):
        """Several buttons on one line: each gets the window halfway to its neighbours."""
        channel = next((self.of_type["adc"][part.get("adc_name")] for part in parts if part.get("adc_name") in self.of_type["adc"]), {})
        pin = self.gpio_of_adc(channel)
        labels, volts = config.get("button_labels"), config.get("voltage_range")
        if not isinstance(volts, list) or not isinstance(labels, list):
            self.run.no_place["button.adc_multi of another form"] += 1
            return
        top = config.get("max_voltage")
        for at, label in enumerate(labels):
            low = ((volts[at - 1] if at else 0) + volts[at]) // 2
            high = (volts[at] + (volts[at + 1] if at + 1 < len(volts) else top)) // 2 if at + 1 < len(volts) or top else None
            if high is None:
                self.run.no_place["button.adc_multi with no top of the range"] += 1
                continue
            self.devices[f"{name}_{word(label)}"] = {"class": "button", "pins": {"in": {"gpio": pin, "analog": [low, high]}}}

    def device_led_strip(self, _name, device, _item, config, chip, _parts):
        device["class"] = "led"
        device["pins"] = wired({"data": config.get("strip_gpio_num")})
        device["config"] = given({"kind": chip or "strip", "count": config.get("max_leds")})

    def device_gpio_ctrl(self, name, device, _item, _config, _chip, parts):
        device["class"] = "led" if "led" in name else "other"
        device["pins"] = wired({"out": self.gpio_of(parts).get("pin")})

    def device_ledc_ctrl(self, name, device, _item, config, _chip, parts):
        ledc = next((self.of_type["ledc"][part.get("ledc_name") or part.get("name")] for part in parts if (part.get("ledc_name") or part.get("name")) in self.of_type["ledc"]), {})
        display = self.devices.get(self.lcd) if self.lcd else None
        if display is not None and ("backlight" in name or "brightness" in name):
            display.setdefault("pins", {})["backlight"] = line(ledc.get("gpio_num"))
            display.setdefault("controls", {})["backlight"] = given({"how": "backlight_pwm", "min": 0, "max": 100, "start": config.get("default_percent")})
            device["skip"] = True
            return
        device["class"] = "other"
        device["pins"] = wired({"out": ledc.get("gpio_num")})

    def device_power_ctrl(self, _name, device, item, config, _chip, parts):
        if item.get("sub_type") == "gpio":
            part = parts[0] if parts else {}
            feeds = [word(other.get("name")) for other in self.listed if other.get("power_ctrl_device") == item.get("name")]
            self.power.append({"line": line(self.of_type["gpio"].get(part.get("gpio_name"), {}).get("pin")), "level": int(part.get("active_level", 1)), "feeds": feeds})
            device["skip"] = True
            return
        device["class"] = "pmic"
        bus, _ = self.bus_of(parts, ("i2c",))
        reach = address(config.get("i2c_addr"))
        device["on"] = {bus: {"address": reach}} if bus and reach else {}

    def device_fs_fat(self, _name, device, item, config, _chip, parts):
        device["class"] = "storage"
        device["config"] = {"media": "microsd"}
        sub = config.get("sub_config") or {}
        if item.get("sub_type") == "sdmmc":
            pins = wired(sub.get("pins") or {})
            if "SLOT_0" in str(sub.get("slot")):  # that slot has its pins in the IO MUX, and a pack writes them all as 0
                self.run.no_place["sdmmc slot 0: its pins are fixed, the pack gives none"] += 1
                pins = {}
            self.buses.setdefault("sdmmc", {})["sdmmc0"] = pins
            device["on"] = {"sdmmc.sdmmc0": {}}
        else:
            bus, _ = self.bus_of(parts, ("spi",))
            device["on"] = {bus: {"cs": line(sub.get("cs_gpio_num", sub.get("gpio_cs")))}} if bus else {}

    def device_fs_spiffs(self, _name, device, _item, _config, _chip, _parts):
        self.run.no_place["spiffs: a file system, no device"] += 1
        device["skip"] = True

    def device_gpio_expander(self, _name, device, _item, config, chip, parts):
        device["class"] = "io_expander"
        bus, part = self.bus_of(parts, ("i2c",))
        reach = address(part.get("i2c_addr")) if part else None
        device["on"] = {bus: {"address": reach}} if bus and reach else {}
        device["config"] = given({"pins": config.get("max_pins")})
        if chip:
            self.run.chip(chip, "io_expander", ["i2c"])
        return chip

    def device_knob(self, _name, device, _item, config, _chip, _parts):
        device["class"] = "encoder"
        device["pins"] = wired({"a": config.get("gpio_encoder_a"), "b": config.get("gpio_encoder_b")})

    def device_camera(self, _name, device, item, config, _chip, parts):
        device["class"] = "camera"
        bus, _ = self.bus_of(parts, ("i2c",))
        device["on"] = {bus: {"role": "control"}} if bus else {}
        sub = item.get("sub_type")
        if sub == "dvp":
            dvp = config.get("dvp_config") or {}
            self.buses.setdefault("dvp", {})["cam"] = {"pclk": line(dvp.get("pclk_io")), "vsync": line(dvp.get("vsync_io")), "de": line(dvp.get("de_io")), "data": [line(pin) for pin in (dvp.get("data_io") or {}).values() if line(pin) != "nc"]}
            device["on"]["dvp.cam"] = {"role": "data"}
            device["pins"] = wired({"xclk": dvp.get("xclk_io"), "rst": dvp.get("reset_io"), "pwdn": dvp.get("pwdn_io")})
            device["config"] = given({"xclk_hz": dvp.get("xclk_freq") or None})
        elif sub == "csi":
            csi = config.get("csi_config") or {}
            clock = csi.get("xclk_config") or {}
            bus = given({"lanes": csi.get("data_lanes")})
            for ldo in self.of_type["ldo"].values():
                bus.update(given({"phy_ldo_chan": ldo.get("chan_id"), "phy_ldo_mv": ldo.get("voltage_mv")}))
            self.buses.setdefault("csi", {})["csi0"] = bus
            device["on"]["csi.csi0"] = {"role": "data"}
            device["pins"] = wired({"xclk": clock.get("xclk_pin"), "rst": csi.get("reset_io"), "pwdn": csi.get("pwdn_io")})
            device["config"] = given({"xclk_hz": clock.get("xclk_freq_hz") or None})
        else:
            spi = config.get("spi_config") or {}
            own = f"spi{int(spi.get('spi_port', 1)) + 1}"
            self.buses.setdefault("spi", {})[own] = {"mosi": line(spi.get("spi_data0_io_pin")), "miso": "nc", "sclk": line(spi.get("spi_sclk_pin"))}
            device["on"][f"spi.{own}"] = {"role": "data", "cs": line(spi.get("spi_cs_pin"))}
            device["pins"] = wired({"xclk": spi.get("xclk_pin")})

    def device_ethernet(self, _name, device, item, config, chip, _parts):
        device["class"] = "network"
        device["provides"] = {"ethernet": {}}
        data, management = config.get("dataif_gpio") or {}, config.get("smi_gpio") or {}
        lines = {key.replace("_num", ""): line(value) for key, value in {**data, **management}.items()}
        lines["ref_clk"] = line((config.get("clock_config") or {}).get("clock_gpio"))
        bus = item.get("sub_type", "").split("_")[-1]
        self.buses.setdefault(bus, {})["eth0"] = lines
        device["on"] = {f"{bus}.eth0": {}}
        device["pins"] = wired({"rst": (config.get("phy_config") or {}).get("reset_gpio_num")})
        if chip:
            self.run.chip(chip, "network")
        return chip

    def device_custom(self, _name, device, item, config, chip, parts):
        """Described by C code in the pack: only what its config says of the wires comes over."""
        kind = CUSTOM_CLASS.get(item.get("chip"), "other")
        self.run.no_place["custom: described by C code in the pack"] += 1
        if chip and kind in ("display", "touch", "audio"):
            self.run.no_place[f"custom {kind}, kept as other"] += 1
            kind = "other"
        device["class"] = kind
        if chip:
            self.run.chip(chip, kind)
        if item.get("chip") == "lr1121":
            references = [part.get("name") for part in parts]
            bus = next((self.names[name] for name in references if name in self.names), None)
            pins = {name: self.of_type["gpio"][name].get("pin") for name in references if name in self.of_type["gpio"]}
            found = lambda word_of: next((pin for name, pin in pins.items() if word_of in name), None)
            if bus:
                device["on"] = {bus: given({"cs": line(found("cs")), "hz": config.get("clock_hz"), "mode": config.get("mode")})}
            device["pins"] = wired({"irq": found("irq"), "rst": found("reset")})
        if item.get("chip") == "xpt2046":
            bus = self.names.get(config.get("bus_name"))
            io = config.get("io_spi_config") or {}
            if bus:
                device["on"] = {bus: given({"cs": line(io.get("cs_gpio_num")), "hz": io.get("pclk_hz")})}
        return chip

    def join_brightness(self):
        """A brightness listed before its display is its backlight all the same."""
        display = next((device for device in self.devices.values() if device.get("class") == "display"), None)
        brightness = self.devices.get("lcd_brightness")
        if display is not None and brightness and "out" in brightness.get("pins", {}):
            display.setdefault("pins", {})["backlight"] = brightness["pins"]["out"]
            del self.devices["lcd_brightness"]

    def document(self, name, title, origin):
        self.read_peripherals()
        self.read_devices()
        self.join_brightness()
        doc = {**HEAD, "kind": "board", "name": name, "title": title, "mcu": {"target": self.target}, "buses": self.buses, "devices": self.devices, "origin": origin,
               "checked": {"pack": {"level": LEVEL, "source": f"{origin['from']} {origin.get('ref', '')}".strip()}}}
        if self.power:
            for step in self.power:
                step["feeds"] = sorted({self.merged.get(name, name) for name in step["feeds"]})
            doc["power"] = self.power
        return doc


def pins_of_pack(devices, peripherals):
    """Every GPIO a pack names, with who names it: for the comparison with a board of the catalog."""
    found = collections.defaultdict(list)

    def add(pin, who):
        if isinstance(pin, int) and pin >= 0:
            found[pin].append(who)

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, int) and re.search(r"(gpio_num|_gpio|_io|_io_num|^pin|^gpio_num)$", key):
                    add(value, f"{path}.{key}")
                elif key == "pins" and isinstance(value, dict):
                    for pin_name, pin in value.items():
                        add(pin, f"{path}.{pin_name}")
                else:
                    walk(value, path)

    for item in (*(peripherals.get("peripherals") or []), *(devices.get("devices") or [])):
        if isinstance(item, dict):
            walk(item.get("config") or {}, item.get("name"))
    return found


def compared(ours, devices, peripherals):
    """The pins of a board of the catalog against a pack: what differs, for a person to check on the board."""
    board = next(item for item in boards_gen.read_all(ROOT / "catalog")[0] if item["name"] == ours)
    mine = {pin: entry["owners"] for pin, entry in boards_gen.pin_map(board).items() if entry["owners"]}
    theirs = pins_of_pack(devices, peripherals)
    return [f"GPIO {pin}: pack {theirs.get(pin, 'nothing')}, catalog {mine.get(pin, 'free')}" for pin in sorted({*theirs, *mine})]


def checked(doc, raw, whole, found_rules):
    """What keeps a board out, each reason a line. It stops at the first stage that refuses."""
    errors = [error for error in raw.iter_errors(doc)]
    plain_errors = [error for error in errors if error.validator != "unevaluatedProperties"] or errors  # the root repeats what failed below it
    if plain_errors:
        return [f"schema {'/'.join(str(part) for part in error.path)}: {error.message[:120]}" for error in plain_errors]
    try:
        resolved = resolve.resolve(copy.deepcopy(doc))  # it fills the document in
    except resolve.Refused as error:
        return [f"resolve: {error}"]
    problems = [f"resolved {'/'.join(str(part) for part in error.path)}: {error.message[:120]}" for error in whole.iter_errors(resolved)]
    problems += [f"rule {item['rule']}: {item['message']}" for item in rules.check(resolved, found_rules)]
    numbers = {kind: {own: {key: boards_gen.number(value) for key, value in bus.items()} for own, bus in named.items()} for kind, named in (resolved.get("buses") or {}).items()}
    return problems or boards_gen.pin_problems({**resolved, "buses": numbers})


def validators():
    """The schema of a file, the schema of a resolved board, the rules."""
    whole = jsonschema.Draft202012Validator({"$ref": "#/$defs/resolved", "$defs": SCHEMA["$defs"]})
    return jsonschema.Draft202012Validator(SCHEMA), whole, json.loads((ROOT / "catalog" / "rules.json").read_text())


def write_index(out):
    """The files of the tree for the page: a server gives no listing to rely on."""
    paths = sorted(path.relative_to(out).as_posix() for kind in ("boards", "modules", "devices") if (out / kind).exists() for path in (out / kind).rglob("*.json"))
    (out / "index.json").write_text(resolve.dump(paths) + "\n")


def write_documents(out, kind, file_name, documents):
    target = out / kind
    if target.exists():
        shutil.rmtree(target)
    for name, doc in documents.items():
        path = target / name / file_name
        path.parent.mkdir(parents=True)
        path.write_text(resolve.dump(doc) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packs", nargs="+", help="NAME=DIR of a pack as unpacked from the registry")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "imported")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()

    run = Import()
    raw, whole, found_rules = validators()
    docs, sources, differ = {}, {}, {}
    licenses = args.out / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    for pack in args.packs:
        pack_name, _, folder = pack.partition("=")
        folder = pathlib.Path(folder)
        manifest = read_yaml(folder / "idf_component.yml")
        version = str(manifest.get("version", ""))
        for file_name in ("LICENSE", "NOTICE"):
            if (folder / file_name).exists():
                shutil.copyfile(folder / file_name, licenses / f"{pack_name}.{file_name}")
        license_text = (folder / "LICENSE").read_text(errors="ignore").strip().split("\n")[0].strip() if (folder / "LICENSE").exists() else ""
        sources[pack_name] = given({"version": version, "url": manifest.get("repository"), "license": manifest.get("license") or license_text})
        for path in sorted(folder.rglob("board_devices.yaml")):
            where = path.parent
            key = f"{pack_name}/{where.name}"
            devices, peripherals, info = read_yaml(path), read_yaml(where / "board_peripherals.yaml"), read_yaml(where / "board_info.yaml")
            if key in OURS:
                differ[OURS[key]] = compared(OURS[key], devices, peripherals)
                continue
            name = word(key.replace("/", "_"))
            origin = {"from": pack_name, "ref": version, "path": str(where.relative_to(folder)), "license": sources[pack_name].get("license", ""), "tool": TOOL, "date": args.date}
            docs[name] = Board(run, info, devices, peripherals).document(name, info.get("description") or name, origin)

    write_documents(args.out, "devices", "device.json", run.chips)
    resolve.ROOTS.insert(0, args.out)
    refused = {}
    for name, doc in docs.items():
        problems = checked(doc, raw, whole, found_rules)
        if problems:
            refused[name] = problems
    taken = {name: doc for name, doc in docs.items() if name not in refused}
    write_documents(args.out, "boards", "board.json", taken)
    report = {"date": args.date, "sources": sources, "boards": len(taken), "chips": len(run.chips), "refused": refused, "differ_from_the_catalog": differ,
              "no_place": dict(run.no_place.most_common()), "libraries": {name: sorted(chips) for name, chips in sorted(run.libraries.items())}}
    (args.out / "report.json").write_text(resolve.dump(report) + "\n")
    write_index(args.out)
    print(f"{len(taken)} boards taken, {len(refused)} refused, {len(differ)} compared with the catalog, {len(run.chips)} chips with no entry of their own")
    return 0


if __name__ == "__main__":
    sys.exit(main())
