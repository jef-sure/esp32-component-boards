#!/usr/bin/env python3
"""
Writes a touch calibration into the data of a board. dgx_di_calibrate_measure prints a C
initializer in the log; give that text on stdin:

    python3 tools/board_calibration.py BOARD [TOUCH [LIBRARY=VERSION ...]] < log.txt
"""
import json
import pathlib
import re
import sys

import resolve

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIBRARY = "esp-idf/jef-sure/dgx-di"  # dgx_di_calibrate_measure prints the calibration of this library
HEAD = ("x_min", "x_max", "y_min", "y_max", "width", "height", "flags", "knots_x", "knots_y", "rounds")
TAIL = ("down_ms", "up_ms", "blink_ms", "gap_ms", "off_tenths", "worst_tenths", "left_tenths", "left_worst_tenths")


def field(text, name):
    match = re.search(rf"\.{name}\s*=\s*(-?\d+)", text)
    if not match:
        raise SystemExit(f"no .{name} in the text")
    return int(match[1])


def knots(text, name):
    match = re.search(rf"\.{name}\s*=\s*\{{((?:\s*\{{[^{{}}]*\}}\s*,?)*)\}}", text)
    if not match:
        raise SystemExit(f"no .{name} in the text")
    return [[int(a), int(b)] for a, b in re.findall(r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*\}", match[1])]


def parse(text):
    affine = re.search(r"\.affine\s*=\s*\{([^{}]*)\}", text)
    if not affine:
        raise SystemExit("no .affine in the text")
    out = {name: field(text, name) for name in HEAD}
    out.update({"affine": [int(v) for v in affine[1].split(",")], "x": knots(text, "x"), "y": knots(text, "y")})
    out.update({name: field(text, name) for name in TAIL})
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = ROOT / "catalog" / "boards" / sys.argv[1] / "board.json"
    board = json.loads(path.read_text())
    touch = sys.argv[2] if len(sys.argv) == 3 else "touch"
    if touch not in board.get("devices", {}):
        raise SystemExit(f"{path}: no device {touch}")
    measured = dict(arg.split("=", 1) for arg in sys.argv[3:])
    entry = {"rule": "the newest", **({"measured_with": measured} if measured else {}), **parse(sys.stdin.read())}
    board["devices"][touch].setdefault("config", {}).setdefault("calibrations", {}).setdefault(LIBRARY, []).append(entry)
    path.write_text(resolve.dump(board) + "\n")
    print(f"{path.relative_to(ROOT)}: the calibration of {touch} written; now tools/boards_gen.py --all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
