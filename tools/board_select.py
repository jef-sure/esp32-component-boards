#!/usr/bin/env python3
"""Choose the boards a project is built for: once, here.

Usage: board_select.py BOARD [--module MODULE ...] [--revision R] [--current BOARD] PROJECT_DIR
       board_select.py BOARD BOARD ... [--current BOARD] PROJECT_DIR
       board_select.py host --as BOARD [--as BOARD ...] PROJECT_DIR
       board_select.py --current BOARD PROJECT_DIR
       board_select.py --again PROJECT_DIR

BOARD is a board of the catalog, or a board of the program: components/local-boards/boards/BOARD/board.json in the
project, whose glue is made there, beside its data. host is the computer: the linux target of ESP-IDF, a window of
SDL2 as large as the display of the board named by --as (src/board_host.c of the component). Each --as is a board of its
own, host_<BOARD>, so the computer showing the CYD and the computer showing another board build side by side; the program
build/host_<BOARD>/<project>.elf runs on the computer. A project of 0.0.7 named the computer host: --again renames its
files, once its CMakeLists.txt takes the computer by if(BOARD MATCHES "^host_").

Each board named gets PROJECT_DIR/sdkconfig.defaults.<BOARD>: the board's sdkconfig.defaults (its chip, its memory,
its flash, and the two lines that choose it, CONFIG_IDF_TARGET and CONFIG_BOARD_SELECT_<BOARD>=y), the lines of the
revision of its chip, and the defaults of every module named. One board or several, the project gets the same:
PROJECT_DIR/CMakePresets.json, a preset for each board of the project with its build directory build/<BOARD> and its
sdkconfig there, and the preset default, a copy of the preset of the current board (--current, else the first named).
A board the project had stays among the presets; a board is taken out by removing its file. Each board has its lock
of the components beside the project, dependencies.lock.<BOARD>, started as a copy of dependencies.lock when the
project has one.

ESP-IDF 6 reads the presets: idf.py build builds the current board, idf.py --preset <BOARD> build another, and the
extension of ESP-IDF for VS Code chooses one as a project configuration. Each board builds in a directory of its own,
so a new board is a new sdkconfig made from its defaults: no set-target, no menuconfig.
board_select.py --current BOARD PROJECT_DIR rewrites only default, so the boards keep their order, and the current board
of selection.json, so the page shows it. ESP-IDF 5 does not read the presets:

    idf.py -B build/<BOARD> -D SDKCONFIG=build/<BOARD>/sdkconfig -D BOARD=<BOARD> build

Both need a CMakeLists.txt that reads sdkconfig.defaults.${BOARD} when BOARD is given, as the skeleton of the page
does. A CMakePresets.json or a file of defaults this command did not write is not touched.

Each file begins with the command that made it and the version of the component; when the component changes,
board_select.py --again PROJECT_DIR makes every such file of the project again the same way, and the presets in their
order with their current board. The presets record the current board they were made with, and selection.json of the page
gets it too, so --again takes the current board of selection.json only when the page has changed it since; the first
time, the order of selection.json too. A file whose first line alone is the command, as the page writes it, is made in
full. ESP-IDF reads the defaults only into a new sdkconfig, so an
sdkconfig made before keeps what it had.

The data is found beside this script (the component's catalog/), wherever the component lies: a checkout beside the
project or managed_components/jef-sure__boards/.
"""

import argparse
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys

import boards_gen
import project_writer
import resolve

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "catalog"


def defaults_of(name, what):
    kind, file = ("boards", "board.json") if what == "board" else ("modules", "module.json")
    # a module --module takes is one set up by its own defaults; the page wires the others to pins of a board of the program
    known = ", ".join(sorted(p.parent.name for p in (DATA / kind).glob("*/sdkconfig.defaults"))) or "none of the catalog"
    if not (DATA / kind / name / file).exists():
        raise SystemExit(f"{name}: no such {what} in {DATA / kind} (--{what} takes {known})")
    defaults = DATA / kind / name / "sdkconfig.defaults"
    if not defaults.exists():
        raise SystemExit(f"{name}: --module takes {known}; this {what} is wired to pins of a board by the page, in a board of the "
                         f"program in components/local-boards/ that names it in modules")
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


