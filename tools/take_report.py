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

FILES = {"boards": "board.json", "modules": "module.json"}
ITEM = re.compile(r"^(boards|modules)/[a-z0-9_]+$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
PRICE = re.compile(r"^(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?$")
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
        raise ValueError(f"Item: not one of the catalog, as modules/pn532_module: {item[:60]}")
    if not shop or len(shop) > 60 or "\n" in shop:
        raise ValueError("Shop: one short line")
    if not CURRENCY.match(currency):
        raise ValueError("Currency: three letters")
    price = PRICE.match(fields.get("Price of one", ""))
    if not price:
        raise ValueError("Price of one: a number, or a range as 3-5")
    low, high = float(price[1]), float(price[2] or price[1])
    if low > high:
        raise ValueError("Price of one: the range runs down")
    offer = {"shop": shop, "currency": currency, "range": [low, high], "date": today, "source": f"Issue {issue}, as reported"}
    qty = fields.get("Sold by", "")
    if qty:
        if not qty.isdigit() or int(qty) < 1:
            raise ValueError("Sold by: a whole number")
        offer["qty"] = int(qty)
    return item, offer


def take(body, issue, catalog, today):
    fields = fields_of(body)
    item, offer = offer_of(fields, issue, today)
    kind, name = item.split("/")
    path = catalog / kind / name / FILES[kind]
    if not path.is_file():
        raise ValueError(f"Item: the catalog has no {item}")
    doc = json.loads(path.read_text())
    doc.setdefault("price", {})[f"report_{issue}"] = offer
    path.write_text(resolve.dump(doc))
    return f"{item}: {offer['shop']}, {offer['range']} {offer['currency']}"


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
