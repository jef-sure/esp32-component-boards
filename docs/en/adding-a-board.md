# Adding a board

A board is a directory in `catalog/boards/` with two files. Everything else is
generated.

## 1. Describe it

Copy the nearest board:

```sh
cp -r catalog/boards/jc1060p470c catalog/boards/myboard
```

Edit `catalog/boards/myboard/board.json`: `name` must equal the directory name;
then the chip, the buses as the board wires them, the devices on them. The
format is in [data-format.md](data-format.md). Where the data comes from, in order of trust: the
board's schematic, the vendor's examples, a well-kept community pin list, and
measuring the board itself.

Write `catalog/boards/myboard/sdkconfig.defaults` by hand. Its first two lines
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

A new chip of a library the component already starts is an entry in the record of that
library in `catalog/libraries/`. A new library is a record and, when the component should
start it, a directory in `adapters/` and its `adapter` field; a new kind of part may also need
the generator and the stub headers in
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
`touch_check` does it on the board's display), then give the log to
`tools/board_calibration.py`. Until then leave
`"measured": false` in the calibration: the glue warns at start and the README
table says so. See [calibration.md](calibration.md).

## 5. Commit

Commit the data, the defaults and the generated files together: a program
that takes the component from the registry builds without running the
generator. `check_boards.py` in CI refuses a commit where they disagree.

## A board of your own, outside the component

The generator is in the component's package. A project may keep its own
`catalog/boards/myboard/` and run `tools/boards_gen.py --data myproject/catalog/boards
--out myproject/boards myboard` to get glue it compiles itself. Making the
component's menu offer such a board is planned (the choice is a named Kconfig
choice, which another Kconfig can extend); for now the project compiles the
glue in a component of its own and names the libraries it needs in its own
manifest.
