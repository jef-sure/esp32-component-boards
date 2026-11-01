#!/usr/bin/env python3
"""
Writes catalog/rates.json from the reference rates of the European Central Bank, so that prices in
any currency compare. The rates are of one day: a price is an estimate, and so is what it comes to.
"""
import json
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
NAMESPACE = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
TIMEOUT_S = 30


def main():
    with urllib.request.urlopen(SOURCE, timeout=TIMEOUT_S) as answer:
        tree = ET.fromstring(answer.read())
    day = next(cube for cube in tree.iter(f"{NAMESPACE}Cube") if "time" in cube.attrib)
    rates = {cube.attrib["currency"]: float(cube.attrib["rate"]) for cube in day}
    out = {"format": "jef-sure/boards", "format_version": 2, "base": "EUR", "date": day.attrib["time"], "source": SOURCE, "rates": dict(sorted(rates.items()))}
    (ROOT / "catalog" / "rates.json").write_text(json.dumps(out, indent=4) + "\n")
    print(f"rates of {out['date']}: {len(rates)} currencies")


if __name__ == "__main__":
    main()
