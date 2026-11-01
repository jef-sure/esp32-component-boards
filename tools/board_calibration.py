#!/usr/bin/env python3
"""
Writes a touch calibration into the data of a board: the places aimed at and what DGX-DI adds to
them. Give the log of dgx_di_calibrate_measure on stdin: the places come from its touches. A text
with only the C initializer gives places worked back from it.

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
MIRROR_X, MIRROR_Y, SWAP_XY = 1, 2, 4  # DGX_DI_MIRROR_X, DGX_DI_MIRROR_Y, DGX_DI_SWAP_XY
KNOTS = 3  # DGX_DI_KNOTS: dgx_di_calibrate_measure aims at three places of each axis
KEPT = 15  # dgx_di_calibrate_measure makes each target of the touches of the last rounds
PLACES = {
    "left_up": (0, 0), "right_up": (2, 0), "left_down": (0, 2), "right_down": (2, 2),
    "up": (1, 0), "down": (1, 2), "left": (0, 1), "right": (2, 1), "middle": (1, 1),
}
OWN = ("rounds", "blink_ms", "gap_ms", "off_tenths", "worst_tenths", "left_tenths", "left_worst_tenths")  # what the places do not say
WORKED_BACK = "The places are worked back from the calibration of DGX-DI: where it placed each target, not the touches themselves."
TOUCHES = "The places are the medians of the touches in the log."


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


def on_device(cal, x, y):
    """What the device reports at x, y as the record places it before its knots: dgx_di_pointer_map backwards."""
    a, b, c, d, e, f = (value / 65536 for value in cal["affine"])
    det = a * e - b * d
    sx, sy = (e * (x - c) - b * (y - f)) / det, (a * (y - f) - d * (x - c)) / det
    range_x, range_y = cal["x_max"] - cal["x_min"] + 1, cal["y_max"] - cal["y_min"] + 1
    swapped = cal["flags"] & SWAP_XY
    w, h = (range_y, range_x) if swapped else (range_x, range_y)
    u, v = round((sx + 0.5) * w / cal["width"] - 0.5), round((sy + 0.5) * h / cal["height"] - 0.5)
    dx, dy = (v, u) if swapped else (u, v)
    if cal["flags"] & MIRROR_X:
        dx = range_x - 1 - dx
    if cal["flags"] & MIRROR_Y:
        dy = range_y - 1 - dy
    return [dx + cal["x_min"], dy + cal["y_min"]]


def median(values):
    ordered, middle = sorted(values[-KEPT:]), min(len(values), KEPT) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle] + 1) >> 1


def touches_of(text, rounds):
    """Each target's median as in the log, as dgx_di_calibrate_measure takes it, for the rounds of the calibration."""
    kept = {}
    for number, target, x, y in re.findall(r"round (\d+), target (\d+) at -?\d+, -?\d+: the device's (-?\d+), (-?\d+)", text):
        if int(number) <= rounds:
            kept.setdefault(int(target), []).append((int(x), int(y)))
    return [[median([x for x, _ in seen]), median([y for _, y in seen])] for seen in kept.values()]


def entry_of(cal, text):
    """The entry of the data: the targets found by the knots of the record, each on the touches of the log if it has them."""
    if cal["knots_x"] != KNOTS or cal["knots_y"] != KNOTS:
        raise SystemExit("the calibration has no knots: its targets are not known, measure again")
    touches = touches_of(text, cal["rounds"])
    out = {"notes": TOUCHES if len(touches) == len(PLACES) else WORKED_BACK}
    out.update({name: cal[name] for name in ("x_max", "y_max", "width", "height")})
    for place, (column, row) in PLACES.items():
        (x, meant_x), (y, meant_y) = cal["x"][column], cal["y"][row]
        device = on_device(cal, x, y)
        if len(touches) == len(PLACES):
            device = min(touches, key=lambda touch: (touch[0] - device[0]) ** 2 + (touch[1] - device[1]) ** 2)
        out[place] = {"meant": [meant_x, meant_y], "device": device}
    out["libraries"] = {LIBRARY: {name: cal[name] for name in OWN}}
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = ROOT / "catalog" / "boards" / sys.argv[1] / "board.json"
    board = json.loads(path.read_text())
    touch = sys.argv[2] if len(sys.argv) >= 3 else "touch"
    if touch not in board.get("devices", {}):
        raise SystemExit(f"{path}: no device {touch}")
    measured = dict(arg.split("=", 1) for arg in sys.argv[3:])
    text = sys.stdin.read()
    head = {"rule": "the newest", **({"measured_with": measured} if measured else {})}
    board["devices"][touch].setdefault("config", {}).setdefault("calibrations", []).append({**head, **entry_of(parse(text), text)})
    path.write_text(resolve.dump(board) + "\n")
    print(f"{path.relative_to(ROOT)}: the calibration of {touch} written; now tools/boards_gen.py --all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
