# Imported data

What `tools/import_board_manager.py`, `tools/import_fritzing.py` and `tools/import_addresses.py`, run in this order, took from the data of others. All about libraries lies in `catalog/libraries/`.
The solver reads this tree after `catalog/`.
It has no glue and no build in CI. The package of the component carries it, with `licenses/`, for the page and the solver.

Nothing here is checked by us: every file has `origin`, and its level is `extracted`. A board that proves itself moves
to `catalog/` through a pull request with its glue and a green build.

- `boards/`, `modules/`, `devices/`: the layout of `catalog/`. A device here is a stub: what the boards and the parts
  say of a chip. A module names its roles in `provides`; the words of `catalog/roles.json` found them, so they can be wrong.
- `report.json`: where the data came from, the boards refused and why, the pins of the boards the catalog has against
  the packs, what the format has no place for, the libraries the packs name.
- `report_fritzing.json`: the same for the parts of Fritzing, which are under CC BY-SA 3.0: only facts are taken.
- `report_addresses.json`: the source of each I2C address in `devices/` and the values refused. The list of a chip can be short.
- No pictures: a picture of others whose license MIT cannot take, as the Fritzing drawings under CC BY-SA 3.0, stays out.
- `licenses/`: the license and the notice of each pack. The packs of Espressif may be used only with Espressif products.

`imported-shops/` beside this tree is not in the repository: it holds what comes from the lists of shops, prices and
roles from their sections, and goes over this tree. There is no license to publish it.

Regenerate it, do not edit it: a correction goes into `catalog/`, which is read first.
