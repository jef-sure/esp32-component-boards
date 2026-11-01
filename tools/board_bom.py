#!/usr/bin/env python3
"""What to buy for a product, read from the data.

Usage: board_bom.py PROJECT                     the list for one product
       board_bom.py PROJECT --units 10          the list for ten
       board_bom.py PROJECT --shop AliExpress   the prices of one shop
       board_bom.py PROJECT --duty 3 EUR        a duty per tariff code in the order
       board_bom.py PROJECT --csv list.csv      the same lines for a spreadsheet

A line is what is bought as one: the board a project stands on, and what the project adds to it.
The chips of a bought board are not lines. Delivery and duty belong to an order, not to a board, so
they are not in the data: the duty comes from the command line, and a total stays a range.
"""

import argparse
import collections
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import resolve  # noqa: E402


def bought_as_one(doc):
    """The board a project stands on: a board with extends is a variant, bought as it is."""
    while doc.get("kind") == "project":
        doc = resolve.load("boards", doc["extends"])
    return doc


def line_of(item, title, count=1):
    return {"title": title, "count": count, **{key: item[key] for key in ("maker", "part", "price", "tariff") if key in item}}


def parts_of(use, module):
    """The devices a module brings, by the names they have on the board."""
    doc = resolve.chain(resolve.load("modules", module["module"]))
    resolve.add_modules(doc)
    return {f"{use}_{part}" for part in doc["devices"]}


def lines_of(name):
    """The lines of a board or project, the same goods on one line."""
    doc = resolve.load("boards", name)
    base = resolve.resolve(bought_as_one(doc))
    product = resolve.resolve(doc)
    lines = {"": {**line_of(base, base["title"]), **({"price": product["price"]} if "price" in product else {})}}  # a layer may add an offer
    parts = set()
    for use, module in product["modules"].items():
        parts |= parts_of(use, module)
        if use not in base["modules"]:
            lines.setdefault(f"module {module['module']}", {**line_of(module, module["title"]), "count": 0})["count"] += 1
    for use, device in product["devices"].items():
        if use not in base["devices"] and use not in parts:
            what = device.get("part") or device.get("chip") or use
            lines.setdefault(f"device {what}", {**line_of(device, what), "count": 0})["count"] += device.get("count", 1)
    return product, list(lines.values())


def offers_for(line, units, shop):
    """Per shop, the offer of the largest quantity that this many units reach."""
    best = {}
    for name, offer in (line.get("price") or {}).items():
        low, high = offer["range"]
        if low > high:
            raise ValueError(f"{line['title']}: price {name}: the range runs down: {offer['range']}")
        if shop and offer["shop"].lower() != shop.lower():
            continue
        least = offer.get("qty", 1)
        key = (offer["shop"], offer["currency"])
        if least <= units and least >= best.get(key, {}).get("qty", 1):
            best[key] = offer
    return list(best.values())


def costs_of(line, units, shop):
    """The cost of a line by currency: {currency: (each low, each high, line low, line high)}."""
    found = {}
    for offer in offers_for(line, units, shop):
        found.setdefault(offer["currency"], []).append(offer["range"])
    return {
        currency: (min(r[0] for r in ranges), max(r[1] for r in ranges), min(r[0] for r in ranges) * units, max(r[1] for r in ranges) * units)
        for currency, ranges in found.items()
    }


def money(currency, low, high):
    return f"{currency} {low:.2f}" if low == high else f"{currency} {low:.2f}-{high:.2f}"


def costs_text(costs, first):
    return ", ".join(money(currency, *cost[first : first + 2]) for currency, cost in sorted(costs.items())) or "no price"


def tariff_bounds(lines):
    """How many tariff codes an order counts: the known codes in one parcel, up to every line in its own."""
    known = {line["tariff"] for line in lines if "tariff" in line}
    return max(len(known), 1), len(lines)


def report(product, lines, args):
    rows = []
    totals = collections.defaultdict(lambda: [0, 0])
    for line in lines:
        units = line["count"] * args.units
        costs = costs_of(line, units, args.shop)
        rows.append({**line, "units": units, "each": costs_text(costs, 0), "cost": costs_text(costs, 2)})
        for currency, (_, _, low, high) in costs.items():
            totals[currency][0] += low
            totals[currency][1] += high
    width = max(len(row["title"]) for row in rows)
    out = [f"{product['title']}: {args.units} of it" + (f", prices of {args.shop}" if args.shop else ""), ""]
    out += [f"{row['units']:>4}  {row['title']:<{width}}  {row['each']:<20}  {row['cost']}" for row in rows]
    out.append("")
    out += [f"goods: {money(currency, *total)}" for currency, total in sorted(totals.items())]
    if args.duty:
        amount, currency = float(args.duty[0]), args.duty[1]
        fewest, most = tariff_bounds(lines)
        out.append(f"duty: {fewest} to {most} tariff codes at {money(currency, amount, amount)}: {money(currency, fewest * amount, most * amount)}")
        totals[currency][0] += fewest * amount
        totals[currency][1] += most * amount
    missing = [row["title"] for row in rows if row["each"] == "no price"]
    for currency, total in sorted(totals.items()):
        each = money(currency, total[0] / args.units, total[1] / args.units)
        out.append(f"{'at least' if missing else 'total'}: {money(currency, *total)}, {each} for one")
    if missing:
        out.append(f"no price, so the total is not complete: {', '.join(missing)}")
    return out, rows


def write_csv(path, rows):
    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["qty", "what", "maker", "part", "tariff", "each", "cost"])
        for row in rows:
            writer.writerow([row["units"], row["title"], row.get("maker", ""), row.get("part", ""), row.get("tariff", ""), row["each"], row["cost"]])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board", help="a board of the catalog, or of the program given by --project")
    parser.add_argument("--project", type=pathlib.Path, help="the program whose components/local-boards to read before the catalog")
    parser.add_argument("--units", type=int, default=1, help="how many products are built")
    parser.add_argument("--shop", help="use only the prices of this shop")
    parser.add_argument("--duty", nargs=2, metavar=("AMOUNT", "CURRENCY"), help="a duty on each tariff code in the order")
    parser.add_argument("--csv", type=pathlib.Path, help="write the lines to this file as well")
    args = parser.parse_args()
    if args.project:
        resolve.add_project(args.project)
    if args.units < 1:
        parser.error("--units must be 1 or more")
    try:
        product, lines = lines_of(args.board)
        text, rows = report(product, lines, args)
    except (resolve.Refused, ValueError) as error:
        print(f"{args.board}: {error}", file=sys.stderr)
        return 1
    print("\n".join(text))
    if args.csv:
        write_csv(args.csv, rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