HOST = "host"  # the computer: host_<BOARD> shows the display of BOARD
# the computer in the CMake of 0.0.7, which host_<BOARD> does not match
OLD_HOST_LINE = 'if(BOARD STREQUAL "host")'
NEW_HOST_LINE = 'if(BOARD MATCHES "^host_")'
# the start orientations of a display that are a turn of its glass, (x, y, swap), and the turn of the window that shows its
# screen upright, as measured with DGX 0.10.10: a finger pressed at a pixel of the window is at that pixel of the screen
HOST_TURNS = {("left-right", "top-bottom", False): 0, ("right-left", "bottom-top", False): 180,
              ("right-left", "top-bottom", True): 270, ("left-right", "bottom-top", True): 90}
HOST_BUS_LINES = {"spi": 1, "qspi": 4}  # the buses the window of DGX counts the time of
HOST_MAIN_STACK_WORDS = 16384  # 128 KB on the computer, as DGX asks of the task that makes its window
RECORD = "# board_select.py "  # the first line of a file it writes: the arguments that make it again
PRESETS = "CMakePresets.json"
VENDOR = "jef-sure/boards"  # the vendor map of CMake presets that marks the file as written here
DEFAULT = "default"  # the preset idf.py builds when none is named


def our_presets(project, boards):
    """The presets of the project when this command wrote them, None when there are none; refuses those of another."""
    path = project / PRESETS
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    if VENDOR not in doc.get("vendor", {}):
        raise SystemExit(f"{path}: written by someone else, so it is not touched: add the presets of {', '.join(boards)} to it, "
                         f"or remove it and run the command again")
    return doc


def with_current(doc, current):
    """The presets with default, the one idf.py builds when no preset is named: a copy of the preset of the current board,
    in the same build directory, so the boards keep their order and only default changes with the current one."""
    boards = [preset for preset in doc["configurePresets"] if preset["name"] != DEFAULT]
    chosen = next((preset for preset in boards if preset["name"] == current), None)
    if not chosen:
        raise SystemExit(f"--current {current}: not a board of {PRESETS} ({', '.join(preset['name'] for preset in boards)})")
    default = {**chosen, "name": DEFAULT, "displayName": f"The current board: {chosen['displayName']}"}
    return resolve.dump({**doc, "configurePresets": [*boards, default]}) + "\n"


def presets_text(project, boards, targets, current, command, follows=None):
    """CMakePresets.json of the boards: one preset each in the order named, and default for the current one. follows is
    the current board they are made with, which selection.json gets too: a page that names another later has changed it."""
    our_presets(project, boards)
    # Ninja, as idf.py takes it: a build directory CMake Tools of VS Code made with another generator stops idf.py there
    presets = [{"name": board, "displayName": title_of(board), "generator": "Ninja", "binaryDir": f"build/{board}",
                "cacheVariables": {"BOARD": board, "IDF_TARGET": target, "SDKCONFIG": f"build/{board}/sdkconfig"}} for board, target in zip(boards, targets)]
    made = {"made by": command, **({"follows": follows} if follows else {})}
    return with_current({"version": 3, "vendor": {VENDOR: made}, "configurePresets": presets}, current)


def seed_locks(project, boards):
    """The lock of the components of each board, dependencies.lock.<board>, starts as the lock the project had, so its
    versions carry over; then it is the component manager's file, and the lock of one board is not read any more."""
    root = project / "dependencies.lock"
    seeded = [board for board in boards if root.exists() and not (project / f"dependencies.lock.{board}").exists()]
    for board in seeded:
        shutil.copyfile(root, project / f"dependencies.lock.{board}")
    if seeded:
        print(f"{root}: copied to dependencies.lock.<board> for {', '.join(seeded)}; each board reads its own now, and this one is not read")


