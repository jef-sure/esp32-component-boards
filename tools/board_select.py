#!/usr/bin/env python3
"""Choose the board a project is built for: once, here.

Usage: board_select.py BOARD [--module MODULE ...] [--reset] PROJECT_DIR
       board_select.py BOARD BOARD ... PROJECT_DIR
       board_select.py host --as BOARD ... PROJECT_DIR

host is the computer: the linux target of ESP-IDF, a window of SDL2 as large as the display of the board named by
--as (src/board_host.c of the component). It is chosen like a board and built like one: idf.py -D BOARD=host build,
then the program build/host/<project>.elf runs on the computer.

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

Each file begins with the command that made it and the version of the component; when the component
changes, board_select.py --again PROJECT_DIR makes every such file of the project again the same way.
ESP-IDF reads the defaults only into a new sdkconfig, so an sdkconfig made before keeps what it had.

Several boards write PROJECT_DIR/sdkconfig.defaults.<BOARD> each, and PROJECT_DIR/CMakePresets.json: a preset
for each board, in the order named, with its build directory build/<BOARD>, its sdkconfig and its lock of components
there. ESP-IDF 6 reads the presets: idf.py build builds the first board, the current one, idf.py --preset <BOARD>
build another, and the extension of ESP-IDF for VS Code chooses one as a project configuration. ESP-IDF 5 does not
read them:

    idf.py -B build/<BOARD> -D SDKCONFIG=build/<BOARD>/sdkconfig -D BOARD=<BOARD> build

Both need a CMakeLists.txt that reads sdkconfig.defaults.${BOARD} when BOARD is given, as the skeleton of the page
does. A CMakePresets.json the command did not write is not touched.

The data is found beside this script (the component's catalog/), wherever the component
lies: a checkout beside the project or managed_components/jef-sure__boards/.
"""

import argparse
import json
import pathlib
import re
import shlex
import subprocess
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
    if revision and "revisions" not in resolve.load("mcu", mcu["target"]):
        raise SystemExit(f"{mcu['target']}: catalog/mcu describes no revisions of it, so --revision {revision} means nothing")
    try:
        lines = resolve.chip_settings(mcu, revision)
    except (resolve.Refused, ValueError) as err:
        options = resolve.load("mcu", mcu["target"])["revisions"]["options"]
        raise SystemExit(f"--revision {revision}: {err}; the options of {mcu['target']}: {', '.join(f'{n // 100}.{n % 100}' for n in options)}")
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


HOST = "host"
RECORD = "# board_select.py "  # the first line of a file it writes: the arguments that make it again
PRESETS = "CMakePresets.json"
VENDOR = "jef-sure/boards"  # the vendor map of CMake presets that marks the file as written here


def presets_text(project, boards, targets, command):
    """CMakePresets.json of the boards: one preset each, the first the board idf.py builds with no --preset."""
    path = project / PRESETS
    if path.exists() and VENDOR not in json.loads(path.read_text()).get("vendor", {}):
        raise SystemExit(f"{path}: written by someone else, so it is not touched: add the presets of {', '.join(boards)} to it, "
                         f"or remove it and run the command again")
    presets = [{"name": board, "displayName": title_of(board), "binaryDir": f"build/{board}",
                "cacheVariables": {"BOARD": board, "IDF_TARGET": target, "SDKCONFIG": f"build/{board}/sdkconfig"}} for board, target in zip(boards, targets)]
    return resolve.dump({"version": 3, "vendor": {VENDOR: {"made by": command}}, "configurePresets": presets}) + "\n"


def title_of(board):
    if board == HOST:
        return "the computer"
    try:
        return resolve.load("boards", board).get("title", board)
    except resolve.Refused:
        return board


def made_by(board, modules=(), revision=None, shows=None):
    """The first lines of a file: the command that made it, and the component it was made from."""
    words = [board, *(f"--module {module}" for module in modules), *([f"--revision {revision}"] if revision else []), *([f"--as {shows}"] if shows else [])]
    version = re.search(r'^version: "([^"]+)"', (ROOT / "idf_component.yml").read_text(), flags=re.M)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() if (ROOT / ".git").exists() else ""
    made = f"jef-sure/boards {version[1] if version else '?'}" + (f", commit {commit}" if commit else "")
    return f"{RECORD}{' '.join(words)}\n# from {made}: board_select.py --again PROJECT_DIR makes it again when the component changes\n"


