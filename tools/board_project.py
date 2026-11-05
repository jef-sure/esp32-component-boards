#!/usr/bin/env python3
"""A new project on a board of the catalog, chosen by hand: the files the page writes, from editor/skeleton/.

Usage: board_project.py DIR --board BOARD [--module MODULE ...] [--name NAME]
       board_project.py DIR --selection SELECTION.json [--name NAME]

DIR is empty or holds only what a repository starts with (.git, .gitignore, README, LICENSE); nothing in it is
replaced. The files are those of editor/skeleton/files.json, filled as the page fills them, and selection.json.
The component comes as this copy came: from git at its commit, or from the registry at its version. No solver runs: --module takes a module that
board_select.py sets up by its defaults, as the 2004 on its I2C. A kit the page chose is taken back with --selection,
its answers too; a kit wired to pins by the page has a board of the program, which is taken from the folder of that
selection.json under the name of the new project. Then, in DIR, as its README says:

    idf.py reconfigure
    python3 managed_components/jef-sure__boards/tools/board_select.py --again .
    idf.py build
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import boards_gen  # noqa: E402
import project_writer  # noqa: E402
import resolve  # noqa: E402

EDITOR = ROOT / "editor"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")  # as a name of the schema: a board of the program is <project>_<board>
REPOSITORY_ONLY = re.compile(r"^(\.git|\.gitignore|\.gitattributes|README.*|LICENSE.*)$", re.IGNORECASE)
SELECTION = "selection.json"
BY_HAND = "chosen by hand with tools/board_project.py: no solver ran"


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


def program_wires(board, raw):
    """The lines of each module of a board of the program to the board, from its data, as a table of the README."""
    rows = []
    for use, entry in (raw.get("modules") or {}).items():
        title = resolve.load("modules", entry["module"]).get("title", entry["module"]) if "module" in entry else use
        for bus, extra in (entry.get("on") or {}).items():
            kind, own = bus.split(".", 1)
            lines = {**((board.get("buses") or {}).get(kind) or {}).get(own, {}), **(extra or {})}
            for line, pin in sorted(lines.items()):
                pin = pin.get("gpio") if isinstance(pin, dict) else pin
                if isinstance(pin, int) and line != "hz":
                    rows.append(f"| {title} | {line.upper()} | GPIO {pin} of {bus} |")
        rows += [f"| {title} | {line.upper()} | GPIO {pin} |" for line, pin in sorted((entry.get("pins") or {}).items()) if isinstance(pin, int)]
    return "\n".join(["| what | line | to |", "|---|---|---|", *rows]) if rows else "None: the board has it all."


def dependency_of(name, version):
    """The line of main/idf_component.yml for a library the program calls itself, as the page writes it."""
    record = ROOT / "catalog" / "libraries" / "esp-idf" / name / "library.json"
    found = json.loads(record.read_text()) if record.is_file() else {}
    if any(way.get("via") == "registry" for way in found.get("install", [])):
        return f'  {name}: "^{version}"'
    return f"  {name}:\n    git: {found.get('url', '')}"


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
    chosen, kit, raw = {}, None, None
    if args.selection:
        chosen = json.loads(args.selection.read_text())
        # the current kit of several; a selection.json before format 3 held one kit at its top
        kit = next((item for item in chosen["boards"] if item["board"] == chosen.get("current")), chosen["boards"][0]) if "boards" in chosen else chosen
        args.board, args.module = kit.get("base", kit["board"]), [module["name"] for module in kit.get("modules") or ()]
        if kit.get("base"):
            # a kit the page wired to pins: its board of the program lies beside the selection.json
            source = args.selection.parent / "components" / "local-boards" / "boards" / kit["board"] / "board.json"
            if not source.is_file():
                raise SystemExit(f"{source}: not there: --selection takes the selection.json of a project folder, with its components/local-boards")
            raw, args.module = json.loads(source.read_text()), []
    unwired = [module for module in args.module if not (ROOT / "catalog" / "modules" / module / "sdkconfig.defaults").is_file()]
    if unwired:
        raise SystemExit(f"{', '.join(unwired)}: no module of the catalog is set up by defaults of its own; the page wires modules to pins "
                         "of the board: choose the kit there, or take the project it wrote with --selection DIR/selection.json")
    name = args.name or args.dir.resolve().name
    if not NAME.match(name):
        raise SystemExit(f"{name}: a project name is a lowercase letter, then lowercase letters, digits and _: give one with --name")
    if args.dir.exists() and not all(REPOSITORY_ONLY.match(path.name) for path in args.dir.iterdir()):
        raise SystemExit(f"{args.dir}: not empty: nothing is written there")
    named = f"{name}_{args.board}" if raw else args.board
    if raw and (ROOT / "catalog" / "boards" / named).exists():
        raise SystemExit(f"the catalog has a board {named}: give the project another name")
    try:
        board = boards_gen.read_board(ROOT / "catalog" / "boards" / args.board / "board.json")
        modules = [boards_gen.read_board(ROOT / "catalog" / "modules" / module / "module.json") for module in args.module]
        program = boards_gen.read_board(resolve.add_project(args.selection.parent) / "boards" / kit["board"] / "board.json") if raw else None
    except (OSError, ValueError, resolve.Refused) as err:
        raise SystemExit(f"{err}")
    if raw:
        # the libraries the page listed for the kit: those the glue starts come with the board, the program names the rest
        glue = {f"{record['owner']}/{record['name']}" for _, record, _ in boards_gen.started_devices(program)}
        parts = [f"- {board['title']}", *(f"- {item.get('count', 1)} x {resolve.load('modules', item['name']).get('title', item['name'])}, on {item.get('on', '').upper()}" for item in kit["modules"]),
                 *(f"- {line['text']}" for line in kit.get("says", []) if line.get("level") == "do")]
        started = [item for item in kit.get("libraries", []) if item["name"] in glue]
        own = [item for item in kit.get("libraries", []) if item["name"] not in glue]
        library_lines = [f"- `{item['name']}` {item['version']}: comes with the board, which starts it." for item in started] + \
                        [f"- `{item['name']}` {item['version']}: the program calls it, main/idf_component.yml names it." for item in own]
        section = "\n".join([f"## {raw.get('title', board['title'])}: `{named}`", "", "### What it takes", "", *parts, "", "### The wires", "", program_wires(program, raw), "",
                             "### The libraries", "", "\n".join(library_lines) or "None."])
        dependencies = "\n".join(dependency_of(item["name"], item["version"]) for item in own)
    else:
        parts = [f"- {board['title']}", *(f"- 1 x {module['title']}, on {', '.join(boards_gen.bus_kinds(module)).upper()}" for module in modules)]
        started = libraries([board, *modules])
        # the section of the kit in the README, as the page writes one for each kit
        section = "\n".join([f"## {board['title']}: `{args.board}`", "", "### What it takes", "", *parts, "", "### The wires", "", wires(board, modules), "",
                             "### The libraries", "", libraries_text(started)])
        dependencies = ""
    fill = {
        "@NAME@": name,
        "@TITLE@": name,
        "@KITS@": section,
        "@CURRENT@": named,
        "@DEPENDENCIES@": dependencies,
        "@COMPONENT@": project_writer.component_lines(project_writer.component_source()),
    }
    files = {}
    for source, target in json.loads((EDITOR / "skeleton" / "files.json").read_text())["files"]:
        text = (EDITOR / source).read_text()
        for mark, value in fill.items():
            text = text.replace(mark, value)
        files[target] = text
    entry = {**kit, "board": named} if raw else {"board": args.board,
                                                  "modules": [{"name": module["name"], "count": 1, "on": ", ".join(boards_gen.bus_kinds(module))} for module in modules],
                                                  "libraries": [{"name": item["name"], "version": item["version"]} for item in started],
                                                  "says": [{"level": "note", "text": BY_HAND}]}
    selection = {"format": "jef-sure/boards", "format_version": 3, "name": name, "currency": chosen.get("currency", "EUR"), "answers": chosen.get("answers", {}),
                 "boards": [entry], "current": named, "others": [], "rejected": []}
    files[SELECTION] = json.dumps(selection, indent=4) + "\n"
    if raw:
        files[f"components/local-boards/boards/{named}/board.json"] = resolve.dump({**raw, "name": named}) + "\n"
    # the first line is the command that makes the defaults of the board, as the page writes it: board_select.py --again does
    module_args = "".join(f" --module {module}" for module in args.module)
    files[f"sdkconfig.defaults.{named}"] = f"# board_select.py {named}{module_args}\n# board_project.py wrote this line only: board_select.py --again . makes the defaults of the board.\n"
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
