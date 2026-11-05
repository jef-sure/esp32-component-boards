#!/usr/bin/env python3
"""A new project on a board of the catalog, chosen by hand: the files the page writes, from editor/skeleton/.

Usage: board_project.py DIR --board BOARD [--module MODULE ...] [--name NAME]
       board_project.py DIR --selection SELECTION.json [--name NAME]

DIR is empty or holds only what a repository starts with (.git, .gitignore, README, LICENSE); nothing in it is
replaced. The files are those of editor/skeleton/files.json, filled as the page fills them, and selection.json.
The component comes from git at the commit of this checkout. No solver runs: selection.json has no answers, and a
kit the page chose is taken back with --selection. Then, in DIR, as its README says:

    idf.py reconfigure
    python3 managed_components/jef-sure__boards/tools/board_select.py --again .
    idf.py build
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import boards_gen  # noqa: E402
import resolve  # noqa: E402

EDITOR = ROOT / "editor"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")  # as a name of the schema: a board of the program is <project>_<board>
REPOSITORY_ONLY = re.compile(r"^(\.git|\.gitignore|\.gitattributes|README.*|LICENSE.*)$", re.IGNORECASE)
SELECTION = "selection.json"
BY_HAND = "chosen by hand with tools/board_project.py: no solver ran"


def commit():
    """The commit of this checkout, as the server of the model reports it to the page; main without git."""
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "main"


def wires(board, modules):
    """The lines of each module to the bus of the board it is on, as a table of the README."""
    rows = []
    for module in modules:
        for kind in boards_gen.bus_kinds(module):
            named = (board.get("buses") or {}).get(kind) or {}
            if not named:
                raise SystemExit(f"{board['name']} has no {kind} bus for {module['name']}")
            own, lines = sorted(named.items())[0]
            rows += [f"| {module['title']} | {line.upper()} | GPIO {pin} of {kind}.{own} |" for line, pin in sorted(lines.items()) if isinstance(pin, int) and line != "hz"]
    return "\n".join(["| what | line | to |", "|---|---|---|", *rows]) if rows else "None: the board has it all."


def libraries(parts):
    """The libraries the glue starts, each with the version its adapter asks and the devices it starts."""
    seen = {}
    for part in parts:
        for device, record, also in boards_gen.started_devices(part):
            for used in (record, *also):
                key = (f"{used['owner']}/{used['name']}", (used.get("adapter") or {}).get("version", ""))
                seen.setdefault(key, set()).add(device["name"])
    return [{"name": name, "version": version, "devices": sorted(devices)} for (name, version), devices in sorted(seen.items())]


def libraries_text(started):
    """As the page lists the libraries that come with the board."""
    rows = [f"- `{item['name']}` {item['version']}".rstrip() + f", for {', '.join(item['devices'])}: comes with the board, which starts it." for item in started]
    return "\n".join(rows) or "None."


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dir", type=pathlib.Path)
    parser.add_argument("--board")
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--selection", type=pathlib.Path, help="selection.json the page wrote: its board and modules")
    parser.add_argument("--name", help="the name of the project (lowercase letters, digits and _); the name of DIR by default")
    args = parser.parse_args()
    if bool(args.board) == bool(args.selection):
        parser.error("--board or --selection, one of them")
    if args.selection:
        chosen = json.loads(args.selection.read_text())
        # the current kit of several; a selection.json before format 3 held one kit at its top
        kit = next((item for item in chosen["boards"] if item["board"] == chosen.get("current")), chosen["boards"][0]) if "boards" in chosen else chosen
        args.board, args.module = kit.get("base", kit["board"]), [module["name"] for module in kit.get("modules") or ()]
    name = args.name or args.dir.resolve().name
    if not NAME.match(name):
        raise SystemExit(f"{name}: a project name is a lowercase letter, then lowercase letters, digits and _: give one with --name")
    if args.dir.exists() and not all(REPOSITORY_ONLY.match(path.name) for path in args.dir.iterdir()):
        raise SystemExit(f"{args.dir}: not empty: nothing is written there")
    try:
        board = boards_gen.read_board(ROOT / "catalog" / "boards" / args.board / "board.json")
        modules = [boards_gen.read_board(ROOT / "catalog" / "modules" / module / "module.json") for module in args.module]
    except (OSError, ValueError, resolve.Refused) as err:
        raise SystemExit(f"{err}")
    parts = [f"- {board['title']}", *(f"- 1 x {module['title']}, on {', '.join(boards_gen.bus_kinds(module)).upper()}" for module in modules)]
    started = libraries([board, *modules])
    # the section of the kit in the README, as the page writes one for each kit
    section = "\n".join([f"## {board['title']}: `{args.board}`", "", "### What it takes", "", *parts, "", "### The wires", "", wires(board, modules), "",
                         "### The libraries", "", libraries_text(started)])
    fill = {
        "@NAME@": name,
        "@TITLE@": name,
        "@KITS@": section,
        "@CURRENT@": args.board,
        "@DEPENDENCIES@": "",
        "@COMPONENT_VERSION@": commit(),
    }
    files = {}
    for source, target in json.loads((EDITOR / "skeleton" / "files.json").read_text())["files"]:
        text = (EDITOR / source).read_text()
        for mark, value in fill.items():
            text = text.replace(mark, value)
        files[target] = text
    selection = {"format": "jef-sure/boards", "format_version": 3, "name": name, "currency": "EUR", "answers": {},
                 "boards": [{"board": args.board,
                             "modules": [{"name": module["name"], "count": 1, "on": ", ".join(boards_gen.bus_kinds(module))} for module in modules],
                             "libraries": [{"name": item["name"], "version": item["version"]} for item in started],
                             "says": [{"level": "note", "text": BY_HAND}]}],
                 "current": args.board, "others": [], "rejected": []}
    files[SELECTION] = json.dumps(selection, indent=4) + "\n"
    # the first line is the command that makes the defaults of the board, as the page writes it: board_select.py --again does
    module_args = "".join(f" --module {module}" for module in args.module)
    files[f"sdkconfig.defaults.{args.board}"] = f"# board_select.py {args.board}{module_args}\n# board_project.py wrote this line only: board_select.py --again . makes the defaults of the board.\n"
    for target in files:
        if (args.dir / target).exists():
            raise SystemExit(f"{args.dir / target}: there already: nothing is written")
    for target, text in files.items():
        path = args.dir / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"{path}: written")
    print(f"Now, in {args.dir}: idf.py reconfigure, then\n    python3 managed_components/jef-sure__boards/tools/board_select.py --again .\nand idf.py build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
