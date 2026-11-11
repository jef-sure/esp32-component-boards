# The tools

All in `tools/`, Python 3.9 or later, as ESP-IDF 5.5 has. Most need only the standard library:
`check_format.py` needs `jsonschema` and Node.js, which runs the JavaScript of
the page; the importers need `jsonschema`. Run them from the root of the repository (or of
`managed_components/jef-sure__boards/`).

The package of the registry carries the tools a program uses: `board_select.py`, `board_project.py`,
`board_pins.py`, `board_bom.py`, `board_calibration.py`, `boards_mcp.py`, and `boards_gen.py`, `project_writer.py`,
`resolve.py` and `rules.py`, which they import. The checks, the importers, `audit.py`, `make_mcu.py`, `update_rates.py`,
`take_report.py` and `sync_versions.py` are for the repository: they need `test/`, ESP-IDF or the network.

## boards_gen.py

```sh
python3 tools/boards_gen.py --all          # everything, from every board and module
python3 tools/boards_gen.py cyd_s028r      # one board's glue and board.cmake only
python3 tools/boards_gen.py my_board --data DIR --out DIR  # a board of a directory of its own, its glue into another
```

Reads `catalog/boards/*/board.json` and `catalog/modules/*/module.json`, merges
them with the catalog, applies `catalog/rules.json`, refuses what it cannot make glue for (see
[data-format.md](data-format.md)), and writes:

- `boards/<board>/<board>.c` and `board.cmake` for every board and module, `display.cmake`
  for every board;
- `boards/boards.cmake`: the lists the component's `CMakeLists.txt` compiles by;
- `Kconfig`: the choice, the modules' options, the hidden symbols;
- the `dependencies:` of `idf_component.yml`, between `# boards: dependencies
  generated` and `# boards: end of generated`;
- the table of boards in `README.md` and `README.ru.md`, between
  `<!-- boards:table -->` and `<!-- boards:end -->`;
