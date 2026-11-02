#!/usr/bin/env python3
"""
Writes the I2C addresses of the chips into imported/devices/. The Python of ESPHome (MIT) gives the one a chip comes at,
and the headers of libraries with a permissive license the others. Only text is read, nothing from these sources runs.
The board packs are no source: some give an address in the 8-bit form.

An address goes into `address_try`, the first as a chip comes. The list can be short: a value in a header shows that the
address exists, its absence shows nothing. So a clash on these addresses stays an unknown in the solver. What a filter
refused goes to imported/report_addresses.json with its reason, and a correction goes into catalog/, which is read first.

Run it after import_fritzing.py, which rewrites imported/devices/. --libraries is a folder of clones named owner__repo.
--compare FILE prints where a table of Tasmota's I2CDEVICES.md differs: it stays a check and goes nowhere.

Usage: import_addresses.py --esphome DIR --libraries DIR [--compare FILE] [--date YYYY-MM-DD]
"""
import argparse
import collections
import datetime
import json
import pathlib
import re
import shutil
import sys

import resolve

ROOT = resolve.ROOT
ARDUINO = "arduino_esp32"
PERMISSIVE = ("MIT", "BSD", "Apache", "ISC", "Unlicense", "CC0", "0BSD", "Zlib")
LOWEST, HIGHEST = 0x08, 0x77
SKIPPED_FOLDERS = {"examples", "example", "test", "tests", "extras", "docs"}
ESPHOME_DEFAULT = re.compile(r"i2c_device_schema\(\s*(?:default_address\s*=\s*)?(0x[0-9a-fA-F]+)\s*\)")
ESPHOME_NAMES = {"sht3xd": "sht31", "sht4x": "sht41", "aht10": "aht20", "tca9548a": "pca9548", "bmp3xx": "bmp390", "vl53l0x": "vl530x"}
DEFINE = re.compile(r"^\s*#\s*define\s+(\w+)\s+\(?\s*(?:\(uint8_t\)\s*)?(0x[0-9a-fA-F]{1,2})\s*\)?\s*(?://.*|/\*.*)?$")
ASSIGNED = re.compile(r"\b(\w*[Aa][Dd][Dd][Rr]\w*)\s*=\s*\(?(0x[0-9a-fA-F]{1,2})\)?\s*[;,)]")
ADDRESS_NAME = re.compile(r"I2C_?ADDR|DEFAULT_?(I2C_?)?ADDR|ADDR(ESS)?(_\w{1,10})?$", re.I)
NOT_ADDRESS = re.compile(r"REG|EEPROM|MEM|FLASH|PAGE|OFFSET|PTR|BUFFER|SLOT|ROM|OTP|CHANNEL|CMD|COMMAND|BLOCK|MASK|PIN|BIT|PART|SERIAL|MAC|BASE|START|END|LSB|MSB|SLV|WRITE|READ|COUNT|SIZE|LEN|NUM|MAX|MIN|STEP|DELAY", re.I)
FIRST_WORD = re.compile(r"^([A-Za-z]{2,}\d\w*?)_")
BUS_WORDS = ("i2c", "iic")
SHARED_PREFIX = 4


