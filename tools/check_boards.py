#!/usr/bin/env python3
"""Check the boards: the data reads, and everything generated from it is what it says.

Usage: check_boards.py [--fix] [--host-syntax]

Every board in catalog/ is read as the generator reads it (a change of the schema is a
change of the generator and of this). Then:

  - the glue in boards/, boards/boards.cmake, Kconfig, the dependencies of idf_component.yml
    and the tables of the READMEs are what tools/boards_gen.py --all would make of the data
    (--fix makes them so);
  - every board's sdkconfig.defaults chooses its chip and itself (CONFIG_IDF_TARGET,
    CONFIG_BOARD_SELECT_<BOARD>=y), a module's turns itself on;
  - the glue of a board defines every function of boards.h (the contract holds at link);
  - the map of pins has no two owners of one GPIO, no output on an input-only one;
  - every component the data names has a rule in the manifest;
  - with --host-syntax, every glue compiles on this machine against test/fake with
    -fsyntax-only (the fast filter; the real check is the build in CI).

Run from the repository root: python3 tools/check_boards.py
"""

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import boards_gen  # noqa: E402
import resolve

# what a board must define, read from the headers rather than kept here twice: every function boards.h declares (in the
# glue, in src/ or in an adapter the board starts) and every table board_glue.h names extern (in the glue)
API_FUNCTIONS = sorted(set(re.findall(r"^[A-Za-z_][\w \*]*?\b(board_\w+)\s*\([^;{]*\)\s*;", (ROOT / "include" / "boards.h").read_text(), re.M)))
API_TABLES = sorted(set(re.findall(r"^extern const struct \w+ (board_\w+);", (ROOT / "src" / "board_glue.h").read_text(), re.M)))
HOST = "board_host.c"  # boards.h of the computer, the linux target only
NOT_A_BOARD = {"board_none.c", HOST}  # they define what a glue gives: read beside a glue, they would hide what it lacks
MODULE_API = ["board_character_display_init"]  # a module gives the function of its kind


def error(msg):
    print(f"check_boards: {msg}", file=sys.stderr)
    return 1


def check_defaults(board):
    """The board's sdkconfig.defaults chooses the chip and the board; a module's turns itself on."""
    errors = 0
    path = ROOT / "catalog" / ("modules" if board.get("module") else "boards") / board["name"] / "sdkconfig.defaults"
    if not path.exists():
        return error(f"{path.relative_to(ROOT)}: the board needs one (what its chip, its memory and its flash need), written by hand")
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
    if board.get("module"):
        want = f"CONFIG_{boards_gen.module_symbol(board)}=y"
        if want not in lines:
            errors += error(f"{path.relative_to(ROOT)}: a module's defaults turn it on: {want}")
        for line in lines:
            if line.startswith("CONFIG_IDF_TARGET"):
                errors += error(f"{path.relative_to(ROOT)}: a module names no chip, its board does")
        return errors
    target = f'CONFIG_IDF_TARGET="{board["mcu"]["target"]}"'
    if target not in lines:
        errors += error(f"{path.relative_to(ROOT)}: the first lines choose the chip: {target}")
    settings = resolve.chip_settings(board["mcu"])
    psram = board["mcu"].get("psram_mhz")
    if not settings and psram and f"CONFIG_SPIRAM_SPEED_{psram}M=y" not in lines:
        errors += error(f"{path.relative_to(ROOT)}: the data says PSRAM at {psram} MHz: CONFIG_SPIRAM_SPEED_{psram}M=y")
    for line in lines:
        if settings and re.match(r"CONFIG_(SPIRAM_SPEED_|ESP_DEFAULT_CPU_FREQ_MHZ_|\w+_REV_MIN_|\w+_SELECTS_REV_LESS_V3)", line):
            errors += error(f"{path.relative_to(ROOT)}: {line} follows the revision of the chip, board_select.py writes it")
    select = f"CONFIG_{boards_gen.choice_symbol(board)}=y"
    if select not in lines:
        errors += error(f"{path.relative_to(ROOT)}: the first lines choose the board: {select}")
    for line in lines:
        if line.startswith("CONFIG_BOARD_SELECT_") and line != select:
            errors += error(f"{path.relative_to(ROOT)}: chooses another board: {line}")
    return errors


def check_api(board, text):
    """The glue defines every function of boards.h with what the board starts, a module the one of its kind, and the tables."""
    errors = 0
    module = board.get("module")
    for name in MODULE_API if module else API_FUNCTIONS:
        if not re.search(rf"\b{name}\s*\([^;{{]*\)\s*\{{", text):
            errors += error(f"boards/{board['name']}/{board['name']}.c: {name} is defined nowhere: the contract of boards.h would not hold at link")
    for name in () if module else API_TABLES:
        if not re.search(rf"\bconst struct \w+ {name}\s*=", text):
            errors += error(f"boards/{board['name']}/{board['name']}.c: does not give {name}")
    return errors