def is_host(board):
    return board.startswith(f"{HOST}_")


def shown_by(board):
    """The board whose display the computer host_<BOARD> shows."""
    return board[len(HOST) + 1:]


def check_host_cmake(project):
    """The CMake of 0.0.7 builds the computer only when BOARD is host: host_<BOARD> would build for the linux target
    with the drivers of a chip and fail. The line is the project's, so it is said, not changed."""
    cmake = project / "CMakeLists.txt"
    if cmake.exists() and OLD_HOST_LINE in cmake.read_text(errors="replace"):
        raise SystemExit(f"{cmake}: the computer is host_<board> since jef-sure/boards 0.1.0: replace {OLD_HOST_LINE} by "
                         f"{NEW_HOST_LINE} there, then run this again")


def title_of(board):
    if is_host(board):
        return f"the computer as {title_of(shown_by(board))}"
    try:
        return resolve.load("boards", board).get("title", board)
    except resolve.Refused:
        return board


def made_by(board, modules=(), revision=None):
    """The first lines of a file: the command that made it, and the component it was made from."""
    words = [board, *(f"--module {module}" for module in modules), *([f"--revision {revision}"] if revision else [])]
    # quoted in the repository, bare in the manifest the registry ships
    version = re.search(r"""^version:\s*["']?([^"'\s#]+)""", (ROOT / "idf_component.yml").read_text(), flags=re.M)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() if (ROOT / ".git").exists() else ""
    made = f"jef-sure/boards {version[1] if version else '?'}" + (f", commit {commit}" if commit else "")
    return f"{RECORD}{' '.join(words)}\n# from {made}: board_select.py --again PROJECT_DIR makes it again when the component changes\n"


def made_here(project):
    """The files of the project board_select.py wrote: those whose first line is its command. ESP-IDF's own files of a
    target, as sdkconfig.defaults.esp32p4, are not among them."""
    return [path for path in sorted(project.glob("sdkconfig.defaults.*")) if path.read_text(errors="replace").startswith(RECORD)]


def boards_of(project):
    """The boards of a project of several: those of the files board_select.py wrote, but the one board alone."""
    return [path.name.split(".", 2)[2] for path in made_here(project) if path.name != "sdkconfig.defaults.board"]


def again(parser, project):
    """Every file of the project board_select.py wrote, made again by the command its first line keeps."""
    local = resolve.add_project(project)
    files = made_here(project)
    if not files:
        raise SystemExit(f"{project}: no sdkconfig.defaults.* there says how it was made: choose the board again")
    # the CMake of the project takes the computer first: nothing is written before it can be built
    if any(name == HOST or is_host(name) for name in (path.name.split(".", 2)[2] for path in files)):
        check_host_cmake(project)
    targets = {}
    written = []
    renamed = {}
    for path in files:
        args = parser.parse_intermixed_args(shlex.split(path.read_text().splitlines()[0][len(RECORD):]) + [str(project)])
        board = args.names[0]
        named = path.name.split(".", 2)[2]
        if board == HOST:
            # a file of 0.0.7, host --as BOARD: the computer is host_<BOARD> now, its file and its lock with it
            if len(args.shows) != 1:
                raise SystemExit(f"{path}: its first line names the computer with no one board to show")
            board = f"{HOST}_{args.shows[0]}"
            if named == HOST:
                moved = project / f"sdkconfig.defaults.{board}"
                if moved.exists():
                    raise SystemExit(f"{path} and {moved}: the computer as {args.shows[0]} twice: remove {path}")
                lock, kept = project / f"dependencies.lock.{HOST}", project / f"dependencies.lock.{board}"
                if lock.exists() and not kept.exists():
                    lock.rename(kept)
                path.unlink()
                path, named, renamed[HOST] = moved, board, board
                print(f"{path}: the computer of {project} is {board} now; build/{HOST} can go")
        if named not in (board, "board"):
            # a copy of the file of another board would build that board under this name
            raise SystemExit(f"{path}: its first line makes {board}, its name says {named}: make it with board_select.py {named} {project}")
        text, target = host_text(local, shown_by(board)) if is_host(board) else defaults_text(project, local, board, args.module, args.revision)
        path.write_text(made_by(board, args.module, args.revision) + text)
        written.append(path)
        print(f"{path}: {board}, {target}, again")
        if path.name != "sdkconfig.defaults.board":
            targets[board] = target
    # a file named by its board is one of the boards of the presets, one of them alone too, as the page writes it
    presets = []
    if targets:
        boards, current = order_of(project, list(targets), renamed=renamed)
        command = "board_select.py --again ."  # the same wherever the project lies
        (project / PRESETS).write_text(presets_text(project, boards, [targets[board] for board in boards], current, command, current))
        presets = [project / PRESETS, *current_taken(project, current)]
        print(f"{project / PRESETS}: a preset for each, and default for the current one, {current}")
        seed_locks(project, boards)
    project_writer.keep_ours(project, [*written, *presets])
    print("An sdkconfig made before keeps what it had: ESP-IDF reads the defaults only into a new one. To take what changed,\n"
          "remove build/<BOARD>/sdkconfig of the board.")
    return 0


