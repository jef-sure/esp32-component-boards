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
# Digits with the marks people put between them: a point or a comma, and a space, a no-break space or an apostrophe
# that only part thousands.
NUMBER = re.compile(r"^\d(?:[\d.,' \u00a0\u202f\u2009]*\d)?$")
GROUPS = " '\u00a0\u202f\u2009"
DASH = re.compile(r"\s*[-\u2013\u2014]\s*")
# A sign in the price is taken when it is one of the currency of the form.
SIGNS = {"€": {"EUR"}, "£": {"GBP"}, "₹": {"INR"}, "¥": {"JPY", "CNY"}, "$": {"USD", "AUD", "CAD", "NZD", "SGD", "HKD", "MXN"}}
PRICE_FORMS = "a number as 3.76, 3,76, 1,234.56 or 1.234,56, or a range as 3-5"
EMPTY = "_No response_"


def fields_of(body):
    """The fields of an issue form: a heading of three hashes, then the answer."""
    found = {}
    for part in re.split(r"^### ", body, flags=re.M)[1:]:
        label, _, value = part.partition("\n")
        found[label.strip()] = "" if value.strip() == EMPTY else value.strip()
    return found


def number_of(text):
    """A price as it is written in one country or another: 3.76, 3,76, 1,234.56, 1.234,56, 1 234,56, 1'234.56.
    Raises ValueError when it is not a number, or when it reads two ways."""
    if not NUMBER.match(text):
        raise ValueError(f"Price of one: {PRICE_FORMS}")
    marks = [char for char in text if char in ".,"]
    decimal = None
    if len(set(marks)) == 2:
        decimal = marks[-1]
    elif len(marks) == 1:
        whole, fraction = re.split("[.,]", text)
        # one mark before three digits is a decimal mark or a thousands one: 1,200 is 1.2 in Germany and 1200 in England
        if len(fraction) == 3 and whole.strip(GROUPS) != "0" and not any(char in GROUPS for char in text):
            raise ValueError(f"Price of one: {text} reads two ways, {whole}.{fraction} and {whole}{fraction}: write {whole}{fraction} for the second, "
                             f"{whole}{marks[0]}{fraction}0 for the first")
        decimal = marks[0]
    whole, _, fraction = text.rpartition(decimal) if decimal else (text, "", "")
    parted_by = set(re.sub(r"\d", "", whole))
    groups = re.split(r"[.,' \u00a0\u202f\u2009]", whole)
    if len(parted_by) > 1 or decimal in parted_by or not grouped([len(group) for group in groups]):
        raise ValueError(f"Price of one: {text}: the thousands are not parted by three digits; {PRICE_FORMS}")
    return float("".join(groups) + "." + (fraction or "0"))


def grouped(sizes):
    """Digit groups of a whole number: by three, as 1,234,567, or in India by two before the last three, as 12,34,567."""
    if len(sizes) == 1:
        return True
    if sizes[-1] != 3:
        return False
    return 1 <= sizes[0] <= 3 and all(size == 3 for size in sizes[1:]) or 1 <= sizes[0] <= 2 and all(size == 2 for size in sizes[1:-1])


def price_of(text, currency):
    """The range of a price, with the currency taken out when it is the one of the form."""
    text = re.sub(rf"(?i)\b{currency}\b", " ", text)
    for sign, codes in SIGNS.items():
        if currency in codes:
            text = text.replace(sign, " ")
    numbers = DASH.split(text.strip())
    if len(numbers) > 2:
        raise ValueError(f"Price of one: {PRICE_FORMS}")
    low, high = number_of(numbers[0]), number_of(numbers[-1])
    if low > high:
        raise ValueError("Price of one: the range runs down")
    return [low, high]


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
    offer = {"shop": shop, "currency": currency, "range": price_of(fields.get("Price of one", ""), currency), "date": today, "source": f"Issue {issue}, as reported"}
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
