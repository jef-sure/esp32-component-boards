# The tools

All in `tools/`, Python 3.8 or later, no packages beyond the standard
library. Run them from the root of the repository (or of
`managed_components/jef-sure__boards/`).

## boards_gen.py

```sh
python3 tools/boards_gen.py --all          # everything, from every board and module
python3 tools/boards_gen.py cyd_s028r      # one board's glue and board.cmake only
```

Reads `catalog/boards/*/board.json` and `catalog/modules/*/module.json`, merges
them with the catalog, applies `catalog/rules.json`, refuses what it cannot make glue for (see
[data-format.md](data-format.md)), and writes:

- `boards/<board>/<board>.c` and `board.cmake` for every board and module;
- `boards/boards.cmake`: the lists the component's `CMakeLists.txt` compiles by;
- `Kconfig`: the choice, the modules' options, the hidden symbols;
- the `dependencies:` of `idf_component.yml`, between `# boards: dependencies
  generated` and `# boards: end of generated`;
- the table of boards in `README.md` and `README.ru.md`, between
  `<!-- boards:table -->` and `<!-- boards:end -->`.

It writes a file only when its content changes. The tables at its top are
the knowledge it has beyond the data: which DGX header and `DGX_ENABLE_*`
symbols a panel driver takes, which pixel depths, which touch kinds, which
registry component and version each feature brings.

## check_boards.py

```sh
python3 tools/check_boards.py                 # the data and the generated agree
python3 tools/check_boards.py --host-syntax   # and every glue and the core compile against test/fake
python3 tools/check_boards.py --fix           # write what differs instead of complaining
```

Exit status 1 and a line per finding on stderr when: a `board.json` does not
read; a generated file differs from what the data says or is missing; a
board's `sdkconfig.defaults` is missing or does not choose its chip and
itself; a module's does not turn it on; a glue does not define every
function of `boards.h`; two owners share a GPIO or an output drives an
input-only one; a component the data names has no manifest rule; a rule
names a symbol the Kconfig lacks. CI runs it first.

`--host-syntax` compiles each glue and the sources of `src/` and `adapters/` with the host's `gcc -std=gnu11
-fsyntax-only -Wall -Wextra -Werror` against `test/fake/`, stub headers that
mirror the shape of the real ESP-IDF, DGX, DGX-DI and hd44780 declarations.
When a real header changes its shape, the generator and the stubs change
together. Seconds, no ESP-IDF; the real check remains the build in CI.

## board_pins.py

```sh
python3 tools/board_pins.py cyd_s028r           # GPIO -> owner, conflicts marked
python3 tools/board_pins.py cyd_s028r --tree    # chip -> buses -> devices -> pins
python3 tools/board_pins.py --all               # every board's conflicts, for CI
```

The map the checks are made on, for a human to look at: every GPIO the data
names, who owns it and in which direction, with *TWO OWNERS*, *INPUT ONLY,
DRIVEN* and *NOT A GPIO OF THIS CHIP* beside the offenders.

## board_select.py

```sh
python3 tools/board_select.py cyd_s028r ~/myproject
python3 tools/board_select.py jc1060p470c --module lcd2004_pcf8574 --reset ~/myproject
```

Writes `~/myproject/sdkconfig.defaults.board`: the board's defaults, then
each module's. With `--reset` moves an existing `sdkconfig` to `sdkconfig.old`
so the new defaults are read. See [choosing-a-board.md](choosing-a-board.md).

## check_format.py

```sh
python3 tools/check_format.py
```

Needs `jsonschema` and `node`; the Python of ESP-IDF has the first. Checks every
file of `catalog/` and `test/format/catalog/` against
`catalog/format.schema.json`, every board through the merge and the rules, the
cases of `test/format/good/` and `test/format/bad/`, and that `tools/rules.py` and
`editor/rules.js` find the same.

## board_pins.py and the free pins

```sh
python3 tools/board_pins.py jc1060p470c --free        # what is left for what will be connected
python3 tools/board_pins.py jc1060p470c --free ADC    # the same, that can do this
python3 tools/board_pins.py jc1060p470c --json        # every GPIO, for a tool
```

What a GPIO can do comes from the table of the chip in the documentation of ESP-IDF, kept in
`catalog/mcu/` by `tools/make_mcu.py`: its analog functions, whether it is a strapping pin, what the
notes say. Who has it comes from the board, a line of a device included. Pins on a connector come
first. A line several devices use on purpose says when it is free.

## make_mcu.py

```sh
python3 tools/make_mcu.py [ESP-IDF directory]
```

Writes `catalog/mcu/` from `soc_caps.h` of ESP-IDF.

## sync_versions.py

```sh
python3 tools/sync_versions.py
```

Fills `versions` of the `esp-idf` library records: from the component registry what each version
is built against and requires, from the tags of git the versions the registry has not. A version the registry does not have yet stays as written.

## The editor

`editor/index.html` reads format 1 only and does not open the files of the catalog.
It is to be replaced by an editor on a tree. Until then edit the JSON by hand and
run `tools/check_format.py`.

## test/fake

The stub headers for `--host-syntax`. Not in the registry package. A new
include in the generated glue needs a stub here with the same name and the
shape of what the glue calls.

## The CI workflow

`.github/workflows/build.yml`: `check_boards.py --host-syntax` and
`board_pins.py --all`, then `examples/hello_board` and `examples/hello_lvgl`
built for every board under two versions of ESP-IDF, plus one build of
`hello_board` with the 2004 module, each in its own job. Add a board to the matrix when you add it to the data.
