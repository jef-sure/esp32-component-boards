#!/usr/bin/env python3
"""
Imports modules from Fritzing parts into imported/modules/. Run it after import_board_manager.py, which rewrites
imported/devices/.

A part is data from the net: its XML is read and nothing in it runs, an .fzpz is read in place and never unpacked. Only
facts are taken: the contacts, the supply they name, the part number. A module needs a bus its contacts show and a role
its name shows; the rest goes to the report with its reason.

Usage: import_fritzing.py NAME=DIR ... [--ref NAME=COMMIT ...] [--out DIR] [--date YYYY-MM-DD]
"""
import argparse
import collections
import datetime
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import import_board_manager as importer
import resolve

ROOT = resolve.ROOT
LICENSE = "CC-BY-SA-3.0"
TOOL = "tools/import_fritzing.py"
BIGGEST_PART = 4 * 1024 * 1024  # a description is text: anything larger in an .fzpz is not one
MOST_CONTACTS = 48
FIRST_CONTACTS = {"J1": "contacts of the part"}
GONE = "the shop no longer sells it"
NEEDS_MORE = ("display", "touch", "audio")  # a device of these needs a chip and a config of its own
ROLES = [role for group in json.loads((ROOT / "catalog" / "roles.json").read_text())["groups"] for role in group["roles"]]
I2S_CLOCK, I2S_WORD = {"bclk", "bck", "bitclk"}, {"lrc", "lrck", "lrclk", "ws", "wsel"}
ONE_LINE = {"din", "di", "data", "dat", "dq", "sig", "signal", "s", "in", "out", "do", "ctrl", "pwm"}
MOST_FOR_ONE_LINE = 6
# what is not a module for a board of ours
NOT_MODULES = (("a board of its own", r"\b(arduino|raspberry|teensy|esp8266|esp32|nodemcu|wemos|launchpad|beaglebone|pyboard|pybadge|pygamer|pyportal|netduino|metro|itsybitsy|trinket|gemma|flora|qt py|circuit playground|feather(?!wing)|96boards|spresense|photon|particle|ft232h|kb2040|macropad|trinkey|pic\d+f\w*)\b"),
               ("for another form", r"\b(shield|cobbler|hat|bonnet|pihat|breadboard|programmer|ftdi|usb to)\b"))
BARE_PACKAGE = re.compile(r"(dip|soic|sot|qfn|tqfp|ssop|tsop|to-?\d)", re.I)
JUST_A_NUMBER = re.compile(r"[0-9A-Z-]{5,14}")  # in the core of Fritzing a title like this is a chip with no board
CHIP_LIKE = re.compile(r"\b([A-Z]{2,6}-?\d{2,5}[A-Z0-9]{0,6})\b")
NOT_CHIPS = {"USB", "I2C", "RGB", "SPI"}
SUPPLY = ((re.compile(r"^\+?3(\.3?0?)?v3?$|^3v3$", re.I), 3.3), (re.compile(r"^\+?5(\.0)?v$", re.I), 5))
ANY_SUPPLY = re.compile(r"^(vcc|vin|vdd|v\+|vbat|vbus|power|pwr)$", re.I)
SPI_OUT, SPI_CLOCK, SPI_SELECT = {"mosi", "sdi", "si", "dat"}, {"sck", "sclk", "clk"}, {"cs", "ss", "nss", "ssel", "ce", "cs0"}
UART_PAIRS = ({"tx", "rx"}, {"txd", "rxd"}, {"txo", "rxi"})


def text_of(path):
    """The description of a part: an .fzp, or the one inside an .fzpz."""
    if path.suffix == ".fzp":
        return path.read_bytes()
    with zipfile.ZipFile(path) as package:
        member = next((info for info in package.infolist() if info.filename.endswith(".fzp")), None)
        if member is None or member.file_size > BIGGEST_PART:
            return None
        return package.read(member)


def read_part(path):
    root = ET.fromstring(text_of(path))
    contacts = []
    for connector in root.findall(".//connector"):
        name = (connector.get("name") or "").strip()
        if name and name not in contacts:
            contacts.append(name)
    return {"title": (root.findtext("title") or "").strip(), "tags": [tag.text or "" for tag in root.findall(".//tag")],
            "properties": {item.get("name"): (item.text or "").strip() for item in root.findall(".//property")}, "contacts": contacts}


def buses_of(contacts):
    """The buses the names of the contacts show. One contact may carry several, as NSS/SCL/RX."""
    names = {word for contact in contacts for word in re.split(r"[/ _\-]+", contact.lower()) if word}
    found = []
    if any(name.endswith("sda") for name in names) and any(name.endswith("scl") for name in names):  # 0SDA, INPUTSDA of a multiplexer
        found.append("i2c")
    if {"mosi", "miso"} <= names or (names & SPI_OUT and names & SPI_CLOCK and names & SPI_SELECT):
        found.append("spi")
    if any(pair <= names for pair in UART_PAIRS):
        found.append("uart")
    if names & I2S_CLOCK and names & I2S_WORD:
        found.append("i2s")
    return found