- `catalog/index.json`, the list of the files of the catalog the page reads;
- the list of boards of the matrix of `.github/workflows/build.yml`, between its marks.

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
python3 tools/board_pins.py jc1060p470c --display  # 1024x600 154x86: pixels and mm, as shown
python3 tools/board_pins.py my_board --project ~/myproject --free  # a board of a program: the pins left
```

`--display` prints what `BOARD_PIXELS` and `BOARD_MM` hold, for a Makefile that has no
CMake, as the host build of a game: `HOST_DISPLAY := $(shell python3 .../board_pins.py
jc1060p470c --display)`. A board with no pixel display prints nothing and exits with 1.

The map the checks are made on, for a human to look at: every GPIO the data
names, who owns it and in which direction, with *TWO OWNERS*, *INPUT ONLY,
DRIVEN* and *NOT A GPIO OF THIS CHIP* beside the offenders.

## board_select.py

```sh
python3 tools/board_select.py cyd_s028r ~/myproject
python3 tools/board_select.py my_board ~/myproject    # a board of the program, in its components/local-boards/
python3 tools/board_select.py cyd_s028r jc8012p4a1c --current jc8012p4a1c ~/myproject
python3 tools/board_select.py --current cyd_s028r ~/myproject
python3 tools/board_select.py host --as jc8012p4a1c ~/myproject    # the computer host_jc8012p4a1c, as large as the 10-inch board, and the board when it is not there
python3 tools/board_select.py host --as cyd_s028r --as jc1060p470c ~/myproject  # two computers side by side, with their boards
```

Writes `~/myproject/sdkconfig.defaults.<board>` for each board named: the board's defaults, the lines of the
revision of its chip (`--revision`), then those of each module of `--module` that has defaults of its own (no module of
the catalog has them now: the page wires modules into a board of the program). Then `CMakePresets.json`: a preset for each board of the
project, those it had and those named, each building in `build/<board>`, and `default` for the current one, the first
named unless `--current` names another, which goes into the `current` of `selection.json` too when the project has
one. `--current` alone changes only `default` and that `current`. A board of the project starts its
lock, `dependencies.lock.<board>`, as a copy of `dependencies.lock`. A file of defaults or a `CMakePresets.json` it did
not write is not replaced. See [choosing-a-board.md](choosing-a-board.md).

In a project VS Code works on (one with `.vscode/`, or the command run from VS Code) it writes the target of the
current board for the ESP-IDF extension into `.vscode/settings.json`: `idf.customExtraVars.IDF_TARGET` and
`idf.sdkconfigFilePath`, `sdkconfig.<board>` (`tools/vscode_env.py`). The extension takes the target from them
when it starts, after a reload of the window, and puts it into new terminals as `IDF_TARGET`; `idf.buildPath`,
`build/<board>`, is where its build goes while no project configuration is chosen in it; till then a terminal of ESP-IDF needs `unset IDF_TARGET`.
Each configuration of such a project, as `idf.py reconfigure`, writes there the environment of ESP-IDF for CMake Tools,
`cmake.environment`, and adds the ESP-IDF extension and clangd to the recommendations of `.vscode/extensions.json`.

Each file it writes begins with the command that made it and the version and commit of the component. After
the component changes, `board_select.py --again ~/myproject` makes every such file of the project again the same
way, and the presets in their order with their current board, unless the page changed the `current` of
`selection.json` since (see [choosing-a-board.md](choosing-a-board.md)). A file it writes that the list of the bridge
has stays the page's: its new hash goes into the list. An `sdkconfig` made before keeps what it had: remove
`sdkconfig.<board>` to take what changed.

The configuration editor of the ESP-IDF extension (the gear) and `idf.py menuconfig` change `sdkconfig.<board>`
of the current board alone. `board_select.py --keep ~/myproject` puts what was set into the project's own
`sdkconfig.defaults`, which every board reads after its own file: the minimal configuration of ESP-IDF (savedefconfig)
and, on ESP-IDF 6, each option set on by the person (the `sdkconfig` marks the rest by a line `# default:`),
less what `sdkconfig.defaults.<board>` sets, the target, the choice of the board, its memory. An option of the board
changed there is named and not kept. The lines `sdkconfig.defaults` has stay, and an option named there takes the value
of the configuration. `idf.py save-defconfig` ("ESP-IDF: Save Default Configuration") does not do: it writes the lines
of the current board into `sdkconfig.defaults` too, and every board reads that file. Each configuration does the same
for what changed in `sdkconfig.<board>` since the one before (`board_select.py --auto-keep <board>`): a snapshot of the
`sdkconfig` of each board lies in `.boards/` of the project. An option a board left as it was, as an older `sdkconfig`
of another board with an older value, is not taken back.

## board_project.py

```sh
python3 tools/board_project.py ~/my_game --board jc8012p4a1c
python3 tools/board_project.py ~/again --selection ~/old/selection.json
python3 tools/board_project.py ~/clock-2 --board cyd_s028r --name clock_two  # a folder whose name is no name of a project
```

A new project on a board chosen by hand, without the page: the files the page writes for a new folder
(`editor/skeleton/files.json` lists them, both read the list), filled the same way, and `selection.json` with no
answers. The component comes as this copy came: from git at its commit, or from the registry at its version, as the
page writes it. `--module` takes a module that `board_select.py` sets up by its own defaults; no module of the catalog
has them now, the page wires modules to pins. `--selection` takes
the current kit of a `selection.json` with its answers; a kit the page wired has a board of the program, which is taken
from `components/local-boards/` beside that `selection.json` and named after the new project, with its wires and its
libraries in the README. The folder is empty or holds only `.git`, `.gitignore`, a README or a LICENSE; nothing in it is
replaced. The command it prints next is the one in the README of the project.

## board_bom.py

```sh
python3 tools/board_bom.py my_board --project .                        # one product
python3 tools/board_bom.py my_board --project . --units 10 --shop aliexpress  # ten, at the prices of one shop
python3 tools/board_bom.py my_board --project . --units 10 --duty 3 EUR  # with a duty per tariff code
python3 tools/board_bom.py my_board --project . --csv my_board.csv      # the lines for a spreadsheet
```

A line is what is bought as one: the board a project stands on, then the modules and devices
the project adds, the same goods on one line. The chips of a bought board are not lines, and a
board with `extends` is a variant, one purchase. So a product is written as `kind: project`
over its base board. The list counts everything, what the person has already among it: a product is bought whole, so
its total is the cost in full of the page.

