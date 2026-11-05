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

import resolve

ROOT = pathlib.Path(__file__).resolve().parent.parent
IDF = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.espressif/v6.1/esp-idf"))
PROVIDES = {"SOC_WIFI_SUPPORTED": "wifi", "SOC_BT_SUPPORTED": "bluetooth", "SOC_BT_CLASSIC_SUPPORTED": "bluetooth_classic", "SOC_DAC_SUPPORTED": "dac", "SOC_USB_OTG_SUPPORTED": "usb_otg",
            "SOC_MIPI_DSI_SUPPORTED": "mipi_dsi", "SOC_LCD_RGB_SUPPORTED": "lcd_rgb", "SOC_EMAC_SUPPORTED": "emac",
            "SOC_SDMMC_HOST_SUPPORTED": "sdmmc", "SOC_TOUCH_SENSOR_SUPPORTED": "touch_pads", "SOC_TWAI_SUPPORTED": "twai"}
# What the driver of each source can change while it runs: its API, the same on every chip.
LEDC_CAN = ["frequency", "duty", "phase", "fade", "pause"]
MCPWM_CAN = ["frequency", "duty", "phase", "dead_time", "sync"]
RMT_CAN = ["carrier", "loop"]
# Module clocks that are not precise enough to count a frequency on: RC oscillators.
IMPRECISE_CLOCKS = {"RC_FAST", "RC_FAST_D256", "RTC_FAST", "RC_SLOW", "RC32K"}
# What was tried on a chip, not only read: the pair of pins of a source counts as unknown in a kit until it is here.
FREQUENCY_TRIED = {"esp32": {"ledc_pairs": {"level": "hardware", "covers": ["frequency_sources.ledc.pairs"], "by": "~/freecad/tc-eth-poe/piezo-test: two channels, one timer, hpoint half a period, antiphase read on the pins, four discs heard", "date": "2026-10-15"}},
                   "esp32p4": {"ledc_pairs": {"level": "hardware", "covers": ["frequency_sources.ledc.pairs"], "by": "Anton: tried in the project of the time clock on the ESP32-P4", "date": "2026-11-01", "notes": "The date is that of his word. The project went on on another machine, so the copy here does not have this code."}}}
# the datasheets of these chips, DC characteristics: VIH is at most VDD + 0.3 V, here at a VDD of 3.3 V
GPIO_HIGH_MV_MAX = {target: 3600 for target in ("esp32", "esp32s2", "esp32s3", "esp32c3", "esp32c5", "esp32c6", "esp32h2", "esp32p4", "esp32s31")}
# esp_wifi.h: the unit of esp_wifi_set_max_tx_power() is 0.25 dBm, the range 8 to 84, after esp_wifi_start()
WIFI_TX_POWER = {"how": "wifi_tx_power", "min": 8, "max": 84, "unit": "0.25 dBm", "read": "command"}