def key(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def form(value):
    return f"0x{value:02x}"


def esphome_defaults(components):
    found = {}
    for path in sorted(components.glob("*/*.py")):
        for match in ESPHOME_DEFAULT.finditer(path.read_text(errors="ignore")):
            value = int(match[1], 16)
            if LOWEST <= value <= HIGHEST:
                name = re.sub(r"_(i2c|base)$", "", path.parent.name)
                found.setdefault(key(ESPHOME_NAMES.get(name, name)), (value, f"esphome/components/{path.parent.name}/{path.name}"))
    return found


def other_chip(name, chip):
    """A name that starts with another part number: a companion chip of the same library."""
    word = FIRST_WORD.match(name)
    return bool(word) and key(word[1]) not in BUS_WORDS and not key(word[1]).startswith(chip[:SHARED_PREFIX])


def header_addresses(clones, repositories):
    """chip -> value -> (name, source), for each header of a library that names the chip."""
    found = collections.defaultdict(dict)
    refused = []
    for url, entry in repositories.items():
        folder = clones / re.sub(r"https://github\.com/|\.git$", "", url).replace("/", "__")
        for path in sorted(folder.rglob("*.h*")):
            parts = path.relative_to(folder).parts
            if ".git" in parts or SKIPPED_FOLDERS & {part.lower() for part in parts}:
                continue
            for row in path.read_text(errors="ignore").splitlines():
                match = DEFINE.match(row) or ASSIGNED.search(row)
                if not match or not ADDRESS_NAME.search(match[1]) or NOT_ADDRESS.search(match[1]):
                    continue
                value = int(match[2], 16)
                if not LOWEST <= value <= HIGHEST:
                    continue
                for chip in entry["chips"]:
                    wanted = key(chip)
                    if not any(wanted in text or wanted[:-1] in text for text in (key(match[1]), key(path.name), key(folder.name.split("__")[1]))):
                        continue
                    if other_chip(match[1], wanted):
                        refused.append({"chip": chip, "address": form(value), "name": match[1], "why": "names another chip"})
                    elif value not in found[chip] or found[chip][value][0].upper() != found[chip][value][0]:
                        found[chip][value] = (match[1], f"{folder.name.replace('__', '/')}/{path.name}")
    return found, refused


def addresses_of(chip, defaults, headers):
    """The list of a chip with the source of each, and the values refused."""
    found = headers.get(chip, {})
    named = {value: entry for value, entry in found.items() if entry[0].upper() == entry[0]}
    sources = {value: f"{entry[1]}: {entry[0]}" for value, entry in (named or found).items()}
    first = defaults.get(key(chip))
    if first:
        sources[first[0]] = first[1]
    # a header can give the address shifted left for the read and write bit
    refused = [{"chip": chip, "address": form(value), "why": "the 8-bit form of another"} for value in sources if value / 2 in sources]
    shifted = {int(item["address"], 16) for item in refused}
    kept = {value: source for value, source in sources.items() if value not in shifted}

    def rank(value):
        return (first is None or value != first[0], "DEFAULT" not in found.get(value, ("",))[0].upper(), value)

    return {form(value): kept[value] for value in sorted(kept, key=rank)}, refused


def table_of(path):
    table = {}
    for row in path.read_text().splitlines():
        cells = [cell.strip() for cell in row.split("|")]
        if len(cells) > 4 and cells[3] and "0x" in cells[4]:
            for part in cells[4].split(","):
                values = re.findall(r"0x[0-9a-fA-F]+", part)
                ends = [int(value, 16) for value in values]
                table.setdefault(key(cells[3]), set()).update(range(ends[0], ends[-1] + 1) if "-" in part and len(ends) == 2 else ends)
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--esphome", type=pathlib.Path, required=True, help="esphome/components of a clone")
    parser.add_argument("--libraries", type=pathlib.Path, required=True, help="a folder of clones named owner__repo")
    parser.add_argument("--esphome-license", type=pathlib.Path, help="its LICENSE, copied into imported/licenses/")
    parser.add_argument("--compare", type=pathlib.Path, help="an I2CDEVICES.md: prints where it differs")
    parser.add_argument("--list", action="store_true", help="print the repositories to clone and stop")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()

    out = ROOT / "imported"
    stubs = {path: json.loads(path.read_text()) for path in sorted((out / "devices").glob("*/device.json"))}
    on_i2c = {path: doc for path, doc in stubs.items() if "i2c" in (doc.get("on") or {})}
    names = {doc["name"] for doc in on_i2c.values()}
    repositories = {}
    for entry in json.loads((ROOT / "catalog" / "libraries" / "libraries.json").read_text())["libraries"].values():
        chips = sorted(names & set(entry["chips"]))
        if chips and ARDUINO in entry.get("platforms", []) and "github.com" in entry.get("repository", "") and entry.get("license", "").startswith(PERMISSIVE):
            repositories[entry["repository"]] = {"chips": chips, "license": entry["license"]}
    if args.list:
        print("\n".join(repositories))
        return 0

    defaults = esphome_defaults(args.esphome)
    headers, refused = header_addresses(args.libraries, repositories)
    report = {"date": args.date, "sources": {"esphome": "MIT, its Python", "headers": "libraries with a permissive license, listed by chip below"}, "chips": {}, "none": [], "refused": refused}
    for path, doc in on_i2c.items():
        addresses, dropped = addresses_of(doc["name"], defaults, headers)
        report["refused"] += dropped
        if not addresses:
            report["none"].append(doc["name"])
            continue
        doc["on"]["i2c"]["address_try"] = list(addresses)
        doc["checked"]["address"] = {"level": "extracted", "source": "imported/report_addresses.json"}
        path.write_text(resolve.dump(doc) + "\n")
        report["chips"][doc["name"]] = addresses

    (out / "report_addresses.json").write_text(resolve.dump(report) + "\n")
    if args.esphome_license:
        shutil.copyfile(args.esphome_license, out / "licenses" / "esphome.LICENSE")
    print(f"{len(report['chips'])} chips of {len(on_i2c)} on I2C have addresses, {len(report['refused'])} values refused")

    if args.compare:
        table = table_of(args.compare)
        for name, addresses in report["chips"].items():
            known = table.get(key(name))
            if known and {int(value, 16) for value in addresses} - known:
                print(f"{name}: {', '.join(addresses)}, the table has {', '.join(form(value) for value in sorted(known))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
