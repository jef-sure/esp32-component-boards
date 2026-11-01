#!/usr/bin/env python3
"""
Writes catalog/mcu/<target>/mcu.json from soc_caps.h of ESP-IDF, so the facts of a chip are not
typed by hand. Strapping pins and the pins of flash and PSRAM are not in those headers.
"""
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IDF = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.espressif/v6.1/esp-idf"))
PROVIDES = {"SOC_WIFI_SUPPORTED": "wifi", "SOC_BT_SUPPORTED": "bluetooth", "SOC_DAC_SUPPORTED": "dac", "SOC_USB_OTG_SUPPORTED": "usb_otg",
            "SOC_MIPI_DSI_SUPPORTED": "mipi_dsi", "SOC_LCD_RGB_SUPPORTED": "lcd_rgb", "SOC_EMAC_SUPPORTED": "emac",
            "SOC_SDMMC_HOST_SUPPORTED": "sdmmc", "SOC_TOUCH_SENSOR_SUPPORTED": "touch_pads", "SOC_TWAI_SUPPORTED": "twai"}
# the datasheets of these chips, DC characteristics: VIH is at most VDD + 0.3 V, here at a VDD of 3.3 V
GPIO_HIGH_MV_MAX = {target: 3600 for target in ("esp32", "esp32s2", "esp32s3", "esp32c3", "esp32c5", "esp32c6", "esp32h2", "esp32p4", "esp32s31")}
# esp_wifi.h: the unit of esp_wifi_set_max_tx_power() is 0.25 dBm, the range 8 to 84, after esp_wifi_start()
WIFI_TX_POWER = {"how": "wifi_tx_power", "min": 8, "max": 84, "unit": "0.25 dBm", "read": "command"}


def defines(path):
    found = {}
    for line in path.read_text().splitlines():
        match = re.match(r"#define\s+(SOC_\w+)\s+(.+?)\s*(/\*.*|//.*)?$", line)
        if match:
            found[match[1]] = match[2]
    return found


def number(text, found, depth=0):
    if text is None or depth > 4:
        return None
    text = re.sub(r"\bBIT(\d+)\b", lambda m: f"(1<<{m[1]})", text)
    text = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[UL]+\b", r"\1", text)
    for name in set(re.findall(r"\bSOC_\w+\b", text)):
        value = number(found.get(name), found, depth + 1)
        if value is None:
            return None
        text = re.sub(rf"\b{name}\b", str(value), text)
    if not re.fullmatch(r"[\s0-9a-fA-FxX()|&~<+*-]*", text):
        return None
    return eval(text)  # a constant expression of the headers of ESP-IDF, checked by the line above


def bits(mask, count):
    return [n for n in range(count) if mask >> n & 1]


def speeds(path, symbol):
    """The speeds a Kconfig offers, each with what it depends on."""
    if not path.exists():
        return []
    blocks = re.findall(rf"config {symbol}(\d+)M?\b[^\n]*\n((?:[ \t]+(?!config\b)\S[^\n]*\n)*)", path.read_text())
    return [(int(mhz), block) for mhz, block in blocks if "FPGA" not in block]


def limits_of(target):
    """The largest speeds of a chip and, when revisions of it differ, those of the older ones."""
    limits, older = {}, {}
    for name, path, symbol in (("psram_mhz", IDF / f"components/esp_psram/{target}/Kconfig.spiram", "SPIRAM_SPEED_"),
                               ("cpu_mhz", IDF / f"components/esp_system/port/soc/{target}/Kconfig.cpu", "ESP_DEFAULT_CPU_FREQ_MHZ_")):
        found = speeds(path, symbol)
        if found:
            limits[name] = max(mhz for mhz, block in found if not re.search(r"depends on [^\n!]*_SELECTS_REV_LESS_V3", block))
            low = max(mhz for mhz, block in found if not re.search(r"!\w*_SELECTS_REV_LESS_V3", block))
            # a Kconfig may leave a faster choice open and name the speed of the older chips as their default
            default = re.search(rf"default {symbol}(\d+)M? if \w*_SELECTS_REV_LESS_V3", path.read_text())
            low = int(default[1]) if default else low
            if low != limits[name]:
                older[name] = low
    return limits, older