# The strapping pins of a chip as its datasheet of Espressif gives them ("Boot Configurations"), copied, not judged:
# the rows of its table of boot mode control (a level, or "any", for each pin of the mode) and, for each strapping pin,
# what it selects, its own pull at reset (None when it floats) and the footnote of the table when there is one. Which
# level harms what is the solver's to say (keep_out). MTMS, MTDI and MTDO are given as their GPIOs. The files lie in
# ~/dgx-bench/datasheets-espressif-2026-11-04/<chip>/; no header of ESP-IDF has this.
BOOT_MODE, FLASH_VOLTAGE, ROM_MESSAGES, SDIO_TIMING, JTAG_SOURCE = "boot mode", "flash voltage", "rom messages", "sdio timing", "jtag source"
DATASHEETS = "~/dgx-bench/datasheets-espressif-2026-11-04"
BOOT = {
    "esp32": ("esp32/esp32_datasheet_en_v5.3.pdf, Tables 3-1 and 3-3",
              {"spi_boot": {0: 1, 2: "any"}, "joint_download_boot": {0: 0, 2: 0}},
              {0: ([BOOT_MODE], "up"), 2: ([BOOT_MODE], "down"), 5: ([SDIO_TIMING], "up"), 12: ([FLASH_VOLTAGE], "down"), 15: ([ROM_MESSAGES, SDIO_TIMING], "up")}),
    "esp32s2": ("esp32s2/esp32-s2_datasheet_en_v1.9.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {0: 1, 46: "any"}, "joint_download_boot": {0: 0, 46: 0}},
                {0: ([BOOT_MODE], "up"), 45: ([FLASH_VOLTAGE], "down"), 46: ([BOOT_MODE, ROM_MESSAGES], "down")}),
    "esp32s3": ("esp32s3/esp32-s3_datasheet_en_v2.2.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {0: 1, 46: "any"}, "joint_download_boot": {0: 0, 46: 0}},
                {0: ([BOOT_MODE], "up"), 3: ([JTAG_SOURCE], None), 45: ([FLASH_VOLTAGE], "down"), 46: ([BOOT_MODE, ROM_MESSAGES], "down")}),
    "esp32c2": ("esp32c2/esp8684_datasheet_en_v2.3.pdf, Tables 10 and 12",
                {"spi_boot": {9: 1, 8: "any"}, "joint_download_boot": {9: 0, 8: 1}},
                {8: ([BOOT_MODE, ROM_MESSAGES], None), 9: ([BOOT_MODE], "up")}),
    "esp32c3": ("esp32c3/esp32-c3_datasheet_en_v2.4.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {2: 1, 8: "any", 9: 1}, "joint_download_boot": {2: 1, 8: 1, 9: 0}},
                {2: ([BOOT_MODE], None, "GPIO2 actually does not determine SPI Boot and Joint Download Boot mode, but it is recommended to pull this pin up due to glitches.", False),
                 8: ([BOOT_MODE, ROM_MESSAGES], None), 9: ([BOOT_MODE], "up")}),
    "esp32c5": ("esp32c5/esp32-c5_datasheet_en_v1.5.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {26: "any", 27: "any", 28: 1}, "joint_download_boot_0": {26: "any", 27: 1, 28: 0}, "joint_download_boot_1": {26: 0, 27: 0, 28: 0}},
                {2: ([SDIO_TIMING], None), 3: ([SDIO_TIMING], None), 7: ([JTAG_SOURCE], None), 25: ([SDIO_TIMING], None),
                 26: ([BOOT_MODE], None), 27: ([BOOT_MODE, ROM_MESSAGES], "up"), 28: ([BOOT_MODE], "up")}),
    "esp32c6": ("esp32c6/esp32-c6_datasheet_en_v1.5.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {8: "any", 9: 1}, "joint_download_boot": {8: 1, 9: 0}},
                {4: ([SDIO_TIMING], None), 5: ([SDIO_TIMING], None), 8: ([BOOT_MODE, ROM_MESSAGES], None), 9: ([BOOT_MODE], "up"), 15: ([JTAG_SOURCE], None)}),
    "esp32c61": ("esp32c61/esp32-c61_datasheet_en_v1.1.pdf, Tables 3-1 and 3-3",
                 {"spi_boot": {8: "any", 9: 1}, "joint_download_boot": {8: 1, 9: 0}},
                 {3: ([SDIO_TIMING], None), 4: ([SDIO_TIMING], None), 7: ([JTAG_SOURCE], None), 8: ([BOOT_MODE, ROM_MESSAGES], None), 9: ([BOOT_MODE], "up")}),
    "esp32h2": ("esp32h2/esp32-h2_datasheet_en_v1.3.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {8: "any", 9: 1}, "joint_download_boot": {8: 1, 9: 0}},
                {8: ([BOOT_MODE, ROM_MESSAGES], None), 9: ([BOOT_MODE], "up"), 25: ([JTAG_SOURCE], None)}),
    "esp32p4": ("esp32p4/esp32-p4_datasheet_en_v0.7.pdf, Tables 3-1 and 3-3",
                {"spi_boot": {35: 1, 36: "any", 37: "any", 38: "any"}, "joint_download_boot": {35: 0, 36: 1, 37: "any", 38: "any"}},
                {34: ([JTAG_SOURCE], None), 35: ([BOOT_MODE], "up"), 36: ([BOOT_MODE, ROM_MESSAGES], None),
                 37: ([BOOT_MODE], None, "For details about the functionalities of GPIO37 and GPIO38, see ESP32-P4 Technical Reference Manual > Chapter Chip Boot Control."),
                 38: ([BOOT_MODE], None, "For details about the functionalities of GPIO37 and GPIO38, see ESP32-P4 Technical Reference Manual > Chapter Chip Boot Control.")}),
    "esp32s31": ("esp32s31/esp32-s31_datasheet_en_v0.5.pdf, Tables 3-1 and 3-3",
                 {"spi_boot": {61: 1, 60: "any"}, "joint_download_boot": {61: 0, 60: 1}, "invalid_combination": {61: 0, 60: 0}},
                 {36: ([FLASH_VOLTAGE], None), 37: ([JTAG_SOURCE], None), 60: ([BOOT_MODE, ROM_MESSAGES], "up"), 61: ([BOOT_MODE], "up")}),
}

