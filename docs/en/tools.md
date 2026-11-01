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

## board_bom.py

```sh
python3 tools/board_bom.py my_board --project .                        # one product
python3 tools/board_bom.py my_board --project . --units 10 --shop AliExpress  # ten, at the prices of one shop
python3 tools/board_bom.py my_board --project . --units 10 --duty 3 EUR  # with a duty per tariff code
python3 tools/board_bom.py my_board --project . --csv my_board.csv      # the lines for a spreadsheet
```

A line is what is bought as one: the board a project stands on, then the modules and devices
the project adds, the same goods on one line. The chips of a bought board are not lines, and a
board with `extends` is a variant, one purchase. So a product is written as `kind: project`
over its base board.

Prices are ranges, so a total is a range. A line with no price is named, and the total then
reads "at least". Currencies are not converted. For a quantity the tool takes, per shop, the
offer of the largest `qty` that the quantity reaches.

Delivery and duty depend on the order, so they are not in the data. `--duty` adds an amount per
tariff code: the fewest codes are those known, in one parcel; the most is every line in a parcel
of its own. The tool does not know when a duty applies. In the EU, from 1 July 2026, it is
[3 EUR per tariff classification on goods up to 150 EUR](https://commission.europa.eu/news-and-media/news/ensuring-fairness-and-safety-eur3-customs-duty-low-value-parcels-2026-06-29_en),
so a larger order is outside this sum. Delivery is not counted at all.

## check_format.py

```sh
python3 tools/check_format.py
```

Needs `jsonschema` and `node`; the Python of ESP-IDF has the first. Checks every
file of `catalog/` and `test/format/catalog/` against
`catalog/format.schema.json`, every board through the merge and the rules, the
cases of `test/format/good/` and `test/format/bad/`, that `tools/rules.py` and
`editor/rules.js` find the same, and that `tools/resolve.py` and `editor/resolve.js`
give the same for every document that passes the schema.

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

## update_rates.py

Writes `catalog/rates.json` from the reference rates of the European Central Bank, so that prices in
any currency compare on the page. It needs the network and nothing else; the page only reads the file.

## take_report.py

Takes a price from an issue of the form `price.yml` and adds it to the file of its item as an offer. The text of an
issue comes from anyone, so it is only read as fields, and `.github/workflows/reports.yml` gives it through a file. The
workflow opens a pull request, and a person merges it. `check_format.py` tries the tool on good and bad reports.

## import_board_manager.py

Takes the boards of esp_board_manager packs into `imported/`, a tree in the layout of `catalog/` that the tools read
after it. A pack is data from the net: it is unpacked apart and only read.

```sh
python3 tools/import_board_manager.py esp_boards=PATH guition_boards=PATH --date 2026-11-01
```

It gives no value a pack does not, takes no DSI timings and no init commands, writes no `shared_pins`. What the format
refuses goes to `imported/report.json` with its reason, beside the pins of the boards the catalog has against the
packs and what the format has no place for. `check_format.py` checks the result and these rules.

## import_fritzing.py

Takes modules from Fritzing parts into `imported/modules/`. Run it after `import_board_manager.py`, which rewrites
`imported/devices/`.

```sh
python3 tools/import_fritzing.py adafruit=PATH fritzing=PATH --ref adafruit=COMMIT --date 2026-11-01
```

Only facts are taken: the contacts, the supply they name, the part number. A module needs a bus its contacts show.
Its roles come from the words of `catalog/roles.json`, and from the sections of a shop when `--shop` names a copy of its list, which also gives the price and leaves out what is no longer sold.

## sync_versions.py

```sh
python3 tools/sync_versions.py
```

Fills `versions` of the `esp-idf` library records: from the component registry what each version
is built against and requires, from the tags of git the versions the registry has not. A version the registry does not have yet stays as written.

## The page

`editor/index.html` answers what to build and on what, and edits the files of the catalog. It needs no
build and no network, only a static server from the root of the repository: Live Server of VS Code, or

```sh
python3 -m http.server 8000
```

Open `/editor/` on that server: the catalog loads by itself.

### select

The form comes from `catalog/questions.json`. Every board of the catalog gets a verdict at once: what
it has, the modules it lacks with the wires for them, the price, and what the data does not say,
marked `?`. Boards that do not fit are listed with the reason. The solver only proposes: each kit
is a project, and the checks of the tools decide about it. So two PN532 go on SPI by themselves,
because the rules refuse one I2C address twice.

The solver wires I2C, SPI, QSPI and UART and the lines a chip needs beside its bus, such as BUSY and
RST of the PN5180. A DSI module takes a free DSI bus of the board on a ribbon, and its timings stay an
unknown of the kit, because they are measured on a board. The solver takes free pins that come out to
a connector and leaves strapping pins, the pins of the flash and those of the console alone. It joins
a bus of the board only when the lines of that bus come out and no display holds it, and it lists
those lines too. For each module it picks the lowest line of power that fits and comes out, and it
asks for a level shifter when the lines of a module go above what the pins of the chip take, see
[Supply and levels](data-format.md#supply-and-levels). It does not add up currents.

Tones and PWM are outputs of the chip: each has a frequency, a tone a tolerance and jitter, PWM its bits
of duty, and either may have to change while it runs. The solver tries the sources of the chip in the
order of `frequency_sources`, works out the frequency it gets from each, and takes the first that holds:
usually LEDC, then MCPWM and RMT, a crystal of the board through CLK_OUT, I2S with the APLL. A frequency
belongs to a timer, so outputs of one setting share it. The figures are calculated, not measured.

Kits come in this order: those that fit, the fewest unknowns, the fewest modules, the fewest wires,
then the price. A budget makes the price a criterion: it then comes right after the unknowns, and a
missing price counts as an unknown. `tools/check_format.py` gives the kits of `test/solver/` to the
generator as well.

`make a project…` asks for a folder, and the folder decides what happens:

- an empty folder, or one with only `.git`, a README, a licence and `.gitignore`, gets a whole
  project. What already lies there stays;
- a folder with a `CMakeLists.txt` is a program, and gets only its board in `components/local-boards/`;
- any other folder is refused.

The list of what would happen comes first and nothing is written before `write`. A board file that
differs is replaced only when ticked, and nothing is ever removed. If a file changed after the list
was made, nothing is written at all. A kit that needs no module gets no
board file: the project names the board of the catalog. The page does not talk to GitHub: the result
is a folder, for git or for nothing.

The board is chosen before the first build, because the dependencies follow from what it has:
`board_select.py`, then `idf.py build`. In a project built for another board run
`idf.py reconfigure build`; `board_select.py` says so.

### edit

`open a folder` takes a program or its `components/local-boards`, to edit the boards of that program. It takes the folder of the
repository too, and then Chromium saves into the catalog in place. A page opened from a file has no
server to load from, so there the repository comes first.

On the left are the documents of the catalog, next to them the tree of the one open. `card` shows
the fields of a node with what the schema says of each: what the file writes in plain text, what
it inherits in grey. A value typed over an inherited one goes into this file. In a file with
`extends`, × on an inherited field writes `null`, which takes it out here and leaves the base as it
is. `pins` is the map of the GPIOs, `json` the file as it will be saved and the resolved board as the
tools read it.

Every change runs the same checks as the tools: the schema, the loader, the rules and the map of
pins. The problems are listed above the card. Chromium saves into the folder opened; without one,
or in another browser, the page gives a download to put in place by hand. Then run
`tools/boards_gen.py --all`, or `tools/board_select.py` for a board of a program.

The boards of a program are listed apart, over the catalog, and what is new goes there. Without a
program a new document goes into the catalog, so `project` is not offered.

The files of `catalog/mcu/` are written by `tools/make_mcu.py`, so they are read only here. The same
holds for a part of a module on a board: change it in the module, or through `modules` of the board.

`tools/check_format.py` compares `editor/schema.js`, `editor/pins.js` and the JSON the page saves with
the tools in Python, on every document and on spoiled copies of them.

## test/fake

The stub headers for `--host-syntax`. Not in the registry package. A new
include in the generated glue needs a stub here with the same name and the
shape of what the glue calls.

## The CI workflow

`.github/workflows/build.yml`: `check_boards.py --host-syntax` and
`board_pins.py --all`, then `examples/hello_board` for every board and
`examples/hello_lvgl` for every board with a graphics display, under two
versions of ESP-IDF, plus one build of
`hello_board` with the 2004 module, each in its own job. Add a board to the matrix when you add it to the data.
