#!/usr/bin/env python3
"""Check the boards: the data reads, and everything generated from it is what it says.

Usage: check_boards.py [--fix] [--host-syntax]

Every board in boards-data/ is read as the generator reads it (a change of the schema is a
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import boards_gen  # noqa: E402

# what boards.h declares and every board's glue must define
API = (
    "bool board_display_init(struct board_display *out)",
    "bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)",
    "bool board_character_display_init(struct board_character_display *out)",
    "bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)",
    "bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)",
    "void board_sound_source(board_sound_source_t source)",
    "bool board_button(bool *pressed)",
    "const struct board_spi_bus *board_spi_bus(int host)",
    "bool board_spi_taken(int host)",
    "bool board_bus_get(const char *bus, const char *field, long *out)",
    "const struct board_i2c_pins *board_i2c_pins(void)",
    "const struct board_data board_data =",
)
MODULE_API = ("bool board_character_display_init(struct board_character_display *out)",)


def error(msg):
    print(f"check_boards: {msg}", file=sys.stderr)
    return 1


def check_defaults(board):
    """The board's sdkconfig.defaults chooses the chip and the board; a module's turns itself on."""
    errors = 0
    path = ROOT / "boards-data" / board["name"] / "sdkconfig.defaults"
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
    select = f"CONFIG_{boards_gen.choice_symbol(board)}=y"
    if select not in lines:
        errors += error(f"{path.relative_to(ROOT)}: the first lines choose the board: {select}")
    for line in lines:
        if line.startswith("CONFIG_BOARD_SELECT_") and line != select:
            errors += error(f"{path.relative_to(ROOT)}: chooses another board: {line}")
    return errors


def check_api(board, text):
    """The glue defines every function of boards.h, a module the one of its kind."""
    errors = 0
    for signature in (MODULE_API if board.get("module") else API):
        if signature not in text:
            errors += error(f"boards/{board['name']}/{board['name']}.c: does not define {signature.split('(')[0].split()[-1]}: the contract of boards.h would not hold at link")
    return errors


def host_syntax(source):
    """A source compiles against test/fake with -fsyntax-only: the shape of every call is right."""
    cmd = ["gcc", "-std=gnu11", "-fsyntax-only", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-function",
           f"-I{ROOT / 'include'}", f"-I{ROOT / 'src'}", f"-I{ROOT / 'test' / 'fake'}", str(source)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return error(f"{source.relative_to(ROOT)} does not compile against test/fake:\n{result.stderr}")
    return 0


def main():
    fix = "--fix" in sys.argv
    syntax = "--host-syntax" in sys.argv
    errors = 0
    try:
        boards, modules = boards_gen.read_all(ROOT / "boards-data")
    except (ValueError, KeyError) as err:
        return error(str(err))
    for board_file in sorted((ROOT / "boards-data").glob("*/board.json")):
        try:
            boards_gen.read_board(board_file)
        except (ValueError, KeyError) as err:
            errors += error(f"{board_file.relative_to(ROOT)}: {err}")
    if errors:
        return 1

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
            errors += error(f"{stale.relative_to(ROOT)}: the defaults live in boards-data/{board['name']}/, not here (remove it)")
        errors += check_defaults(board)
        glue = ROOT / "boards" / board["name"] / f"{board['name']}.c"
        if glue.exists():
            errors += check_api(board, glue.read_text())
        for problem in boards_gen.pin_problems(board):
            errors += error(f"boards-data/{board['name']}/board.json: {problem}")
        if syntax and glue.exists():
            errors += host_syntax(glue)
    if syntax:
        for source in sorted((ROOT / "src").glob("*.c")):
            errors += host_syntax(source)

    # every component the data names has its rule
    manifest = (ROOT / "idf_component.yml").read_text()
    for board in boards:
        touch = board.get("touch")
        if touch and touch["kind"] == "esp_lcd_touch" and f"  {touch['component']}:" not in manifest:
            errors += error(f"idf_component.yml: no dependency on {touch['component']}, which boards-data/{board['name']} names")
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