IOMUX_LINES = {"MOSI": "mosi", "MISO": "miso", "CLK": "sclk", "CS": "cs", "WP": "wp", "HD": "hd"}  # names of spi_pins.h -> of the buses


def defines(path, names=r"SOC_\w+"):
    found = {}
    for line in path.read_text().splitlines():
        match = re.match(rf"#define\s+({names})\s+(.+?)\s*(/\*.*|//.*)?$", line)
        if match:
            found[match[1]] = match[2]
    return found


def number(text, found, depth=0):
    if text is None or depth > 4:
        return None
    text = re.sub(r"\bBIT(\d+)\b", lambda m: f"(1<<{m[1]})", text)
    text = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[UL]+\b", r"\1", text)
    for name in set(re.findall(r"\b[A-Za-z_]\w*\b", text)):
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
    # the rows of the list-table, by the names of its columns: some chips have no column of RTC or LP GPIO
    rows = [[first.strip(), *(cell.strip() for cell in re.findall(r"\n[ \t]+-[ \t]*([^\n]*)", rest))] for first, rest in re.findall(r"\* - ([^\n]*)((?:\n[ \t]+-[^\n]*)*)", text)]
    if not rows or rows[0][0] != "GPIO":
        return {}, []
    columns = {name: i for i, name in enumerate(rows[0])}
    cell = lambda row, *names: next((row[columns[name]] for name in names if name in columns and columns[name] < len(row)), "")
    pins = {}
    for row in rows[1:]:
        if not row[0].startswith("GPIO"):
            continue
        notes = [part.strip() for part in re.split(r"[;；,]", cell(row, "Comments", "Comment")) if part.strip()]
        low_power = cell(row, "RTC GPIO", "LP GPIO")
        if not low_power and "RTC" in notes:  # a table with no column of its own says RTC among the comments
            notes.remove("RTC")
            low_power = "RTC"
        entry = {"analog": [part.strip() for part in cell(row, "Analog Function").split(",") if part.strip()], "low_power": low_power, "notes": notes}
        entry = {key: value for key, value in entry.items() if value}
        if entry:
            pins[row[0][len("GPIO"):]] = entry
    block = re.search(r"\.\. note::\n\n((?:[ \t]+[^\n]*\n)+)", text)
    notes = [re.sub(r"`([^`<]*?)\s*<[^>]*>`_*", r"\1", line.strip()[2:]) for line in (block[1] if block else "").splitlines() if line.strip().startswith("- ")]
    return pins, notes


def versions(text):
    """A version as written in COMPATIBILITY.md, without its v and +."""
    return text.strip().lstrip("v").rstrip("+")


def since_first(sections):
    """The earliest version of a chip: "initial" goes before any number."""
    found = [entry["since"] for entry in sections.values() if "since" in entry]
    return min(found, key=lambda value: [0] if value == "initial" else [1, *map(int, value.split("."))]) if found else None