Prices are ranges, so a total is a range. A line with no price is named, and the total then
reads "at least". Currencies are not converted. For a quantity the tool takes, per shop, the
offers of the largest `qty` that the quantity reaches, and of several the median, as the page does; a line sold only by
the pack is a pack. `--shop` takes a shop of `catalog/shops.json` by its name, its
title or its address, as a report does.

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
give the same for every document that passes the schema. It counts the products of a chain in the list of
goods, and, where compote of ESP-IDF and git are, packs the component as the registry would and finds in the
archive only files git tracks, none of `test/`, `.github/` or `imported/`.

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

Writes `catalog/mcu/` from ESP-IDF: `soc_caps.h`, the GPIO tables of its docs, the clock tree and the low-level
headers of LEDC, MCPWM, RMT and I2S. The boot modes of the strapping pins come from the datasheets of Espressif.

## update_rates.py

Writes `catalog/rates.json` from the reference rates of the European Central Bank, so that prices in
any currency compare on the page. It needs the network and nothing else; the page only reads the file.

## take_report.py

```sh
python3 tools/take_report.py body.md --issue 3    # the text of issue 3, into the catalog of this repository
```

Takes a price from an issue of the form `price.yml` and adds it to the file of its item as an offer. The text of an
issue comes from anyone, so it is only read as fields, and `.github/workflows/reports.yml` gives it through a file. The
workflow opens a pull request, and a person merges it; a refused report gets a comment with the reason, and an edit of the
issue is read again. A price is read as it is written in one country or another: 3.76, 3,76, 1,234.56, 1.234,56,
1 234,56, 1'234.56, 12,34,567, with the sign or the code of its currency or without. One mark before three digits, as
1,200, reads two ways and is refused with both readings. The shop is found in `catalog/shops.json` by its address
(`https://de.aliexpress.com/item/...` is `aliexpress`), its name or a name close to one (`aliexpres`); a name of two
shops, as `amazon`, is refused. An address or a name the list lacks becomes a new shop with no title, and the pull
request says to write it: `check_format.py` refuses the shop until then. A seller is taken on a marketplace or
classifieds only. `check_format.py` tries the tool on good and
bad reports.

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

## import_libraries.py

Lists the known libraries in `catalog/libraries/libraries.json`, the leading list: Arduino from `library_index.json`, ESP-IDF
from the catalog, the dependencies of the packs and a search of GitHub. Each has one entry, with the chips it names, and a
library with no chip stays a library: it may do an algorithm and drive nothing. `chip_libraries.json` beside it is an index
from a chip to that list and need not cover it. Needs `gh`, logged in.

```sh
python3 tools/import_libraries.py library_index.json.gz --date 2026-11-01
```

It lists by name and ranks nothing. Stars and dates are shown and decide nothing, and a name is all that ties most of these
libraries to a chip, so nobody read them. The registry of Espressif closes its API to robots and is not crawled.

## import_addresses.py

Writes the I2C addresses of the chips into `imported/devices/`, as `address_try` with the first as a chip comes. Run it after
`import_fritzing.py`, which rewrites that folder, and after `import_libraries.py`, whose list says which clones it reads.

```sh
python3 tools/import_addresses.py --list
python3 tools/import_addresses.py --esphome esphome/components --libraries CLONES --date 2026-11-01
```

The sources are the Python of ESPHome and the headers of libraries with a permissive license, in folders named `owner__repo`.
Only text is read. The board packs are no source: they give addresses in the 8-bit form, and `import_board_manager.py`
shifts those of its boards. What a filter refused goes to `imported/report_addresses.json`. `--compare` prints where a table
of Tasmota differs: it is under GPL, so it stays a check and goes nowhere.

The list can be short, so the solver takes a clash on these addresses as an unknown and no refusal.

## audit.py

Keeps what audits found in a library in `audit.json` beside its record, one entry for each commit read.

```sh
python3 tools/audit.py take esp-idf/jef-sure/pn532 RESULT --src COPY --rubric pn532 --rubric-version 1 --commit SHA --by WHO --version 0.7.6 --tag v0.7.6 --blind
python3 tools/audit.py changes esp-idf/jef-sure/pn532 --clone CLONE --to v0.7.7
python3 tools/audit.py carry esp-idf/jef-sure/pn532 READING --src COPY --clone CLONE --to v0.8.0 --commit SHA --by WHO --version 0.8.0 --tag v0.8.0 --blind
```