def pin_table(target):
    """What each GPIO can do, and what the notes under the table say, from the documentation of ESP-IDF."""
    path = IDF / f"docs/en/api-reference/peripherals/gpio/{target}.inc"
    if not path.exists():
        return {}, []
    text = path.read_text()
    pins = {}
    for pin, analog, low_power, comments in re.findall(r"\* - GPIO(\d+)\n\s+-([^\n]*)\n\s+-([^\n]*)\n\s+-([^\n]*)", text):
        entry = {"analog": [part.strip() for part in analog.split(",") if part.strip()], "low_power": low_power.strip(),
                 "notes": [part.strip() for part in comments.split(";") if part.strip()]}
        entry = {key: value for key, value in entry.items() if value}
        if entry:
            pins[pin] = entry
    block = re.search(r"\.\. note::\n\n((?:[ \t]+[^\n]*\n)+)", text)
    notes = [re.sub(r"`([^`<]*?)\s*<[^>]*>`_*", r"\1", line.strip()[2:]) for line in (block[1] if block else "").splitlines() if line.strip().startswith("- ")]
    return pins, notes


def main():
    made = []
    for target_dir in sorted((IDF / "components/soc").glob("esp32*")):
        target = target_dir.name
        caps = next((p for p in (target_dir / "include/soc/soc_caps.h", target_dir / "register/soc/soc_caps.h") if p.exists()), None)
        if caps is None:
            continue
        found = defines(caps)
        count = number(found.get("SOC_GPIO_PIN_COUNT"), found)
        valid = number(found.get("SOC_GPIO_VALID_GPIO_MASK"), found)
        out = number(found.get("SOC_GPIO_VALID_OUTPUT_GPIO_MASK"), found)
        if None in (count, valid, out):
            print(f"{target}: skipped, a mask does not parse", file=sys.stderr)
            continue
        entry = {"format": "jef-sure/boards", "format_version": 2, "kind": "mcu", "name": target, "title": target.upper().replace("ESP32", "ESP32-").rstrip("-"),
                 "gpio": {"count": count, "valid": bits(valid, 64), "input_only": bits(valid & ~out, 64)},
                 "hosts": {key: value for key, value in (("spi", number(found.get("SOC_SPI_PERIPH_NUM"), found)), ("i2c", number(found.get("SOC_I2C_NUM"), found)), ("uart", number(found.get("SOC_UART_HP_NUM") or found.get("SOC_UART_NUM"), found)), ("ledc", number(found.get("SOC_LEDC_CHANNEL_NUM"), found))) if value is not None},
                 "provides": {name: {} for symbol, name in PROVIDES.items() if found.get(symbol) == "1"},
                 "checked": {"facts": {"level": "vendor-docs", "source": f"ESP-IDF {IDF.name}, components/soc/{target}, soc_caps.h"}}}
        if target in GPIO_HIGH_MV_MAX:
            entry["gpio"]["high_mv_max"] = GPIO_HIGH_MV_MAX[target]
            entry["checked"]["levels"] = {"level": "datasheet", "covers": ["gpio.high_mv_max"], "source": "Espressif datasheet of the chip, DC characteristics: VIH at most VDD + 0.3 V, at VDD 3.3 V"}
        if "wifi" in entry["provides"]:
            entry["controls"] = {"wifi_tx_power": WIFI_TX_POWER}
        pins, notes = pin_table(target)
        if pins:
            entry["gpio"].update({"strapping": [int(pin) for pin, info in pins.items() if "Strapping pin" in info.get("notes", ())], "pins": pins, "notes": notes})
            entry["checked"]["pins"] = {"level": "vendor-docs", "covers": ["gpio.pins", "gpio.strapping"], "source": f"ESP-IDF {IDF.name}, docs/en/api-reference/peripherals/gpio/{target}.inc"}
        limits, older = limits_of(target)
        if limits:
            entry["limits"] = limits
        if older:
            # a chip below revision 3 takes less: Kconfig.spiram and Kconfig.cpu say so by ESP32P4_SELECTS_REV_LESS_V3
            kconfig = (IDF / f"components/esp_hw_support/port/{target}/Kconfig.hw_support").read_text()
            prefix = target.upper()
            entry["sdkconfig"] = {"revision": f"CONFIG_{prefix}_REV_MIN_{{value}}", "psram_mhz": "CONFIG_SPIRAM_SPEED_{value}M", "cpu_mhz": "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_{value}", "lines": []}
            entry["revisions"] = {"described": "3.99", "options": [int(n) for n in re.findall(rf"config {prefix}_REV_MIN_(\d+)\b", kconfig)],
                                  "history": [{"before": "3.0", "limits": older, "sdkconfig": {"lines": [f"CONFIG_{prefix}_SELECTS_REV_LESS_V3=y"]}}]}
        path = ROOT / "catalog/mcu" / target / "mcu.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry, indent=4) + "\n")
        made.append(target)
    print("mcu:", " ".join(made))


if __name__ == "__main__":
    main()