def compatibility():
    """What COMPATIBILITY.md of ESP-IDF says of each chip: since which version, by revision. A revision it does not name stays out."""
    chips = {}
    chip, revisions = None, []
    for row in (IDF / "COMPATIBILITY.md").read_text().splitlines():
        if row.startswith("### "):
            chip = re.sub(r"\s*&.*", "", row[4:]).strip().lower().replace("-", "")
            revisions = []
            chips[chip] = {"revisions": {}}
        elif row.startswith("## "):
            chip = None
        elif chip is None:
            continue
        elif row.startswith("#### "):
            revisions = [name.lstrip("v") for name in re.findall(r"v\d+\.\d+", row)]
            for revision in re.findall(r"v(\d+)\.(\d+) - v\d+\.(\d+)", row):
                revisions = [f"{revision[0]}.{minor}" for minor in range(int(revision[1]), int(revision[2]) + 1)]
            for revision in revisions:
                chips[chip]["revisions"].setdefault(revision, {})
        elif "Preview support since ESP-IDF" in row:
            chips[chip]["preview"] = versions(re.search(r"(v[\d.]*\d)", row)[1])
        elif "Supported since initial version" in row:
            for revision in revisions:
                chips[chip]["revisions"][revision]["since"] = "initial"
        elif "Supported since ESP-IDF" in row:
            for revision in revisions:
                chips[chip]["revisions"][revision]["since"] = versions(re.search(r"(v[\d.]*\d)", row)[1])
        elif row.startswith("| release/"):
            branch, recommended, required = [cell.strip() for cell in row.strip("|").split("|")]
            key = versions(branch.replace("release/", "").replace(" and above", "")) + ("+" if "and above" in branch else "")
            for revision in revisions:
                chips[chip]["revisions"][revision].setdefault("required", {})[key] = versions(required)
                chips[chip]["revisions"][revision].setdefault("recommended", {})[key] = versions(recommended)
    for entry in chips.values():
        entry["revisions"] = {revision: about for revision, about in entry["revisions"].items() if about}
        first = since_first(entry["revisions"])
        if first:
            entry["since"] = first
        if not entry["revisions"]:
            del entry["revisions"]
    return chips


def adc1_of(target_dir):
    """The pins of ADC1: Wi-Fi takes ADC2 on the older chips, so a part read with the radio on goes here."""
    header = next(iter(target_dir.glob("**/soc/adc_channel.h")), None)
    pins = sorted({int(pin) for pin in re.findall(r"ADC1_CHANNEL_\d+_GPIO_NUM\s+(\d+)", header.read_text())}) if header else []
    return {"adc1": pins} if pins else {}