def again(parser, project):
    """Every file of the project board_select.py wrote, made again by the command its first line keeps."""
    local = resolve.add_project(project)
    files = [path for path in sorted(project.glob("sdkconfig.defaults.*")) if path.read_text().startswith(RECORD)]
    if not files:
        raise SystemExit(f"{project}: no sdkconfig.defaults.* there says how it was made: choose the board again")
    for path in files:
        args = parser.parse_intermixed_args(shlex.split(path.read_text().splitlines()[0][len(RECORD):]) + [str(project)])
        board = args.names[0]
        text, target = host_text(local, args.shows) if board == HOST else defaults_text(project, local, board, args.module, args.revision)
        path.write_text(made_by(board, args.module, args.revision, args.shows) + text)
        print(f"{path}: {board}, {target}, again")
    print("An sdkconfig made before keeps what it had: ESP-IDF reads the defaults only into a new one. To take what changed,\n"
          "board_select.py BOARD --reset PROJECT_DIR for one board, or remove build/<BOARD>/sdkconfig of several.")
    return 0


def host_text(local, shows):
    """The defaults of the computer: the linux target, and the size of the display of the board it shows."""
    if not shows:
        raise SystemExit("host shows a board: name it with --as, as host --as jc8012p4a1c")
    path = local / "boards" / shows / "board.json"
    path = path if path.exists() else ROOT / "catalog" / "boards" / shows / "board.json"
    if not path.exists():
        raise SystemExit(f"{shows}: no such board in catalog/boards/ or in components/local-boards/boards/")
    primary = boards_gen.primary_shown(boards_gen.read_board(path))
    if not primary:
        raise SystemExit(f"{shows} has no pixel display for the computer to show")
    width, height, mm_w, mm_h = primary
    return (f"# The computer, chosen by tools/board_select.py of jef-sure/boards: a window as large as {shows}\n"
            "# Read before the project's own sdkconfig.defaults. Made from the data of the component: do not edit.\n"
            f'CONFIG_IDF_TARGET="linux"\nCONFIG_BOARD_SELECT_HOST=y\nCONFIG_BOARD_HOST_SHOWS="{shows}"\n'
            f"CONFIG_BOARD_HOST_WIDTH={width}\nCONFIG_BOARD_HOST_HEIGHT={height}\nCONFIG_BOARD_HOST_MM_W={mm_w}\nCONFIG_BOARD_HOST_MM_H={mm_h}\n"), "linux"


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
    parser.add_argument("--as", dest="shows", metavar="BOARD", help="for host: the board whose display the window of the computer has")
    parser.add_argument("--again", action="store_true", help="make every sdkconfig.defaults.* of the project again, by the command each was made with")
    args = parser.parse_intermixed_args()  # options may stand between the boards and the project, as board_select.py b --reset .
    if args.again:
        if len(args.names) != 1 or args.module or args.revision or args.reset or args.shows:
            parser.error("--again takes only the project's directory")
        return again(parser, pathlib.Path(args.names[0]))
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
        if len(set(boards)) != len(boards):
            raise SystemExit("a board named twice")
        texts, targets = {}, []
        for board in boards:
            text, target = host_text(local, args.shows) if board == HOST else defaults_text(project, local, board, [], None)
            texts[project / f"sdkconfig.defaults.{board}"] = made_by(board, shows=args.shows if board == HOST else None) + text
            targets.append(target)
        command = "board_select.py " + " ".join([*boards, *([f"--as {args.shows}"] if args.shows else []), "."])
        texts[project / PRESETS] = presets_text(project, boards, targets, command)
        for out, text in texts.items():
            out.write_text(text)
        for out, board, target in zip(texts, boards, targets):
            print(f"{out}: {board}, {target}")
        print(f"{project / PRESETS}: a preset for each, {boards[0]} first\n"
              f"ESP-IDF 6: idf.py build builds {boards[0]}, idf.py --preset <board> build another, each in build/<board>.\n"
              "ESP-IDF 5 does not read the presets:")
        for board in boards:
            print(f"  idf.py -B build/{board} -D SDKCONFIG=build/{board}/sdkconfig -D BOARD={board} build")
        return 0

    board = boards[0]
    if board == HOST:
        # the computer always stands beside a board of the project: a file and a build directory of its own
        if args.module:
            raise SystemExit("the computer carries no module")
        text, _ = host_text(local, args.shows)
        out = project / f"sdkconfig.defaults.{HOST}"
        out.write_text(made_by(HOST, shows=args.shows) + text)
        print(f"{out}: {HOST}, linux\nNow: idf.py -B build/{HOST} -D SDKCONFIG=build/{HOST}/sdkconfig -D BOARD={HOST} build, then build/{HOST}/<project>.elf")
        return 0
    sdkconfig = project / "sdkconfig"
    before = chosen(sdkconfig)
    if before and before != board and not args.reset:
        # a build would keep the old board: nothing is written, and the command that changes it is named
        raise SystemExit(f"{sdkconfig} is made for {before}: ESP-IDF reads the defaults only into a new one, so a build gives {before}.\n"
                         f"To change the board: board_select.py {board} --reset {project}")
    text, target = defaults_text(project, local, board, args.module, args.revision)
    out = project / "sdkconfig.defaults.board"
    out.write_text(made_by(board, args.module, args.revision) + text)
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
