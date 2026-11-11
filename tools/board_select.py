#!/usr/bin/env python3
"""Choose the boards a project is built for: once, here.

Usage: board_select.py BOARD [--module MODULE ...] [--revision R] [--current BOARD] PROJECT_DIR
       board_select.py BOARD BOARD ... [--current BOARD] PROJECT_DIR
       board_select.py host --as BOARD [--as BOARD ...] PROJECT_DIR
       board_select.py --current BOARD PROJECT_DIR
       board_select.py --again PROJECT_DIR
       board_select.py --keep PROJECT_DIR
       board_select.py --auto-keep BOARD PROJECT_DIR

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
sdkconfig beside its defaults, PROJECT_DIR/sdkconfig.<BOARD>, and the preset default, a copy of the preset of the current board (--current, else the first named).
A board the project had stays among the presets; a board is taken out by removing its file. Each board has its lock
of the components beside the project, dependencies.lock.<BOARD>, started as a copy of dependencies.lock when the
project has one.

ESP-IDF 6 reads the presets: idf.py build builds the current board, idf.py --preset <BOARD> build another, and the
extension of ESP-IDF for VS Code chooses one as a project configuration. Each board builds in a directory of its own,
so a new board is a new sdkconfig made from its defaults: no set-target, no menuconfig.
board_select.py --current BOARD PROJECT_DIR rewrites only default, so the boards keep their order, and the current board
of selection.json, so the page shows it. ESP-IDF 5 does not read the presets:

    idf.py -B build/<BOARD> -D SDKCONFIG=sdkconfig.<BOARD> -D BOARD=<BOARD> build

Both need a CMakeLists.txt that reads sdkconfig.defaults.${BOARD} when BOARD is given, as the skeleton of the page
does. A CMakePresets.json or a file of defaults this command did not write is not touched.

Each file begins with the command that made it and the version of the component; when the component changes,
board_select.py --again PROJECT_DIR makes every such file of the project again the same way, and the presets in their
order with their current board. The presets record the current board they were made with, and selection.json of the page
gets it too, so --again takes the current board of selection.json only when the page has changed it since; the first
time, the order of selection.json too. A file whose first line alone is the command, as the page writes it, is made in
full. ESP-IDF reads the defaults only into a new sdkconfig, so an
sdkconfig made before keeps what it had.

The sdkconfig of a board lies in the project, not in build/, so build/ holds only what a build makes again, as in any
project of ESP-IDF; this command moves one a version before 0.1.1 left in build/<BOARD>/ there.
The configuration editor of VS Code and menuconfig change sdkconfig.<BOARD> of the current board alone.
board_select.py --keep PROJECT_DIR puts what they set into the project's own sdkconfig.defaults, which every board
reads after its own file: the minimal configuration of ESP-IDF (savedefconfig) less what sdkconfig.defaults.<BOARD>
sets, the chip and the choice of the board among it. An option of the board changed there is named and not kept.
save-defconfig of ESP-IDF writes the lines of the board too, so every board would take this one's. Each configuration
does the same for what changed in sdkconfig.<BOARD> since the one before, by --auto-keep, so what is set with the editor
reaches every board at the next build; a snapshot of each sdkconfig is kept in PROJECT_DIR/.boards/.

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
import vscode_env
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


PROGRAM_LINE = "CONFIG_BOARD_SELECT_PROGRAM=y"  # a board of the program is chosen in two steps: this, then which one


def local_defaults(local, name):
    """The sdkconfig.defaults of a board of the program: its own, or the one of the board it extends with the choice changed;
    either way with the line that chooses "A board of this program" before its own."""
    own = local / "boards" / name / "sdkconfig.defaults"
    if own.exists():
        text = own.read_text()
    else:
        base = resolve.load("boards", name).get("extends")
        if not base:
            raise SystemExit(f"{own}: write it, the board extends nothing to take it from")
        text = re.sub(r"^CONFIG_BOARD_SELECT_\w+=y$", f"CONFIG_BOARD_SELECT_{name.upper()}=y", defaults_of(base, "board"), flags=re.M)
    if PROGRAM_LINE in text.splitlines():
        return text
    return re.sub(rf"^CONFIG_BOARD_SELECT_{name.upper()}=y$", f"{PROGRAM_LINE}\n\\g<0>", text, count=1, flags=re.M)


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
    # first, as the one to choose in VS Code: board_select.py --current and the page change what it builds
    return resolve.dump({**doc, "configurePresets": [default, *boards]}) + "\n"


def presets_text(project, boards, targets, current, command, follows=None):
    """CMakePresets.json of the boards: one preset each in the order named, and default for the current one. follows is
    the current board they are made with, which selection.json gets too: a page that names another later has changed it."""
    our_presets(project, boards)
    # Ninja, as idf.py takes it: a build directory CMake Tools of VS Code made with another generator stops idf.py there
    presets = [{"name": board, "displayName": title_of(board, project), "generator": "Ninja", "binaryDir": f"build/{board}",
                "cacheVariables": {"BOARD": board, "IDF_TARGET": target, "SDKCONFIG": f"sdkconfig.{board}"}} for board, target in zip(boards, targets)]
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


def move_sdkconfig(project, boards, renamed=None):
    """The sdkconfig of a board a version before 0.1.1 kept in its build directory, moved beside its defaults with what was
    set in it; a board renamed takes the one of its old name."""
    old_names = {new: old for old, new in (renamed or {}).items()}
    for board in boards:
        kept = project / f"sdkconfig.{board}"
        for name in (board, old_names.get(board)):
            old = project / "build" / name / "sdkconfig" if name else None
            if old and old.exists() and not kept.exists():
                old.rename(kept)
                print(f"{kept}: moved from {old}, with what was set in it; build/ holds no configuration now")


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


def title_of(board, project=None):
    """The title of a board in the lists of presets; a board of the program is named for the program, so it is not taken
    for the board it is made of."""
    if is_host(board):
        return f"the computer as {title_of(shown_by(board), project)}"
    try:
        doc = resolve.load("boards", board)
    except resolve.Refused:
        return board
    title = doc.get("title", board)
    return f"{title} for {project_writer.Project(project).name()}" if doc.get("kind") == "project" and project else title


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
        move_sdkconfig(project, boards, renamed)
        vscode_env.current(project, current, targets[current])
    project_writer.keep_ours(project, [*written, *presets])
    print("An sdkconfig made before keeps what it had: ESP-IDF reads the defaults only into a new one. To take what changed,\n"
          "remove sdkconfig.<BOARD> of the board, after board_select.py --keep . for what was set in it.")
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
            + f"CONFIG_BOARD_HOST_TOUCH={int('BOARD_TOUCH' in boards_gen.features_of(board))}\n"
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


SNAPSHOTS = ".boards"  # the sdkconfig of each board as it was kept last, beside what the page keeps there


def take_snapshot(config, snapshot):
    snapshot.parent.mkdir(exist_ok=True)
    shutil.copyfile(config, snapshot)


# a line of sdkconfig or of a file of defaults: an option and its value, or a bool that is off
OPTION_LINE = re.compile(r"^(?:(CONFIG_\w+)=.*|# (CONFIG_\w+) is not set)$")
DEFAULT_MARK = "# default:"  # in an sdkconfig of ESP-IDF 6, before an option nobody set
DEPRECATED_HEAD = "# Deprecated options for backward compatibility"  # the old names an sdkconfig repeats at its end
KEEP_HEAD = "# The program's own options, on every board after its sdkconfig.defaults.<board>: board_select.py --keep adds them"


def chosen_in(text):
    """The options an sdkconfig has on that the person or a file of defaults set: ESP-IDF 6 marks each other one, a
    default of Kconfig or one another option selects, by a line "# default:" before it, up to the old names it repeats at
    the end. An option the person set that another selects too stays: the minimal configuration would leave it to that
    one. An option set off is in the minimal configuration when it is on by default."""
    found, marked = {}, False
    for line in text.splitlines():
        line = line.strip()
        if line == DEPRECATED_HEAD:
            break
        if line == DEFAULT_MARK:
            marked = True
            continue
        matched = OPTION_LINE.match(line)
        if matched and matched[1] and not marked:
            found[matched[1]] = line
        marked = False
    return found


def options_of(text):
    """The options a file sets, by name, each with its line."""
    found = {}
    for line in text.splitlines():
        matched = OPTION_LINE.match(line.strip())
        if matched:
            found[matched[1] or matched[2]] = line.strip()
    return found


def keep(project, board=None, edited_only=False):
    """--keep: the options of the configuration of the current board that its file of defaults does not set, into the
    project's sdkconfig.defaults; its other lines stay, and an option it names takes the value the configuration has.
    --auto-keep BOARD, as project_include.cmake runs it at each configuration: the same for the options changed in
    sdkconfig.<BOARD> since its last configuration, as the configuration editor or menuconfig change them; an option
    a board left as it was, as one an older sdkconfig of another board still has, is not taken back."""
    if board is None:
        doc = our_presets(project, [])
        if doc is None:
            raise SystemExit(f"{project}: no {PRESETS} there: choose the boards first")
        board = next(preset["cacheVariables"]["BOARD"] for preset in doc["configurePresets"] if preset["name"] == DEFAULT)
    build = project / "build" / board
    ninja = build / "build.ninja"
    config = project / f"sdkconfig.{board}"
    snapshot = project / SNAPSHOTS / f"sdkconfig.{board}"
    edited = None
    if edited_only:
        if not config.exists():
            return 0
        before = options_of(snapshot.read_text()) if snapshot.exists() else None
        edited = {name for name, line in options_of(config.read_text()).items() if before is not None and name in before and before[name] != line}
        # the first configuration of a board, or nothing changed, or no build yet to take the minimal configuration from
        if not edited or not ninja.exists():
            take_snapshot(config, snapshot)
            return 0
    elif not ninja.exists() or not config.exists():
        raise SystemExit(f"{board}: not configured yet: idf.py reconfigure, then change the options and run this again")
    # the command of save-defconfig as ESP-IDF made it for this build, written elsewhere than the project's file
    rule = re.search(r"^build CMakeFiles/save-defconfig\b.*\n  COMMAND = (.*)$", ninja.read_text(), flags=re.M)
    if not rule:
        raise SystemExit(f"{ninja}: no save-defconfig there to take the minimal configuration from")
    saved = build.resolve() / "sdkconfig.kept"  # the command runs in the build directory
    command = re.sub(r"--output savedefconfig \S+", f"--output savedefconfig {shlex.quote(str(saved))}", rule[1])
    # a file of defaults removed since the configuration is left out, as the next configuration leaves it
    command = re.sub(r"--defaults (\S+)", lambda found: found[0] if pathlib.Path(found[1]).exists() else "", command)
    run = subprocess.run(command, shell=True, capture_output=True, text=True)
    text = saved.read_text() if saved.exists() else None
    saved.unlink(missing_ok=True)
    if run.returncode or text is None:
        raise SystemExit(f"savedefconfig of ESP-IDF failed:\n{run.stdout}{run.stderr}")
    minimal = options_of(text)
    config_text = config.read_text()
    have = options_of(config_text)
    # what the person set, where the sdkconfig marks the rest (ESP-IDF 6); the minimal configuration alone elsewhere
    minimal.update(chosen_in(config_text) if DEFAULT_MARK in config_text else {})
    of_board = options_of((project / f"sdkconfig.defaults.{board}").read_text())
    changed = sorted(name for name, line in of_board.items() if name in have and have[name] != line)
    path = project / "sdkconfig.defaults"
    lines = path.read_text().splitlines() if path.exists() else [KEEP_HEAD]
    named = {name: at for at, line in enumerate(lines) for name in options_of(line)}
    wanted = {name: line for name, line in minimal.items() if name not in of_board}
    wanted.update({name: have[name] for name in named if name in have and name not in of_board})
    if edited is not None:
        wanted = {name: line for name, line in wanted.items() if name in edited}
        changed = [name for name in changed if name in edited]
    done = []
    for name, line in wanted.items():
        if name in named:
            if lines[named[name]] != line:
                lines[named[name]] = line
                done.append(line)
        else:
            lines.append(line)
            done.append(line)
    if done:
        path.write_text("\n".join(lines) + "\n")
        print(f"{path}: " + ", ".join(done) + (f", as {config.name} has it now: every board takes it" if edited is not None else ""))
    elif edited is None:
        print(f"{path}: nothing new from {config.name}")
    take_snapshot(config, snapshot)
    if changed:
        print(f"set by sdkconfig.defaults.{board}, not kept: {', '.join(changed)}. The options of a board are its data, "
              "the same for every program on it")
    others = [other for other in boards_of(project) if other != board and (project / f"sdkconfig.{other}").exists()]
    if done and others:
        print("An sdkconfig made before keeps what it had: to take these, remove " + ", ".join(f"sdkconfig.{other}" for other in others))


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
    parser.add_argument("--keep", action="store_true", help="the options set for the current board into the project's sdkconfig.defaults")
    parser.add_argument("--auto-keep", metavar="BOARD", help="the options changed in sdkconfig.BOARD since its last configuration, into sdkconfig.defaults")
    args = parser.parse_intermixed_args()  # options may stand between the boards and the project, as board_select.py b --module m .
    if args.again:
        if len(args.names) != 1 or args.module or args.revision or args.shows or args.current:
            parser.error("--again takes only the project's directory")
        return again(parser, pathlib.Path(args.names[0]))
    if args.keep or args.auto_keep:
        if len(args.names) != 1 or args.module or args.revision or args.shows or args.current:
            parser.error("--keep and --auto-keep take only the project's directory")
        return keep(pathlib.Path(args.names[0]), args.auto_keep, edited_only=bool(args.auto_keep))
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
        vscode_env.current(project, args.current, target_of(project / f"sdkconfig.defaults.{args.current}"))
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
    move_sdkconfig(project, every)
    vscode_env.current(project, current, target_of(project / f"sdkconfig.defaults.{current}"))
    if (project / "sdkconfig.defaults.board").exists():
        print(f"{project / 'sdkconfig.defaults.board'}: the file of one board as it was before the presets; the CMakeLists.txt of the "
              "skeleton reads sdkconfig.defaults.<board> by a preset, take its lines")
    print(f"{project / PRESETS}: a preset for each board of the project ({', '.join(every)}), and default for the current one, {current}\n"
          f"ESP-IDF 6: idf.py build builds {current} in build/{current}, idf.py --preset <board> build another;\n"
          f"board_select.py --current <board> {project} makes another current. ESP-IDF 5 does not read the presets:\n"
          f"  idf.py -B build/{current} -D SDKCONFIG=sdkconfig.{current} -D BOARD={current} build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