def one_line(contacts):
    """The contact of a part with a single data line and its supply, when that is all it has."""
    if len(contacts) > MOST_FOR_ONE_LINE:
        return None
    return next((contact for contact in contacts if contact.lower() in ONE_LINE), None)


def supply_of(contacts):
    """The step a module takes from the board: its volts when a contact names them, the highest of several."""
    named = [volts for contact in contacts for pattern, volts in SUPPLY if pattern.match(contact)]
    if named:
        return {"name": "VCC", "source": "connector", "volts": max(named)}
    return {"name": "VCC", "source": "connector"} if any(ANY_SUPPLY.match(contact) for contact in contacts) else None


def roles_of(text):
    """The roles the name of a part shows, and of each the first variant it names."""
    found = []
    for role in ROLES:
        if re.search(role["words"], text, re.I):
            variant = next((item for item in role.get("variants", []) if re.search(item["words"], text, re.I)), None)
            found.append((role, variant))
    return found


def config_of(role, title, text):
    """What a display or a sound must say of itself, when its name tells; None when it does not."""
    if role == "audio":
        return {"direction": "in"} if re.search(r"\b(microphone|mic)\b", text, re.I) else {"direction": "out"}
    size = re.search(r"\b(\d{2,4}) ?x ?(\d{2,4})\b", title)
    if role == "display" and size:
        return {"kind": "graphics", "panel": {"width": int(size[1]), "height": int(size[2])}}
    return None


def chip_of(title, known):
    """The chip of a part: one of the catalog by its name in the title, or what looks like a part number there."""
    plain = title.lower().replace("-", "").replace("_", "")
    found = next((name for name in known if len(name) > 3 and re.search(rf"(?<![a-z0-9]){re.escape(name.replace('_', ''))}(?![a-z0-9])", plain)), None)
    if found:
        return found, True
    token = next((item for item in CHIP_LIKE.findall(title) if item.rstrip("0123456789-") not in NOT_CHIPS), None)
    return (importer.word(token.replace("-", "")), False) if token else (None, False)