`take` checks that every quote of a result stands in the copy that was read, then keeps the file and the line: with the
commit they say the same, and the code of others stays out of this repository. `changes` compares the last entry with a newer
commit, or with the working tree of a clone when `--to` is absent, and lists what to read again: entries whose lines changed,
entries whose file changed elsewhere, new files. A `no` has no line to compare, so new code can change any of them. The clone
is only read. `carry` makes the entry of a newer commit from the last one: what stands on unchanged lines stays with its lines
moved, a reading of what changed replaces the rest, and it refuses when something on changed lines was not read again.

## boards_mcp.py

Puts the agent of a person beside the page. It runs as an MCP server of a client, serves the page on 127.0.0.1 and takes no
key: the model is the agent that started it. Once, to give it to the agent:

```sh
python3 tools/boards_mcp.py --install
```

With the command `claude` on the machine this gives it to Claude Code for every folder (`claude mcp add -s user`). Without
it, it writes `.mcp.json` in the current folder, beside the servers that file names, and prints the same entry for a client
that keeps it elsewhere. The paths are full, so the folder of the agent does not matter. Then start the agent again and ask
it to help choose the hardware of a device.

One install serves every project. A server started in a project with its own copy of the component in
`managed_components/` hands over to that copy at once: the catalog, the page and `board_select.py` are those of the
version the project builds with. The copy the install was made from serves folders with no copy of their own; when it
is removed, install again.

The agent gives the person a link with a token. On that page a dialog appears, and once it starts it takes the column of the roles, whose search stays: the model reads the description, the blocks
and the best kits, sets the blocks with their variants and parts, the conditions of the solver, and writes a description that a
project keeps as `DESCRIPTION.md`. What the person fixes is theirs: the pin of a block, a part chosen in it, or the button
`pin this board` of a card. The server refuses the model a change of it, the page refuses it again, and the solver keeps a
fixed part for its block and tries only a fixed board.
The field on top is the theme the model starts from, and the dialog develops it: a changed theme reaches the model with the next answer of `wait_for_person`. The solver stays in the page. A page opened any other way has no dialog and works as before.

With no agent the server still gives the page, its solver and the writes of a project, for the folder it runs in:

```sh
python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve   # or --project DIR, --port N
```

It prints the link of the page and serves until Ctrl-C. The link says that no model talks, so the page shows no
dialog.

The server can write the files of a project for the page, so the page writes from the integrated browser of VS Code too:
the files go through the server, whatever the browser lets a page do with folders. It writes into one folder, the one the agent works in or `--project DIR`: an empty folder for a new
project, or one with `CMakeLists.txt`, never the component itself. The rules are those of `tools/project_writer.py`:

- nothing is written unless the person allows it, every time or for ever; for ever is kept for the user, in
  `$XDG_CONFIG_HOME/jef-sure-boards/allowed.json`, by the path and the name of the project, so a project cannot allow itself;
- no path outside the folder, through a link or not, and none of `.git`, a hidden path but `.gitignore`, `build*`,
  `managed_components` or `dependencies.lock*`;
- `.boards/written.json` of the project keeps the hash of each file the server wrote. A file not in it, or changed since, is
  the person's and is replaced only when the person ticks it; after a clone the list is empty, so the first write asks;
- what `board_select.py --again` makes after the files is made on a copy of the project first and goes by the same rule: the
  defaults, the presets and the glue of a board of the program, so no command is left to the person;
- a write is all or nothing, each file goes to disk by a rename, the list last;
- a request that changes anything carries the token in its header and comes from the page of this server (its `Origin`).

## sync_versions.py

```sh
python3 tools/sync_versions.py
```

Fills `versions` of the `esp-idf` library records: from the component registry what each version
is built against and requires, from the tags of git the versions the registry has not. A version the registry does not have yet stays as written.

## The page

`editor/index.html` shows what to build and on what, and edits the files of the catalog. It needs no
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