def adapter_sources(record):
    """The sources of the adapter of a library, as its record names them."""
    return [ROOT / boards_gen.adapter_dir(record) / name for names in (record.get("adapter") or {}).get("sources", {}).values() for name in names]


def adapter_files(record):
    """Every file the record of a library names in its adapter: each must be there."""
    adapter = record.get("adapter") or {}
    folder = ROOT / boards_gen.adapter_dir(record)
    public = [folder / "include" / adapter["public"]] if "public" in adapter else []
    return adapter_sources(record) + [folder / name for name in adapter.get("headers", ())] + public


def host_syntax(source, name=None):
    """A source compiles against test/fake with -fsyntax-only: the shape of every call is right."""
    cmd = ["gcc", "-std=gnu11", "-fsyntax-only", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-function",
           f"-I{ROOT / 'include'}", f"-I{ROOT / 'src'}", *(f"-I{path}" for path in sorted((ROOT / "adapters").glob("*"))),
           *(f"-I{path}" for path in sorted((ROOT / "adapters").glob("*/include"))), f"-I{ROOT / 'test' / 'fake'}", str(source)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return error(f"{name or source.relative_to(ROOT)} does not compile against test/fake:\n{result.stderr}")
    return 0


def main():
    fix = "--fix" in sys.argv
    syntax = "--host-syntax" in sys.argv
    errors = 0
    try:
        boards, modules = boards_gen.read_all(ROOT / "catalog")
    except (ValueError, KeyError) as err:
        return error(str(err))

    # everything generated is what the data says
    for path, text in boards_gen.generated_texts(ROOT, boards, modules).items():
        rel = path.relative_to(ROOT)
        if not path.exists():
            if fix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            else:
                errors += error(f"{rel}: missing (run tools/boards_gen.py --all)")
            continue
        if path.read_text() != text:
            if fix:
                path.write_text(text)
            else:
                errors += error(f"{rel} is not what the data says (run tools/boards_gen.py --all)")
    for board in boards + modules:
        stale = ROOT / "boards" / board["name"] / "sdkconfig.defaults"
        if stale.exists():
            errors += error(f"{stale.relative_to(ROOT)}: the defaults live in catalog/, not here (remove it)")
        errors += check_defaults(board)
        glue = ROOT / "boards" / board["name"] / f"{board['name']}.c"
        if glue.exists():
            # the functions of a part a board has may lie in the core or in an adapter
            core = "".join(path.read_text() for path in sorted((ROOT / "src").glob("*.c")) if path.name not in NOT_A_BOARD)
            core += "".join(path.read_text() for record, _, _ in boards_gen.started(board) for path in adapter_sources(record))
            errors += check_api(board, glue.read_text() + core)
        for problem in boards_gen.pin_problems(board):
            errors += error(f"{boards_gen.data_path(board)}: {problem}")
        if syntax and glue.exists():
            errors += host_syntax(glue)
    if syntax:
        # a title with a quote and a backslash, and a description that would end a comment, as a page may write them
        spoiled = {**boards[0], "title": 'A "quoted" \\ title */', "description": "a comment ends */ here"}
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / f"{spoiled['name']}.c"
            source.write_text(boards_gen.gen_c(spoiled))
            errors += host_syntax(source, f"the glue of {spoiled['name']} with a spoiled title")
        prompt = boards_gen.kconfig_board(spoiled)[1]
        if not re.fullmatch(r'    bool "(?:[^"\\]|\\.)*"', prompt):
            errors += error(f"the Kconfig prompt of a spoiled title is not one string: {prompt}")
        for source in sorted((ROOT / "src").glob("*.c")) + sorted((ROOT / "adapters").glob("*/*.c")):
            if source.name != HOST:  # SDL2 and the linux target: CI builds it for the computer
                errors += host_syntax(source)

    for record in resolve.all_libraries(tuple(resolve.ROOTS)).values():
        for path in adapter_files(record):
            if not path.exists():
                errors += error(f"{resolve.library_id(record)}: its adapter names {path.relative_to(ROOT)}, which is not there")

    # every component the data names has its rule
    manifest = (ROOT / "idf_component.yml").read_text()
    for board in boards:
        for touch in board["touches"]:
            if touch["kind"] == "esp_lcd_touch" and f"  {touch['component']}:" not in manifest:
                errors += error(f"idf_component.yml: no dependency on {touch['component']}, which catalog/boards/{board['name']} names")
    kconfig = (ROOT / "Kconfig").read_text()
    for cfg in re.findall(r"\$CONFIG\{([A-Za-z0-9_]+)\}", manifest):
        if not re.search(rf"^config {cfg}$", kconfig, re.M):
            errors += error(f"idf_component.yml: the rule names {cfg}, which the Kconfig does not define")

    if errors:
        return 1
    print(f"check_boards: {len(boards)} boards, {len(modules)} modules; the data, the glue, the Kconfig and the manifest agree"
          + ("; every glue compiles against test/fake" if syntax else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