def frequency_sources_of(target, found):
    """Where a chip gets a frequency, in the order to try them, from the headers and drivers of ESP-IDF."""
    soc = IDF / f"components/soc/{target}/include/soc"
    tree = (soc / "clk_tree_defs.h").read_text()
    freqs = defines(soc / "soc.h", r"(?:APB|REF)_CLK_FREQ")
    # the crystal the chip is built for by default; none when ESP-IDF finds it at boot (XTAL_FREQ_AUTO)
    kconfig = "".join(path.read_text() for path in (IDF / f"components/esp_hw_support/port/{target}").glob("Kconfig*"))
    crystal = re.search(r"choice XTAL_FREQ\b.*?default XTAL_FREQ_(\d+)\b", kconfig, re.S)
    xtal = int(crystal[1]) * 1000000 if crystal else None

    def hz(clock):
        if pll := re.fullmatch(r"PLL_F(\d+)M", clock):
            return int(pll[1]) * 1000000
        value = {"XTAL": xtal, "APB": number(freqs.get("APB_CLK_FREQ"), freqs), "REF_TICK": number(freqs.get("REF_CLK_FREQ"), freqs)}.get(clock)
        if value is None and clock != "XTAL":
            raise SystemExit(f"{target}: the frequency of the module clock {clock} is not known")
        return value

    def clocks(symbol):
        """The precise module clocks a peripheral can count, by the list of clk_tree_defs.h."""
        listed = re.search(rf"#define\s+{symbol}\s+\{{([^}}]*)\}}", tree)
        names = [name.strip().removeprefix("SOC_MOD_CLK_") for name in listed[1].split(",")] if listed else []
        return {name: hz(name) for name in names if name not in IMPRECISE_CLOCKS and hz(name)}

    def default(symbol):
        """The frequency of the clock the driver takes when the program names none."""
        return hz(re.search(rf"\b{symbol}\s*=\s*SOC_MOD_CLK_(\w+)", tree)[1])

    def low_level(part, names):
        return defines(IDF / f"components/esp_hal_{part}/{target}/include/hal/{part}_ll.h", names)

    sources = {}
    if found.get("SOC_LEDC_SUPPORTED"):
        ll = low_level("ledc", r"LEDC_LL_\w+")
        divider = defines(IDF / "components/esp_driver_ledc/src/ledc.c", r"LEDC_TIMER_DIV_NUM_MAX")
        modes = 2 if found.get("SOC_LEDC_SUPPORT_HS_MODE") else 1  # high and low speed, each with its own timers and channels
        sources["ledc"] = {"title": "LEDC", "kind": "ledc", "timers": modes * number(found["SOC_LEDC_TIMER_NUM"], found), "outputs": modes * number(found["SOC_LEDC_CHANNEL_NUM"], found),
                           "counter_bits": number(found["SOC_LEDC_TIMER_BIT_WIDTH"], found), "divider_bits": number(divider["LEDC_TIMER_DIV_NUM_MAX"], divider).bit_length(),
                           "fraction_bits": number(ll["LEDC_LL_FRACTIONAL_BITS"], ll), "clocks_hz": clocks("SOC_LEDC_CLKS"), "pairs": True, "can": LEDC_CAN}
    if found.get("SOC_MCPWM_SUPPORTED"):
        ll = low_level("mcpwm", r"MCPWM_LL_\w+")
        get = lambda name: number(ll[f"MCPWM_LL_{name}"], ll)
        groups = get("GROUP_NUM")
        # the prescale of a group is shared by its timers (mcpwm_com.c): it stays at the default of the driver as long as
        # the prescale of each timer fits, so a timer counts the clock divided by that default and by its own; the
        # driver takes a period below MAX_COUNT_VALUE (mcpwm_timer.c), though the register would hold that value too
        private = defines(IDF / "components/esp_driver_mcpwm/src/mcpwm_private.h", r"MCPWM_GROUP_CLOCK_DEFAULT_PRESCALE")
        sources["mcpwm"] = {"title": "MCPWM", "kind": "ticks", "timers": groups * get("TIMERS_PER_GROUP"), "outputs": groups * get("OPERATORS_PER_GROUP") * get("GENERATORS_PER_OPERATOR"),
                            "clock_hz": default("MCPWM_TIMER_CLK_SRC_DEFAULT") // number(private["MCPWM_GROUP_CLOCK_DEFAULT_PRESCALE"], private),
                            "ticks_max": get("MAX_COUNT_VALUE") - 1, "prescale_max": get("MAX_TIMER_PRESCALE"), "pairs": True, "can": MCPWM_CAN}
    if found.get("SOC_RMT_SUPPORTED"):
        ll = low_level("rmt", r"RMT_LL_\w+")
        text = (IDF / f"components/esp_hal_rmt/{target}/include/hal/rmt_ll.h").read_text()
        carrier = int(re.search(r"rmt_ll_tx_set_carrier_high_low_ticks.*?high_ticks <= (\d+)", text, re.S)[1])
        channels = number(ll["RMT_LL_INST_NUM"], ll) * number(ll["RMT_LL_TX_CANDIDATES_PER_INST"], ll)
        # the carrier counts the clock of the group (rmt_tx.c), whose divider, where it has one, is set once for all
        # channels and stays 1 for a channel resolution down to the clock / 256 (rmt_common.c): no prescale of its own
        sources["rmt"] = {"title": "RMT", "kind": "ticks", "timers": channels, "outputs": channels, "clock_hz": default("RMT_CLK_SRC_DEFAULT"),
                          "ticks_max": 2 * carrier, "prescale_max": 1, "pairs": False, "can": RMT_CAN}
    if channels := number(found.get("SOC_GPIO_CLOCKOUT_CHANNEL_NUM"), found):
        sources["clk_out"] = {"title": "CLK_OUT", "kind": "clock_out", "timers": channels, "outputs": channels, "signals": ["XTAL32K"] if re.search(r"\bCLKOUT_SIG_XTAL32K\b", tree) else [],
                              "pairs": False, "can": ["start_stop", *(["divider"] if found.get("SOC_CLOCKOUT_SUPPORT_CHANNEL_DIVIDER") else [])]}
    if found.get("SOC_I2S_SUPPORTS_APLL"):
        apll = defines(IDF / f"components/esp_hal_clock/{target}/include/hal/clk_tree_ll.h", r"CLK_LL_APLL_\w+")
        get = lambda name: number(apll[f"CLK_LL_APLL_{name}"], apll)
        i2s = low_level("i2s", r"I2S_LL_INST_NUM")
        sources["i2s_apll"] = {"title": "I2S with APLL", "kind": "apll", "timers": 1, "outputs": number(i2s["I2S_LL_INST_NUM"], i2s), "xtal_hz": xtal,
                               "min_hz": get("MIN_HZ"), "max_hz": get("MAX_HZ"), "multiplier_min_hz": get("MULTIPLIER_MIN_HZ"), "multiplier_max_hz": get("MULTIPLIER_MAX_HZ"), "pairs": False, "can": []}
    if found.get("SOC_DAC_SUPPORTED") and re.search(r"#define\s+SOC_DAC_COSINE_CLKS\b", tree):
        # one generator for the channels (dac_cosine.c), counting an RC oscillator
        sources["dac_cosine"] = {"title": "DAC cosine", "kind": "rc", "timers": 1, "outputs": number(found["SOC_DAC_CHAN_NUM"], found), "pairs": False, "can": []}
    return sources


