#!/usr/bin/env python3
"""
Takes a price from the text of an issue of the form .github/ISSUE_TEMPLATE/price.yml and adds it to the file of
its item as an offer. The text comes from anyone: it is only read as fields, and the item must be one of the catalog.

Usage: take_report.py BODY_FILE --issue NUMBER [--catalog DIR]
"""
import argparse
import datetime
import json
import pathlib
import re
import sys

import resolve

ROOT = pathlib.Path(__file__).resolve().parent.parent

FILES = {"boards": "board.json", "modules": "module.json", "addons": "addon.json"}
ITEM = re.compile(r"^(boards|modules|addons)/[a-z0-9_]+$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
# A decimal comma has one or two digits after it: 1,200 may be a thousand and two hundred, and is refused.
NUMBER = r"\d+(?:\.\d+|,\d{1,2})?"
PRICE = re.compile(rf"^({NUMBER})(?:\s*-\s*({NUMBER}))?$")
EMPTY = "_No response_"


def fields_of(body):
    """The fields of an issue form: a heading of three hashes, then the answer."""
    found = {}
    for part in re.split(r"^### ", body, flags=re.M)[1:]:
        label, _, value = part.partition("\n")
        found[label.strip()] = "" if value.strip() == EMPTY else value.strip()
    return found


def offer_of(fields, issue, today):
    """The file of the item and its offer. Raises ValueError with what is wrong."""
    item, shop, currency = fields.get("Item", ""), fields.get("Shop", ""), fields.get("Currency", "").upper()
    if not ITEM.match(item):
        # The comment shows it in a code span, where a @name mentions no one.
        shown = item.partition("\n")[0][:60].replace("`", "")
        raise ValueError(f"Item: not one of the catalog, as modules/pn532_module: `{shown}`")
    if not shop or len(shop) > 60 or "\n" in shop:
        raise ValueError("Shop: one short line")
    if not CURRENCY.match(currency):
        raise ValueError("Currency: three letters")
    price = PRICE.match(fields.get("Price of one", ""))
    if not price:
        raise ValueError("Price of one: a number as 3.76 or 3,76, or a range as 3-5, without a currency sign or a thousands separator")
    low, high = (float(number.replace(",", ".")) for number in (price[1], price[2] or price[1]))
    if low > high:
        raise ValueError("Price of one: the range runs down")
    offer = {"shop": shop, "currency": currency, "range": [low, high], "date": today, "source": f"Issue {issue}, as reported"}
    qty = fields.get("Sold by", "")
    if qty:
        if not qty.isdigit() or int(qty) < 1:
            raise ValueError("Sold by: a whole number")
        offer["qty"] = int(qty)
    return item, offer


def shop_names(catalog):
    """The shops of the catalog as it writes them, by the name in lower case."""
    names = {}
    for path in catalog.glob("*/*/*.json"):
        doc = json.loads(path.read_text())
        for offer in (doc.get("price") or {}).values() if isinstance(doc, dict) else ():
            names.setdefault(offer["shop"].lower(), offer["shop"])
    return names


def take(body, issue, catalog, today):
    fields = fields_of(body)
    item, offer = offer_of(fields, issue, today)
    offer["shop"] = shop_names(catalog).get(offer["shop"].lower(), offer["shop"])
    kind, name = item.split("/")
    path = catalog / kind / name / FILES[kind]
    if not path.is_file():
        raise ValueError(f"Item: the catalog has no {item}")
    text = path.read_text()
    doc = json.loads(text)
    doc.setdefault("price", {})[f"report_{issue}"] = offer
    path.write_text(with_offer(text, f"report_{issue}", offer, doc))
    return f"{item}: {offer['shop']}, {offer['range']} {offer['currency']}"


def closing(text, start):
    """Where the object that opens at text[start] closes, strings skipped."""
    depth, quoted, escaped = 0, False, False
    for at in range(start, len(text)):
        char = text[at]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if not depth:
                return at
    return -1


def with_offer(text, key, offer, doc):
    """The file with one offer more, by a line put into its text, so the rest of the file stays as it was written; the
    whole file anew (resolve.dump) when the text is not in a shape that takes one."""
    line = f'        "{key}": {resolve.dump(offer, 8, len(key) + 4)}'
    found = re.search(r'^    "price": \{', text, re.M)
    if found:
        end = closing(text, found.end() - 1)
        before = text[:end].rstrip()
        made = f"{before}{'' if before.endswith('{') else ','}\n{line}\n    " + text[end:]
    else:
        last = closing(text, text.index("{"))
        before = text[:last].rstrip()
        made = f'{before},\n    "price": {{\n{line}\n    }}\n' + text[last:]
    try:
        if json.loads(made) == doc:
            return made
    except ValueError:
        pass
    return resolve.dump(doc) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("body", type=pathlib.Path)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--catalog", type=pathlib.Path, default=ROOT / "catalog")
    args = parser.parse_args()
    try:
        print(take(args.body.read_text(), args.issue, args.catalog, datetime.date.today().isoformat()))
    except ValueError as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
