#!/usr/bin/env python3
"""The pins of a board: who owns which GPIO, and the board as a tree.

Usage: board_pins.py BOARD            the map: GPIO -> owner, with the conflicts
       board_pins.py BOARD --tree     the tree: chip -> buses -> devices -> pins
       board_pins.py --all            the map of every board, the conflicts only

The same questions tools/check_boards.py asks of the data in CI (two owners of one pin, an
output on an input-only GPIO, a GPIO the chip has not), here to look at. Run from the
repository root.
"""

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import boards_gen  # noqa: E402


def pin_map(board):
    valid, input_only = boards_gen.GPIOS.get(board["mcu"]["target"], (range(0, 64), ()))
    owners = {}
    for pin, owner, direction in boards_gen.pins_of(board):
        owners.setdefault(pin, []).append((owner, direction))
    lines = [f"{board['title']} ({board['mcu']['target']}): GPIO -> owner"]
    for pin in sorted(owners):
        marks = []
        if pin not in valid:
            marks.append("NOT A GPIO OF THIS CHIP")
        if pin in input_only and any(d != "in" for _, d in owners[pin]):
            marks.append("INPUT ONLY, DRIVEN")
        if len(owners[pin]) > 1:
            marks.append("TWO OWNERS")
        names = ", ".join(f"{o} ({d})" for o, d in owners[pin])
        lines.append(f"  GPIO {pin:>2}  {names}" + (f"   <- {'; '.join(marks)}" if marks else ""))
    problems = boards_gen.pin_problems(board)
    lines.append(f"  {len(owners)} GPIOs used, {len(problems)} problem(s)")
    return "\n".join(lines)


def tree(board):
    lines = [f"{board['title']}  [{board['name']}]", f"  chip: {board['mcu']['target']}, flash {board['mcu'].get('flash_mb', '?')} MB"
             + (f", PSRAM {board['mcu']['psram_mb']} MB" if board['mcu'].get('psram_mb') else "")]
    buses = board.get("buses") or {}
    for kind, named in buses.items():
        for own, bus in (named or {}).items():
            fields = ", ".join(f"{k} {v}" for k, v in sorted((bus or {}).items()) if v is not None)
            lines.append(f"  bus {kind}.{own}: {fields}")
            # the devices on this bus
            display = board.get("display")
            if display and display.get("bus", {}).get("bus") == f"{kind}.{own}":
                strobes = ", ".join(f"{k} {v}" for k, v in display["bus"].items() if k != "bus" and v is not None)
                lines.append(f"    display {display['driver']}: {strobes}")
            touch = board.get("touch")
            if touch and touch.get("bus") == f"{kind}.{own}":
                lines.append(f"    touch {touch['kind']}" + (f" ({touch['component']})" if touch.get("component") else "") + ": "
                             + ", ".join(f"{k} {touch[k]}" for k in ("cs", "irq", "rst", "int") if touch.get(k) is not None))
            sound = board.get("sound")
            if sound and sound.get("bus") == f"{kind}.{own}":
                lines.append(f"    sound {sound['kind']}: address {sound.get('address')}, pa {sound.get('pa')}")
            if sound and sound.get("i2s_bus") == f"{kind}.{own}":
                lines.append(f"    sound {sound['kind']}: streams here")
            sd = board.get("sd")
            if sd and sd.get("bus") == f"{kind}.{own}":
                lines.append(f"    sd: cs {sd['cs']}")
    display = board.get("display")
    if display:
        if boards_gen.is_pixel(display):
            w, h, mm_w, mm_h = boards_gen.lying(display)
            lines.append(f"  display: {display['driver']} {w}x{h} px, {mm_w}x{mm_h} mm as it lies"
                         + (f", rst {display['rst']}" if display.get("rst") is not None else "")
                         + (f", backlight {display['backlight']}" if display.get("backlight") is not None else ""))
        else:
            lines.append(f"  display: {display['driver']} {display['geometry']} on {display['bus']['bus']}")
    sound = board.get("sound")
    if sound and sound["kind"] == "dac":
        lines.append(f"  sound: the chip's DAC on GPIO {sound['out']}" + (f", pa {sound['pa']}" if sound.get("pa") is not None else ""))
    if board.get("button"):
        lines.append(f"  button: GPIO {board['button']['pin']}, {'low' if board['button'].get('active_low', True) else 'high'} when pressed")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board", nargs="?")
    parser.add_argument("--tree", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    boards, modules = boards_gen.read_all(ROOT / "boards-data")
    if args.all:
        for board in boards:
            problems = boards_gen.pin_problems(board)
            print(f"{board['name']}: {len(problems)} problem(s)" + "".join(f"\n  {p}" for p in problems))
        return 0
    if not args.board:
        parser.error("a board, or --all")
    for board in boards + modules:
        if board["name"] == args.board:
            print(tree(board) if args.tree else pin_map(board))
            return 0
    print(f"{args.board}: no such board in boards-data/", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
