#!/usr/bin/env python3
"""Choose the board a project is built for: once, here.

Usage: board_select.py BOARD [--module MODULE ...] [--reset] PROJECT_DIR
       board_select.py BOARD BOARD ... PROJECT_DIR

BOARD is a board of the catalog, or a board of the program: components/local-boards/boards/BOARD/board.json
in the project. The glue of a board of the program is made there, beside its data.

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
old one (--reset does, keeping a copy as sdkconfig.old). Without --reset a change of the board
writes nothing and fails: a build would give the old board. A build directory keeps the target
of its chip in its CMake cache, so a change of the chip takes idf.py set-target, which the
command then names.

Several boards write PROJECT_DIR/sdkconfig.defaults.<BOARD> each, and each is built in a
directory of its own, its sdkconfig and its lock of components there:

    idf.py -B build-<BOARD> -D SDKCONFIG=build-<BOARD>/sdkconfig -D BOARD=<BOARD> build

with a CMakeLists.txt that reads sdkconfig.defaults.${BOARD} when BOARD is given, as the
skeleton of the page does.

The data is found beside this script (the component's catalog/), wherever the component
lies: a checkout beside the project or managed_components/jef-sure__boards/.
"""

import argparse
import pathlib
import re
import sys

import boards_gen
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


def local_defaults(local, name):
    """The sdkconfig.defaults of a board of the program: its own, or the one of the board it extends with the choice changed."""
    own = local / "boards" / name / "sdkconfig.defaults"
    if own.exists():
        return own.read_text()
    base = resolve.load("boards", name).get("extends")
    if not base:
        raise SystemExit(f"{own}: write it, the board extends nothing to take it from")
    return re.sub(r"^CONFIG_BOARD_SELECT_\w+=y$", f"CONFIG_BOARD_SELECT_{name.upper()}=y", defaults_of(base, "board"), flags=re.M)


def defaults_text(project, local, board, modules, revision):
    """The defaults of one board of the project: its own, the lines of the revision of its chip, those of its modules."""
    parts = [f"# The board of this project, chosen by tools/board_select.py of jef-sure/boards: {board}"
             + (f", with {', '.join(modules)}" if modules else "")
             + "\n# Read before the project's own sdkconfig.defaults. Made from the data of the component: do not edit,\n"
             "# run board_select.py again to change the board.\n"]
    if (local / "boards" / board / "board.json").exists():
        boards_gen.write_local(local)
        parts.append(local_defaults(local, board))
    else:
        parts.append(defaults_of(board, "board"))
    mcu = resolve.chain(resolve.load("boards", board))["mcu"]
    lines = resolve.chip_settings(mcu, revision)
    if lines:
        parts.append(f"\n# What revision {revision or mcu['revision']} of the chip takes, from catalog/mcu/\n" + "\n".join(lines) + "\n")
    buses = resolve.chain(resolve.load("boards", board)).get("buses") or {}
    for module in modules:
        text = defaults_of(module, "module")
        missing = [kind for kind in boards_gen.bus_kinds(resolve.load("modules", module)) if kind not in buses]
        if missing:
            # its glue would find no bus to sit on, and the module would not start
            raise SystemExit(f"{module} sits on {', '.join(missing)}, and {board} opens no such bus to a module")
        parts.append("\n" + text)
    return "".join(parts), mcu["target"]


def chosen(sdkconfig):
    """The board an sdkconfig was made for, or None."""
    found = re.search(r"^CONFIG_BOARD_SELECT_(\w+)=y$", sdkconfig.read_text(), flags=re.M) if sdkconfig.exists() else None
    return found[1].lower() if found and found[1] != "NONE" else None


def cached_target(project):
    """The target a build directory keeps in its CMake cache, or None: it is read before any defaults."""
    cache = project / "build" / "CMakeCache.txt"
    found = re.search(r"^IDF_TARGET:STRING=(\w+)$", cache.read_text(), flags=re.M) if cache.exists() else None
    return found[1] if found else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+", metavar="BOARD ... PROJECT_DIR", help="one board or several, each a directory name in catalog/boards/ or in components/local-boards/boards/ of the project, then the project's directory")
    parser.add_argument("--module", action="append", default=[], help="a module the board carries (its directory name in catalog/modules/); may repeat; one board only")
    parser.add_argument("--revision", help="the revision of the chip, when it is not the one the data of the board names: 3.1")
    parser.add_argument("--reset", action="store_true", help="move the project's sdkconfig aside, so the new board's defaults are read")
    args = parser.parse_intermixed_args()  # options may stand between the boards and the project, as board_select.py b --reset .
    if len(args.names) < 2:
        parser.error("name a board and the project's directory")
    *boards, project = args.names
    project = pathlib.Path(project)
    if not (project / "CMakeLists.txt").exists():
        raise SystemExit(f"{project}: no CMakeLists.txt there, is it a project?")
    if len(boards) > 1 and (args.module or args.revision or args.reset):
        raise SystemExit("--module, --revision and --reset are for one board; several boards each take their own build directory")
    local = resolve.add_project(project)

    if len(boards) > 1:
        for board in boards:
            text, target = defaults_text(project, local, board, [], None)
            out = project / f"sdkconfig.defaults.{board}"
            out.write_text(text)
            print(f"{out}: {board}, {target}")
        print("Each board builds in a directory of its own:")
        for board in boards:
            print(f"  idf.py -B build-{board} -D SDKCONFIG=build-{board}/sdkconfig -D BOARD={board} build")
        return 0

    board = boards[0]
    sdkconfig = project / "sdkconfig"
    before = chosen(sdkconfig)
    if before and before != board and not args.reset:
        # a build would keep the old board: nothing is written, and the command that changes it is named
        raise SystemExit(f"{sdkconfig} is made for {before}: ESP-IDF reads the defaults only into a new one, so a build gives {before}.\n"
                         f"To change the board: board_select.py {board} --reset {project}")
    text, target = defaults_text(project, local, board, args.module, args.revision)
    out = project / "sdkconfig.defaults.board"
    out.write_text(text)
    print(f"{out}: {board}" + (f" with {', '.join(args.module)}" if args.module else ""))
    if sdkconfig.exists() and args.reset:
        sdkconfig.replace(project / "sdkconfig.old")
        print(f"{sdkconfig}: moved to sdkconfig.old, the new board's defaults will be read")
    cached = cached_target(project)
    if cached and cached != target:
        # the cache of the build directory names the old chip, and it is read before the defaults
        print(f"Now: idf.py set-target {target}, then idf.py build (build/ is made for {cached})")
    else:
        # the rules of the manifest are read when a project is configured: a build of another board keeps that board's dependencies
        print("Now: idf.py reconfigure build" if (project / "build").exists() else "Now: idf.py build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