def iomux_of(target):
    """The pins of the IO MUX of each SPI host from SPI2 on, from spi_pins.h (in esp_hal_gpspi since ESP-IDF 6, in soc before)."""
    for header in (IDF / f"components/esp_hal_gpspi/{target}/include/soc/spi_pins.h", IDF / f"components/soc/{target}/include/soc/spi_pins.h"):
        if header.exists():
            break
    else:
        return {}
    hosts = {}
    for host, line, pin in re.findall(r"#define\s+SPI(\d)_IOMUX_PIN_NUM_(MOSI|MISO|CLK|CS|WP|HD)\s+(\d+)\b", header.read_text()):
        if int(host) >= 2:
            hosts.setdefault(f"spi{host}", {})[IOMUX_LINES[line]] = int(pin)
    return {"spi": dict(sorted(hosts.items()))} if hosts else {}


def main():
    made = []
    supported = compatibility()
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
                 "gpio": {"count": count, "valid": bits(valid, 64), "input_only": bits(valid & ~out, 64), **adc1_of(target_dir)},
                 "hosts": {key: value for key, value in (("spi", number(found.get("SOC_SPI_PERIPH_NUM"), found)), ("i2c", number(found.get("SOC_HP_I2C_NUM") or found.get("SOC_I2C_NUM"), found)), ("uart", number(found.get("SOC_UART_HP_NUM") or found.get("SOC_UART_NUM"), found))) if value is not None},
                 "provides": {name: {} for symbol, name in PROVIDES.items() if number(found.get(symbol), found) == 1},
                 "checked": {"facts": {"level": "vendor-docs", "source": f"ESP-IDF {IDF.name}, components/soc/{target}, soc_caps.h"}}}
        if sources := frequency_sources_of(target, found):
            entry["frequency_sources"] = sources
            entry["checked"]["frequency_sources"] = {"level": "vendor-docs", "covers": ["frequency_sources"],
                                                     "source": f"ESP-IDF {IDF.name}: soc_caps.h, clk_tree_defs.h and soc.h of the chip, the Kconfig of its crystal, "
                                                               "the low-level headers of LEDC, MCPWM, RMT, I2S and the clock tree, the drivers of LEDC, MCPWM, RMT and the DAC"}
            entry["checked"].update(FREQUENCY_TRIED.get(target, {}))
        if target in GPIO_HIGH_MV_MAX:
            entry["gpio"]["high_mv_max"] = GPIO_HIGH_MV_MAX[target]
            entry["checked"]["levels"] = {"level": "datasheet", "covers": ["gpio.high_mv_max"], "source": "Espressif datasheet of the chip, DC characteristics: VIH at most VDD + 0.3 V, at VDD 3.3 V"}
        if "wifi" in entry["provides"]:
            entry["controls"] = {"wifi_tx_power": WIFI_TX_POWER}
        pins, notes = pin_table(target)
        if not pins:
            raise SystemExit(f"{target}: no table of pins read from docs/en/api-reference/peripherals/gpio/{target}.inc: the parse or the docs changed")
        # the strapping pins the table marks and those the note under it lists; none named is not the same as none there
        strapping = {int(pin) for pin, info in pins.items() if any(note.startswith("Strapping pin") for note in info.get("notes", ()))}
        for note in notes:
            if note.startswith("Strapping pin"):
                strapping |= {int(number) for number in re.findall(r"GPIO(\d+)", note.split("strapping pins")[0])}
        # the datasheet adds what the docs leave out (MTMS and MTDI of the C5 and the C61), and says what each pin does
        datasheet, modes, boot = BOOT.get(target, (None, {}, {}))
        strapping |= set(boot)
        for pin, (selects, pull, *footnote) in boot.items():
            # decides: False where the footnote says the level of the pin does not determine the mode its row names
            pins.setdefault(str(pin), {})["boot"] = {"selects": selects, "pull": pull, **({"footnote": footnote[0]} if footnote else {}), **({"decides": footnote[1]} if len(footnote) > 1 else {})}
        # pins by number, as a JS object orders keys that are numbers whatever order they were written in
        boot_modes = {"boot_modes": {mode: {str(pin): level for pin, level in sorted(levels.items())} for mode, levels in modes.items()}} if modes else {}
        entry["gpio"].update({**({"strapping": sorted(strapping)} if strapping else {}), **boot_modes, "pins": dict(sorted(pins.items(), key=lambda item: int(item[0]))), "notes": notes})
        source = f"ESP-IDF {IDF.name}, docs/en/api-reference/peripherals/gpio/{target}.inc"
        if strapping:
            entry["checked"]["pins"] = {"level": "vendor-docs", "covers": ["gpio.pins", "gpio.strapping"], "source": source}
        else:
            print(f"{target}: neither the docs nor a datasheet here name its strapping pins: gpio.strapping left out", file=sys.stderr)
            entry["checked"]["pins"] = {"level": "vendor-docs", "covers": ["gpio.pins"], "source": source, "notes": "the strapping pins are not named there"}
        if datasheet:
            entry["checked"]["boot"] = {"level": "datasheet", "covers": ["gpio.boot_modes", "gpio.strapping", "gpio.pins"], "source": f"{DATASHEETS}/{datasheet}"}
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
        iomux = iomux_of(target)
        if iomux:
            entry["iomux"] = iomux
            entry["checked"]["iomux"] = {"level": "vendor-docs", "covers": ["iomux"], "source": f"ESP-IDF {IDF.name}, spi_pins.h of {target}"}
        if target in supported:
            entry["platforms"] = {"esp_idf": supported[target]}
            entry["checked"]["platforms"] = {"level": "vendor-docs", "covers": ["platforms"], "source": "COMPATIBILITY.md of ESP-IDF"}
        path = ROOT / "catalog/mcu" / target / "mcu.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resolve.dump(entry) + "\n")  # as the page and the other tools write a document
        made.append(target)
    print("mcu:", " ".join(made))


if __name__ == "__main__":
    main()