def order_of(project, boards, named=(), renamed=None):
    """The order of the boards of a project and the current one. The presets this command wrote are the project's: their
    order and default stand, unless selection.json of the page names another current board than the one they were made
    with. Without them, selection.json of the page orders. Then the boards of selection.json the presets lack, those just
    named in the order named, and the rest by name."""
    chosen = project / "selection.json"
    saved = json.loads(chosen.read_text()) if chosen.exists() else {}
    # a board --again renamed, as host of 0.0.7, keeps its place and its being current
    new = (lambda board: (renamed or {}).get(board, board))
    listed = [new(entry.get("board")) for entry in saved.get("boards", [])]
    picked = current = new(saved.get("current"))
    presets = project / PRESETS
    doc = json.loads(presets.read_text()) if presets.exists() else {}
    if VENDOR in doc.get("vendor", {}):
        made = doc["configurePresets"]
        listed = [new(preset["name"]) for preset in made if preset["name"] != DEFAULT] + listed
        default = new(next((preset["cacheVariables"]["BOARD"] for preset in made if preset["name"] == DEFAULT), None))
        # presets with no record were made with no selection.json: the page wrote its current board since
        followed = new(doc["vendor"][VENDOR].get("follows"))
        current = picked if picked and picked != followed else default
    order = list(dict.fromkeys(board for board in listed if board in boards))
    order += [board for board in named if board in boards and board not in order]
    order += sorted(board for board in boards if board not in order)
    return order, current if current in order else order[0]


def current_taken(project, current):
    """selection.json of the page names the current board the presets are made with, so the page shows it and a change
    there is the page's. Returns the file when it changed: as the page writes it, by four spaces."""
    chosen = project / "selection.json"
    try:
        saved = json.loads(chosen.read_text()) if chosen.is_file() else None
    except ValueError:
        return []
    if not isinstance(saved, dict) or saved.get("current") == current:
        return []
    chosen.write_text(json.dumps({**saved, "current": current}, indent=4, ensure_ascii=False) + "\n")
    return [chosen]


