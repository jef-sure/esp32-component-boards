# Adding a board

A board is a directory in `boards-data/` with two files. Everything else is
generated.

## 1. Describe it

Copy the nearest board:

```sh
cp -r boards-data/jc1060p470 boards-data/myboard
```

Edit `boards-data/myboard/board.json`: `name` must equal the directory name;
then the chip, the buses as the board wires them, the devices on them. The
format is in [data-format.md](data-format.md). The editor at
`editor/index.html` (open it in a browser, no build step) loads the file,
checks the same rules the generator applies as you type, and saves a
`board.json` to download. Where the data comes from, in order of trust: the
board's schematic, the vendor's examples, a well-kept community pin list, and
measuring the board itself.

Write `boards-data/myboard/sdkconfig.defaults` by hand. Its first two lines
choose the chip and the board; the rest is what the chip, its memory and its
flash need, with the reason for every line in a comment. The reasons matter:
the next person reads them, and the chip's revision or the PSRAM's speed are
easy to get wrong silently.

```
CONFIG_IDF_TARGET="esp32s3"
CONFIG_BOARD_SELECT_MYBOARD=y
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
# 8 MB octal PSRAM: the frame buffer lives in it
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_SPEED_80M=y
```

## 2. Generate and check

```sh
python3 tools/boards_gen.py --all
python3 tools/check_boards.py --host-syntax
python3 tools/board_pins.py myboard
```

The generator writes the glue, `boards/boards.cmake`, `Kconfig`, the
manifest's dependencies and the README tables. The check compares them with
the data, verifies the defaults, the API coverage and the pin map, and
compiles the glue against `test/fake/`. The pin map shows every GPIO and its
owner, with conflicts marked.

A new panel driver, touch kind or sound kind is a change of the generator
(its tables at the top: `PANEL_HEADERS`, `PANEL_SELECTS`, `TOUCH_KINDS`,
`FEATURE_DEPS`, `COMPONENT_VERSIONS`) and of the stub headers in
`test/fake/`; a new board of a known kind is data only.

## 3. Build it

```sh
python3 tools/board_select.py myboard examples/hello_board
cd examples/hello_board && idf.py build flash monitor
```

The example prints what it found and draws a frame. Add the board to the
matrix in `.github/workflows/build.yml` so CI builds it from now on.

## 4. Measure the touch

The touch works without a calibration measured on the board, but not
straight. Measure it with DGX-DI's `dgx_di_calibrate_measure` (its example
`touch_check` does it on the board's display), paste the C initializer it
prints into the editor's calibration field, and save. Until then leave
`"measured": false` in the calibration: the glue warns at start and the README
table says so. See [calibration.md](calibration.md).

## 5. Commit

Commit the data, the defaults and the generated files together: a program
that takes the component from the registry builds without running the
generator. `check_boards.py` in CI refuses a commit where they disagree.

## A board of your own, outside the component

The generator is in the component's package. A project may keep its own
`boards-data/myboard/` and run `tools/boards_gen.py --data myproject/boards-data
--out myproject/boards myboard` to get glue it compiles itself. Making the
component's menu offer such a board is planned (the choice is a named Kconfig
choice, which another Kconfig can extend); for now the project compiles the
glue in a component of its own and names the libraries it needs in its own
manifest.
