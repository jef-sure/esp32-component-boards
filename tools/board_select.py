#!/usr/bin/env python3
"""Choose the board a project is built for: once, here.

Usage: board_select.py BOARD [--module MODULE ...] [--reset] PROJECT_DIR

Writes PROJECT_DIR/sdkconfig.defaults.board: the board's sdkconfig.defaults (its chip, its
memory, its flash, and the two lines that choose it: CONFIG_IDF_TARGET and
CONFIG_BOARD_SELECT_<BOARD>=y), then the defaults of every module named. The project's
CMakeLists.txt reads that file before its own defaults:

    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
        set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
    endif()

and then idf.py build builds for the board: no set-target, no menuconfig, the menu follows
the file. The board is named once, on this command line.

An sdkconfig the project already has is not touched unless --reset: ESP-IDF reads the
defaults only when it makes a new sdkconfig, so a project that changes its board removes the
old one (--reset does, keeping a copy as sdkconfig.old).

The data is found beside this script (the component's catalog/), wherever the component
lies: a checkout beside the project or managed_components/jef-sure__boards/.
"""

import argparse
import pathlib
import sys

import resolve

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "catalog"


def defaults_of(name, what):
    kind, file = ("boards", "board.json") if what == "board" else ("modules", "module.json")
    if not (DATA / kind / name / file).exists():
        known = ", ".join(sorted(p.parent.name for p in (DATA / kind).glob(f"*/{file}")))
        raise SystemExit(f"{name}: no such {what} in {DATA / kind} ({known})")
    defaults = DATA / kind / name / "sdkconfig.defaults"
    if not defaults.exists():
        raise SystemExit(f"{name}: nothing to turn on here, it is data: name it in modules of the board")
    return defaults.read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board", help="the board's directory name in catalog/boards/")
    parser.add_argument("project", type=pathlib.Path, help="the project's directory (where its CMakeLists.txt is)")
    parser.add_argument("--module", action="append", default=[], help="a module the board carries (its directory name in catalog/modules/); may repeat")
    parser.add_argument("--revision", help="the revision of the chip, when it is not the one the data of the board names: 3.1")
    parser.add_argument("--reset", action="store_true", help="move the project's sdkconfig aside, so the new board's defaults are read")
    args = parser.parse_args()
    if not (args.project / "CMakeLists.txt").exists():
        raise SystemExit(f"{args.project}: no CMakeLists.txt there, is it a project?")
    parts = [f"# The board of this project, chosen by tools/board_select.py of jef-sure/boards: {args.board}"
             + (f", with {', '.join(args.module)}" if args.module else "")
             + "\n# Read before the project's own sdkconfig.defaults. Made from the data of the component: do not edit,\n"
             "# run board_select.py again to change the board.\n"]
    parts.append(defaults_of(args.board, "board"))
    mcu = resolve.chain(resolve.load("boards", args.board))["mcu"]
    lines = resolve.chip_settings(mcu, args.revision)
    if lines:
        parts.append(f"\n# What revision {args.revision or mcu['revision']} of the chip takes, from catalog/mcu/\n" + "\n".join(lines) + "\n")
    for module in args.module:
        parts.append("\n" + defaults_of(module, "module"))
    out = args.project / "sdkconfig.defaults.board"
    out.write_text("".join(parts))
    print(f"{out}: {args.board}" + (f" with {', '.join(args.module)}" if args.module else ""))
    sdkconfig = args.project / "sdkconfig"
    if sdkconfig.exists():
        if args.reset:
            sdkconfig.replace(args.project / "sdkconfig.old")
            print(f"{sdkconfig}: moved to sdkconfig.old, the new board's defaults will be read")
        else:
            print(f"{sdkconfig} exists: ESP-IDF reads the defaults only into a new one. Remove it (or --reset) for the board to change.")
    print("Now: idf.py build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