def host_text(local, shows):
    """The defaults of the computer: the linux target, and the size of the display of the board it shows."""
    if not shows:
        raise SystemExit("host shows a board: name it with --as, as host --as jc8012p4a1c")
    path = local / "boards" / shows / "board.json"
    path = path if path.exists() else ROOT / "catalog" / "boards" / shows / "board.json"
    if not path.exists():
        raise SystemExit(f"{shows}: no such board in catalog/boards/ or in components/local-boards/boards/")
    board = boards_gen.read_board(path)
    primary = boards_gen.primary_shown(board)
    if not primary:
        raise SystemExit(f"{shows} has no pixel display for the computer to show")
    width, height, mm_w, mm_h = primary
    return (f"# The computer, chosen by tools/board_select.py of jef-sure/boards: a window as large as {shows}\n"
            "# Read before the project's own sdkconfig.defaults. Made from the data of the component: do not edit.\n"
            f'CONFIG_IDF_TARGET="linux"\nCONFIG_BOARD_SELECT_HOST=y\nCONFIG_BOARD_HOST_SHOWS="{shows}"\n'
            f"CONFIG_BOARD_HOST_WIDTH={width}\nCONFIG_BOARD_HOST_HEIGHT={height}\nCONFIG_BOARD_HOST_MM_W={mm_w}\nCONFIG_BOARD_HOST_MM_H={mm_h}\n"
            + host_window(board)
            + f'CONFIG_BOARD_HOST_BUTTONS="{",".join(button["name"] for button in board.get("buttons") or [])}"\n'
            + "# the window of DGX needs 48 KB of stack left in the task that starts the display: app_main's, in words of 8 bytes here\n"
            f"CONFIG_ESP_MAIN_TASK_STACK_SIZE={HOST_MAIN_STACK_WORDS}\n"), "linux"


def host_window(board):
    """The window of the computer as the display of the board: its glass turned as the board is held and the screen at the
    orientation it starts with there, the bus whose time the title tells, the depth of color. A display that starts
    mirrored, or a group of two, is shown as it is shown on the board, not turned."""
    display = board.get("display")
    if board.get("display_groups") or not display:
        return ""
    start = display["original_orientation"]
    turn = HOST_TURNS.get((start["x"], start["y"], start.get("swap", False)))
    kind, own = display["bus"]["bus"].split(".")
    bus = (board.get("buses", {}).get(kind) or {}).get(own) or {}
    lines = [f"CONFIG_BOARD_HOST_COLOR_BITS={display['depth_bits']}"]
    if turn is not None:
        lines += [f"CONFIG_BOARD_HOST_DIR_X={1 if start['x'] == 'left-right' else -1}", f"CONFIG_BOARD_HOST_DIR_Y={1 if start['y'] == 'top-bottom' else -1}",
                  f"CONFIG_BOARD_HOST_SWAP={int(start.get('swap', False))}", f"CONFIG_BOARD_HOST_TURN={turn}"]
    if kind in HOST_BUS_LINES and bus.get("hz"):
        lines += [f"CONFIG_BOARD_HOST_BUS_HZ={bus['hz']}", f"CONFIG_BOARD_HOST_BUS_LINES={HOST_BUS_LINES[kind]}"]
    return "".join(f"{line}\n" for line in lines)