A block asks of the data of its part through the questions of its role: a question with `limit.field`, the path of a value
in the data of a part with its variant applied, and `limit.fits`, how the value meets the answer (`up_to`, `down_to`,
`at_least`, `at_most`, `includes`, `is`), as `co2_up_to` on `provides.air.specified`. The answer lies in `asks` of the block,
so two temperature blocks, a room and an oven, ask different ranges and are two needs. A part whose data has no such value
stays, and the kit names it as an unknown. A measured question of a class with `"asked": "block"` is asked of each block too,
as the reading distance and the cards of a reader, the diagonal and the shape of a graphics display, the outputs of a
chain: two readers ask their own, and two blocks of one role are always two parts. Its `limit.of` and `limit.variant`
may be lists, and a block with no variant chosen is asked what any of them is. The distance between readers stays one
question of the page. Of two displays from modules, the first block gives the primary one. The page shows these fields in the block; the model sets them with `edit_blocks`,
and `roles` lists them. The platform is asked without a version: a kit names the versions that take its chip and its
libraries, and a version is fixed only when the person chooses one.

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

Kits come in this order: those that fit, the fewest unknowns, the least worth of what the board has and nobody asked for
(a camera, touch, Ethernet; not the button of a strapping pin), the fewest modules, the fewest wires, then the price. A part of a
board is worth the lowest price of its chip by the piece, from `price` of its entry in `catalog/devices`, times its
`config.count`. A part that names no chip with a price weighs the cheapest chip of the catalog that gives its role and variant, as
`led_smd`, `led_rgb_5050` and `ws2812b`; with none of those, the cheapest module of its role and variant, else of its role, its
class or of all, by the piece. A price of nothing is no price, and a part weighs at least a cent: nothing is free. The priced
modules of `imported-shops/` stay out of the repository, so only a chip with a price gives the same order everywhere. A budget makes the price a criterion: it then comes right after the unknowns, and a
missing price counts as an unknown. What the person has already, boards and modules named under *What you have
already* (`have` of the answers), costs nothing in the price to buy now, and on a board they have what nobody asked
for weighs nothing: a board one has comes before a dev board and a module that would do. Beside it the card shows the
cost in full, everything bought, as for making the thing again; `selection.json` keeps both, `price` and `cost` of
each board, and the order and a budget go by the price to buy now. `tools/check_format.py` gives the kits of
`test/solver/` to the generator as well.

A block with nothing chosen in it takes the part of its role of the board selected, pinned or current, with what its data
gives, marked "from the board"; when the board changes it goes back to any and takes the part of the new one. What the
person chose or changed in a block stays. The Part of a block offers the parts of the board selected first, before the
modules of the catalog.

The cards wait for the first block on the canvas: with nothing asked every board fits. `make a project…` on a card, while
the project has no boards, or *make the project of these boards…* asks for a folder, and the folder decides what happens:

- an empty folder, or one with only `.git`, a README, a licence and `.gitignore`, gets a whole
  project. What already lies there stays;
- a folder with a `CMakeLists.txt` is a program, and gets only its board in `components/local-boards/`; a program with
  boards of its own moves as [moving-a-program.md](moving-a-program.md) says;
- any other folder is refused.

A program with a `selection.json` keeps its name and its boards. The name of the project is the one there, and from
`boards_mcp.py` the field is locked; a kit it has keeps the name of its board; a kit made from its card joins the boards
the program has and becomes the current one, and the boards not on the page stay in `selection.json` as they were.

The list of what would happen comes first and nothing is written before `write`. A board file that
differs is replaced only when ticked, and nothing is ever removed. If a file changed after the list
was made, nothing is written at all. A kit with no module, and with nothing of its board left unused, gets no
board file: the project names the board of the catalog. A part of the board the project leaves unused (`used: false`)
takes a board of the program, as a module does. The page does not talk to GitHub: the result
is a folder, for git or for nothing.

The board is chosen before the first build, because the dependencies follow from what it has:
`board_select.py`, then `idf.py build`. Each board builds in a directory of its own, so another board needs
nothing more.

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

`.github/workflows/build.yml`: `check_boards.py --host-syntax`, `check_format.py` and
`board_pins.py --all`, then `examples/hello_board` for every board and
`examples/hello_lvgl` for every board with a graphics display, under two
versions of ESP-IDF, plus one build of `hello_board` with the 2004 module, a project that leaves parts alone,
`examples/local_boards`, `examples/multi_board`, and `examples/hello` as the registry hands it out (taken from the
archive compote packs, the component at the commit), each in its own job.
The list of boards of the matrix is written by `boards_gen.py --all` from the data, between its marks.