def same_title(title):
    """A title without the maker and the punctuation: a copy of a part lies in several sources."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^(adafruit|sparkfun)\s+", "", title.lower()))


def read_shop(folder):
    """A copy of what a shop lists: {product: {price, gone, sections}}, and the roles of its sections."""
    shop = {}
    for product in json.loads((folder / "adafruit_products.json").read_text()):
        shop[product["product_id"]] = {"price": product["product_price"], "gone": product.get("discontinue_status") == "Discontinued", "sections": set()}

    def walk(items, path):
        for item in items:
            here = [*path, item["category_name"]]
            for product in item.get("products") or []:
                if product["product_id"] in shop:
                    shop[product["product_id"]]["sections"].add("/".join(here))
            walk(item.get("subcategories") or [], here)

    walk(json.loads((folder / "adafruit_categories.json").read_text()), [])
    for product in shop.values():
        product["roles"] = {role for role, sections in json.loads((folder / "sections.json").read_text()).items() if set(sections) & product["sections"]}
    return shop


def module_of(source, path, part, known, run, shop=None):
    """The record of a part and None, or None and why it stays out."""
    title, properties = part["title"], part["properties"]
    text = " ".join([title, *part["tags"], properties.get("family", "")])
    if BARE_PACKAGE.search(properties.get("package", "")) or (source == "fritzing" and JUST_A_NUMBER.fullmatch(title)):
        return None, "a bare chip"
    number = re.search(r"#?(\d[\w-]*)", properties.get("part number", ""))
    listed = (shop or {}).get(number[1]) if number and "adafruit" in source else None
    if listed and listed["gone"]:
        return None, GONE
    for reason, pattern in NOT_MODULES:
        if re.search(pattern, text, re.I):
            return None, reason
    if not 3 <= len(part["contacts"]) <= MOST_CONTACTS:
        return None, "the number of contacts"
    buses = buses_of(part["contacts"])
    line = None if buses else one_line(part["contacts"])
    if not buses and not line:
        return None, "no bus by its contacts"
    chip, in_catalog = chip_of(title, known)
    roles = roles_of(text)
    if listed:
        roles += [(role, None) for role in ROLES if role["id"] in listed["roles"] and role["id"] not in {item["id"] for item, _ in roles}]
    if not roles and not chip:
        return None, "no role by its name and no chip"
    first, variant = roles[0] if roles else (None, None)
    role = first["class"] if first else (known.get(chip) or ["other"])[0] if in_catalog else "other"
    if role == "button":  # a button of the format has its line, and a part may hold several
        role = "other"
    config = config_of(role, title, text)
    if role in NEEDS_MORE and (not chip or config is None):
        run.no_place[f"{role} with too little data: its contacts are kept"] += 1
        role = "other"
    name = importer.word(f"{source}_{title}")[:80].rstrip("_")
    device = {"on": {bus: {} for bus in buses}} if buses else {"ways": [(variant or {}).get("way") or {"lines": [line.lower()]}]}
    if roles:
        device["provides"] = {item["id"]: ({"variant": chosen["id"]} if chosen else {}) for item, chosen in roles}
    if role in NEEDS_MORE:
        device["config"] = config
    if chip:
        device["chip"] = chip
        if not in_catalog:
            run.chip(chip, role, buses)
    else:
        device["class"] = role
    doc = {**importer.HEAD, "kind": "module", "name": name, "title": title, "devices": {first["id"] if first else role: device}, "connectors": {"J1": {"type": FIRST_CONTACTS["J1"], "pins": part["contacts"]}}}
    if "adafruit" in source:
        doc["maker"] = "adafruit"
    if listed:
        doc["price"] = {"adafruit": {"shop": "Adafruit", "currency": "USD", "range": [float(listed["price"])] * 2, "date": run.date, "source": "A copy of the product list of adafruit.com"}}
    if number:
        doc["part"] = number[1]
    supply = supply_of(part["contacts"])
    if supply:
        doc["power"] = [supply]
    return doc, None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", nargs="+", help="NAME=DIR of the .fzp and .fzpz files")
    parser.add_argument("--ref", action="append", default=[], help="NAME=COMMIT of a source")
    parser.add_argument("--shop", type=pathlib.Path, help="the directory of a copy of what the shop lists")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "imported")
    parser.add_argument("--unpublished", type=pathlib.Path, default=ROOT / "imported-shops", help="where what comes from --shop goes: it has no license to be published")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()
    refs = dict(item.split("=", 1) for item in args.ref)

    run = importer.Import()
    run.date = args.date
    shop = read_shop(args.shop) if args.shop else None
    resolve.ROOTS.insert(0, args.out)
    known = {}
    for root in (ROOT / "catalog", args.out):
        for path in sorted((root / "devices").glob("*/device.json")):
            entry = json.loads(path.read_text())
            known.setdefault(entry["name"], [entry["class"]] if isinstance(entry.get("class"), str) else entry.get("class") or [])
    known = dict(sorted(known.items(), key=lambda item: -len(item[0])))  # the longest name first: st7789v before st7789

    docs, unpublished, outside, seen = {}, {}, collections.defaultdict(collections.Counter), set()
    for source in args.sources:
        name, _, folder = source.partition("=")
        for path in sorted([*pathlib.Path(folder).glob("*.fzp"), *pathlib.Path(folder).glob("*.fzpz")]):
            try:
                part = read_part(path)
            except (ET.ParseError, zipfile.BadZipFile, TypeError):
                outside[name]["unreadable"] += 1
                continue
            doc, reason = module_of(name, path, part, known, run)
            shop_doc, shop_reason = module_of(name, path, part, known, run, shop) if shop else (None, None)
            if shop_reason == GONE:
                outside[name][GONE] += 1
                continue
            if reason and not shop_doc:
                outside[name][reason] += 1
                continue
            title = (doc or shop_doc)["title"]
            if same_title(title) in seen:
                outside[name]["the same title twice"] += 1  # the sources go in the order of the arguments: the first stays
                continue
            seen.add(same_title(title))
            for record in filter(None, (doc, shop_doc)):
                record["origin"] = {"from": name, "ref": refs.get(name, ""), "path": path.name, "license": LICENSE, "tool": TOOL, "date": args.date}
                record["checked"] = {"part": {"level": importer.LEVEL, "source": f"{name} {refs.get(name, '')}".strip()}}
            if doc:
                docs[doc["name"]] = doc
            if shop_doc and shop_doc != doc:
                unpublished[shop_doc["name"]] = shop_doc

    # a stub of this run joins those the boards left
    for chip, entry in run.chips.items():
        path = args.out / "devices" / chip / "device.json"
        if path.exists():
            kept = json.loads(path.read_text())
            entry["class"] = sorted({*kept["class"], *entry["class"]})
            entry["on"] = {**kept.get("on", {}), **entry.get("on", {})}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resolve.dump(entry) + "\n")

    raw, whole, found_rules = importer.validators()
    refused = {}
    for name, doc in docs.items():
        problems = importer.checked(doc, raw, whole, found_rules)
        if problems:
            refused[name] = problems
    taken = {name: doc for name, doc in docs.items() if name not in refused}
    importer.write_documents(args.out, "modules", "module.json", taken)
    from_shop = {name: doc for name, doc in unpublished.items() if not importer.checked(doc, raw, whole, found_rules)}
    if shop:
        importer.write_documents(args.unpublished, "modules", "module.json", from_shop)
        importer.write_index(args.unpublished)
    roles = collections.Counter(next(iter(doc["devices"])) for doc in taken.values())
    report = {"date": args.date, "modules": len(taken), "license": LICENSE, "by_role": dict(roles.most_common()), "stayed_out": {name: dict(counter.most_common()) for name, counter in outside.items()},
              "refused": refused, "chips_of_their_own": sorted(run.chips)}
    (args.out / "report_fritzing.json").write_text(resolve.dump(report) + "\n")
    importer.write_index(args.out)
    print(f"{len(taken)} modules taken, {len(from_shop)} with shop data apart, {len(refused)} refused, {len(run.chips)} chips with no entry of their own")
    print("no place:", run.no_place.most_common())
    print("by role:", roles.most_common())
    print("stayed out:", {name: counter.most_common(6) for name, counter in outside.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