def target_of(path):
    """The chip of a file of defaults this command wrote: its line CONFIG_IDF_TARGET."""
    found = re.search(r'^CONFIG_IDF_TARGET="(\w+)"$', path.read_text(), flags=re.M)
    if not found:
        raise SystemExit(f"{path}: no CONFIG_IDF_TARGET in it: make it again, board_select.py --again {path.parent}")
    return found[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+", metavar="BOARD ... PROJECT_DIR", help="one board or several, each a directory name in catalog/boards/ or in components/local-boards/boards/ of the project, then the project's directory")
    parser.add_argument("--module", action="append", default=[], help="a module the board carries (its directory name in catalog/modules/); may repeat; one board only")
    parser.add_argument("--revision", help="the revision of the chip, when it is not the one the data of the board names: 3.1; one board only")
    parser.add_argument("--as", dest="shows", metavar="BOARD", action="append", default=[],
                        help="for host: a board whose display a window of the computer has, the board host_<BOARD>; may repeat")
    parser.add_argument("--again", action="store_true", help="make every sdkconfig.defaults.* of the project again, by the command each was made with")
    parser.add_argument("--current", metavar="BOARD", help="the board idf.py builds when no preset is named; alone with the project, it changes only that")
    args = parser.parse_intermixed_args()  # options may stand between the boards and the project, as board_select.py b --module m .
    if args.again:
        if len(args.names) != 1 or args.module or args.revision or args.shows or args.current:
            parser.error("--again takes only the project's directory")
        return again(parser, pathlib.Path(args.names[0]))
    if args.current and len(args.names) == 1:
        project = pathlib.Path(args.names[0])
        doc = our_presets(project, [args.current])
        if doc is None:
            raise SystemExit(f"{project}: no {PRESETS} there: name the boards, board_select.py BOARD ... --current {args.current} {project}")
        # the page shows it as current: a later change of it on the page is the page's
        doc["vendor"][VENDOR]["follows"] = args.current
        (project / PRESETS).write_text(with_current(doc, args.current))
        project_writer.keep_ours(project, [project / PRESETS, *current_taken(project, args.current)])
        print(f"{project / PRESETS}: {args.current} is the current board, idf.py build builds it")
        return 0
    if len(args.names) < 2:
        parser.error("name a board and the project's directory")
    *boards, project = args.names
    project = pathlib.Path(project)
    # host --as A --as B names the computers host_A and host_B
    if HOST in boards:
        if not args.shows:
            raise SystemExit("host shows a board: name it with --as, as host --as jc8012p4a1c")
        at = boards.index(HOST)
        boards[at:at + 1] = [f"{HOST}_{shown}" for shown in args.shows]
    elif args.shows:
        raise SystemExit("--as is for host: board_select.py host --as BOARD PROJECT_DIR")
    if not (project / "CMakeLists.txt").exists():
        raise SystemExit(f"{project}: no CMakeLists.txt there, is it a project?")
    if len(set(boards)) != len(boards):
        raise SystemExit("a board named twice")
    if len(boards) > 1 and (args.module or args.revision):
        raise SystemExit("--module and --revision are for one board: name the others in a command of their own")
    if any(is_host(board) for board in boards):
        if args.module or args.revision:
            raise SystemExit("the computer carries no module and has no revision")
        check_host_cmake(project)
    if args.current and args.current not in boards:
        raise SystemExit(f"--current {args.current}: one of the boards named")
    our_presets(project, boards)
    local = resolve.add_project(project)

    # each board named gets its file of defaults; the boards the project had stay, so the presets are of all of them
    texts = {}
    for board in boards:
        text, _ = host_text(local, shown_by(board)) if is_host(board) else defaults_text(project, local, board, args.module, args.revision)
        texts[project / f"sdkconfig.defaults.{board}"] = made_by(board, args.module, args.revision) + text
    if any(not path.read_text().startswith(RECORD) for path in texts if path.exists()):
        raise SystemExit(f"{', '.join(str(path) for path in texts if path.exists() and not path.read_text().startswith(RECORD))}: not written by this command, so not replaced")
    for out, text in texts.items():
        out.write_text(text)
        print(f"{out}: {out.name.split('.', 2)[2]}, {target_of(out)}")
    every, _ = order_of(project, boards_of(project), boards)
    current = args.current or boards[0]
    command = "board_select.py --again ."
    (project / PRESETS).write_text(presets_text(project, every, [target_of(project / f"sdkconfig.defaults.{board}") for board in every], current, command, current))
    project_writer.keep_ours(project, [*texts, project / PRESETS, *current_taken(project, current)])
    seed_locks(project, every)
    if (project / "sdkconfig.defaults.board").exists():
        print(f"{project / 'sdkconfig.defaults.board'}: the file of one board as it was before the presets; the CMakeLists.txt of the "
              "skeleton reads sdkconfig.defaults.<board> by a preset, take its lines")
    print(f"{project / PRESETS}: a preset for each board of the project ({', '.join(every)}), and default for the current one, {current}\n"
          f"ESP-IDF 6: idf.py build builds {current} in build/{current}, idf.py --preset <board> build another;\n"
          f"board_select.py --current <board> {project} makes another current. ESP-IDF 5 does not read the presets:\n"
          f"  idf.py -B build/{current} -D SDKCONFIG=build/{current}/sdkconfig -D BOARD={current} build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
