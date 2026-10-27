# The tools

All in `tools/`, Python 3.8 or later, no packages beyond the standard
library. Run them from the root of the repository (or of
`managed_components/jef-sure__boards/`).

## boards_gen.py

```sh
python3 tools/boards_gen.py --all          # everything, from every board and module
python3 tools/boards_gen.py cyd            # one board's glue and board.cmake only
```

Reads `boards-data/*/board.json`, refuses what it cannot make glue for (see
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

`--host-syntax` compiles each glue and the core sources in `src/` with the host's `gcc -std=gnu11
-fsyntax-only -Wall -Wextra -Werror` against `test/fake/`, stub headers that
mirror the shape of the real ESP-IDF, DGX, DGX-DI and hd44780 declarations.
When a real header changes its shape, the generator and the stubs change
together. Seconds, no ESP-IDF; the real check remains the build in CI.

## board_pins.py

```sh
python3 tools/board_pins.py cyd           # GPIO -> owner, conflicts marked
python3 tools/board_pins.py cyd --tree    # chip -> buses -> devices -> pins
python3 tools/board_pins.py --all         # every board's conflicts, for CI
```

The map the checks are made on, for a human to look at: every GPIO the data
names, who owns it and in which direction, with *TWO OWNERS*, *INPUT ONLY,
DRIVEN* and *NOT A GPIO OF THIS CHIP* beside the offenders.

## board_select.py

```sh
python3 tools/board_select.py cyd ~/myproject
python3 tools/board_select.py jc1060p470 --module lcd2004_pcf8574 --reset ~/myproject
```

Writes `~/myproject/sdkconfig.defaults.board`: the board's defaults, then
each module's. With `--reset` moves an existing `sdkconfig` to `sdkconfig.old`
so the new defaults are read. See [choosing-a-board.md](choosing-a-board.md).

## The editor

`editor/index.html`, Vue 3 and Pinia from a CDN, Bootstrap for the look, no
build step: open it in a browser. *Open a board.json* loads a file; the form
edits it with the generator's rules checked live (the problems listed at the
top, *Save* disabled while any remain); *Save board.json* downloads the
result. The calibration field takes the C initializer
`dgx_di_calibrate_measure` prints and turns it into the fields of the data.
Floats in the file keep their spelling (`5.0` stays `5.0`).

## test/fake

The stub headers for `--host-syntax`. Not in the registry package. A new
include in the generated glue needs a stub here with the same name and the
shape of what the glue calls.

## The CI workflow

`.github/workflows/build.yml`: `check_boards.py --host-syntax` and
`board_pins.py --all`, then `examples/hello_board` built for every board under
two versions of ESP-IDF, plus one build with the 2004 module, each in its own
job. Add a board to the matrix when you add it to the data.
