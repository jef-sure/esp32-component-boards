#!/usr/bin/env python3
"""
Checks of the data format. Needs jsonschema and node: the Python of ESP-IDF has the first.

    python3 tools/check_format.py [--fix]

1. every file of catalog/ and of test/format/catalog/ passes the schema;
2. every board of the catalog passes the schema, the merge, the schema of the result and the rules;
3. every case of test/format/good/ passes all of them;
4. every case of test/format/bad/ fails with the message it expects;
5. rules.py and editor/rules.js find the same in every board that reaches the rules;
6. resolve.py and editor/resolve.js give the same for every document that passes the schema;
7. jsonschema and editor/schema.js agree on every document and on spoiled copies of them, dump of
   resolve.py and catalogJson of resolve.js write the same, boards_gen.py and editor/pins.js find
   the same pins;
8. the solver of the editor gives what the cases of test/solver/ expect, and catalog/questions.json
   passes the schema;
9. board_bom.py counts each product of a chain, and a price of one piece as the page does;
10. the archive compote packs for the registry holds only files git tracks, none of test/, .github/ or
   imported/ (when compote of ESP-IDF and git are there);
11. take_report.py takes a price and a shop from an issue, and every offer names a shop of catalog/shops.json;
12. board_select.py writes for one board what it writes for several, a preset for each board in the order named and default
   for the current one; a board named again becomes current, --current changes only default, --again makes them again by
   selection.json, and a CMakePresets.json or a file of defaults of another is left alone;
13. the lines of CMake that read the defaults of the board and its lock are the same in editor/skeleton/, the examples and
   choosing-a-board.md, the program of the quick start is examples/hello/main/main.c, and examples/hello, which the
   registry hands out, is the skeleton filled for the registry; --fix writes it so;
14. board_project.py --selection takes back a kit the page wired, with its board of the program under the new name;
15. the documents of the catalog and shops.json lie in the form resolve.dump writes; --fix writes them so.
"""
import copy
import hashlib
import http.client
import json
import os
import pathlib
import random
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

import jsonschema

import boards_gen
import audit
import board_bom
import project_writer
import resolve
import rules
import take_report

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "test" / "format"
SCHEMA = json.loads((ROOT / "catalog" / "format.schema.json").read_text())
jsonschema.Draft202012Validator.check_schema(SCHEMA)
RAW = jsonschema.Draft202012Validator(SCHEMA)
RESOLVED = jsonschema.Draft202012Validator({"$ref": "#/$defs/resolved", "$defs": SCHEMA["$defs"]})
QUESTIONS = jsonschema.Draft202012Validator({"$ref": "#/$defs/questions", "$defs": SCHEMA["$defs"]})
RATES = jsonschema.Draft202012Validator({"$ref": "#/$defs/rates", "$defs": SCHEMA["$defs"]})
SHOPS = jsonschema.Draft202012Validator({"$ref": "#/$defs/shops", "$defs": SCHEMA["$defs"]})
JUDGEMENTS = jsonschema.Draft202012Validator({"$ref": "#/$defs/judgements", "$defs": SCHEMA["$defs"]})
ROLES = jsonschema.Draft202012Validator({"$ref": "#/$defs/roles", "$defs": SCHEMA["$defs"]})
RULES = json.loads((ROOT / "catalog" / "rules.json").read_text())
FILE_RULES = {**RULES, "rules": [rule for rule in RULES["rules"] if rule.get("in_files")]}
LEVELS = SCHEMA["$defs"]["level"]["enum"]
resolve.ROOTS.insert(1, TESTS / "catalog")  # before imported/: a stub there must not hide a chip of the cases


def no_nulls(value):
    """A layer may hold null to remove a field: the shape of the rest is what the schema checks."""
    if isinstance(value, dict):
        return {key: no_nulls(item) for key, item in value.items() if item is not None}
    return value


def errors_of(validator, doc, stage):
    found = []
    for error in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.path))):
        found.append(f"{stage}: {'/'.join(map(str, error.path))}: {error.message[:150]}")
    return found


def stages(doc):
    """The problems of the first stage that has any, and the resolved board when it got that far."""
    problems = errors_of(RAW, no_nulls(doc) if "extends" in doc else doc, "schema")
    if problems:
        return problems, None
    try:
        resolved = resolve.resolve(doc)
    except resolve.Refused as error:
        return [f"resolve: {error}"], None
    problems = errors_of(RESOLVED, resolved, "resolved")
    if problems:
        return problems, None
    return [f"rule {found['rule']}: {found['message']}" for found in rules.check(resolved, RULES)], resolved


def documents():
    """Every document that reaches the loader, as it lies in its file."""
    for path in sorted((ROOT / "catalog").glob("boards/*/board.json")) + sorted((ROOT / "catalog").glob("modules/*/module.json")):
        yield f"data_{path.parent.name}", json.loads(path.read_text())
    for path in sorted((TESTS / "good").glob("*.json")):
        yield f"good_{path.stem}", json.loads(path.read_text())
    for path in sorted((TESTS / "bad").glob("*.json")):
        yield f"bad_{path.stem}", json.loads(path.read_text())["board"]


def attempt(call, *args):
    try:
        return call(*args)
    except resolve.Refused as error:
        return {"refused": str(error)}


def loaders_differ(ordered):
    """Gives resolve.py and editor/resolve.js the same input. Returns the number of documents, those refused and where the two part."""
    tdeck = json.loads((TESTS / "good" / "tdeck_like.json").read_text())
    versions = [[a, b, scheme] for pair in ordered for a, b, scheme in (pair, (pair[1], pair[0], pair[2]))] + [["1.0", "1.0.0", "decimal"]]
    given = {
        "docs": {name: doc for name, doc in documents() if not errors_of(RAW, no_nulls(doc) if "extends" in doc else doc, "schema")},
        "overlaid": [[tdeck, [{"devices": {"touch": None}}]]],
        "levels": LEVELS,
        "versions": versions,
        "settings": [{"target": "esp32p4", "psram_mb": 32, "revision": "1.3"}, {"target": "esp32p4", "psram_mb": 32, "revision": "3.2"}, {"target": "esp32p4", "revision": "3.2", "cpu_mhz": 360},
                     {"target": "esp32"}],
        "devices": [{"chip": "pn5180", "firmware_version": version} for version in ("3.A", "3.9", "3.4", "9.9")] + [{"chip": "scd4x", "variant": "scd41"}, {"chip": "scd4x", "variant": "none"}],
        "libraries": [["esp-idf/owner_a/idf_library", version] for version in ("1.1.0", "1.0.0", "0.8.0")],
    }
    with tempfile.TemporaryDirectory() as out:
        path = pathlib.Path(out) / "given.json"
        path.write_text(json.dumps(given))
        run = subprocess.run(["node", str(TESTS / "resolve_cli.js"), str(path)], capture_output=True, text=True)
    if run.returncode:
        return len(given["docs"]), 0, [run.stderr[:800]]
    found = json.loads(run.stdout)
    key = resolve.version_key
    mine = {
        "resolved": {name: attempt(resolve.resolve, doc) for name, doc in given["docs"].items()},
        "overlaid": [attempt(resolve.resolve, doc, layers) for doc, layers in given["overlaid"]],
        "versions": [(key(a, scheme) > key(b, scheme)) - (key(a, scheme) < key(b, scheme)) for a, b, scheme in versions],
        "settings": [attempt(resolve.chip_settings, mcu) for mcu in given["settings"]],
        "devices": [attempt(resolve.apply_type, dict(device)) for device in given["devices"]],
        "libraries": [resolve.library_at(resolve.library(name), version)["chips"] for name, version in given["libraries"]],
    }
    mine["trust"] = {name: [list(resolve.trust(board, f"devices.{device}", LEVELS)) for device in board["devices"]] for name, board in mine["resolved"].items() if "refused" not in board}
    differ = [f"{part} {name}" for name in mine["resolved"] for part in ("resolved", "trust") if mine[part].get(name) != found[part].get(name)]
    differ += [part for part in ("overlaid", "versions", "settings", "devices", "libraries") if mine[part] != found[part]]
    return len(given["docs"]), sum("refused" in board for board in mine["resolved"].values()), differ


# what no document of the catalog reaches: two forms of a oneOf that both fit, the branch of an else
ONE_OF = {"oneOf": [{"type": "integer"}, {"minimum": 0}]}
IF_ELSE = {"if": {"type": "string"}, "then": {"minLength": 2}, "else": {"minimum": 3}}
KEYWORDS = [[ONE_OF, 1], [ONE_OF, -1], [ONE_OF, 0.5], [ONE_OF, -0.5], [IF_ELSE, "a"], [IF_ELSE, "ab"], [IF_ELSE, 1], [IF_ELSE, 5]]


def spoiled(doc, rng):
    """A copy of a document with one place changed: a field gone, of another type, or one that does not exist."""
    out = copy.deepcopy(doc)
    node, places = out, []
    while isinstance(node, (dict, list)) and node:
        places.append(node)
        node = node[rng.choice(list(node))] if isinstance(node, dict) else rng.choice(node)
    place = rng.choice(places)
    key = rng.choice(list(place)) if isinstance(place, dict) else rng.randrange(len(place))
    choice = rng.randrange(4)
    if choice == 0 and isinstance(place, dict):
        del place[key]
    elif choice == 1:
        place[key] = "text"
    elif choice == 2:
        place[key] = -1
    elif isinstance(place, dict):
        place["no_such_field"] = 1
    else:
        place.append(place[key])
    return out


def documents_under(root):
    """The files of a tree that are documents of the format: its own files and the lists of libraries are not."""
    return [path for path in sorted(root.rglob("*.json")) if path.parent != root and path.parent != root / "libraries"]


def editor_differs(reached):
    """Gives jsonschema, dump and pins_of of Python and their JS the same input. Returns the counts and where the two part."""
    rng = random.Random(1)
    files = {str(path.relative_to(ROOT)): json.loads(path.read_text()) for root in (ROOT / "catalog", TESTS / "catalog") for path in documents_under(root)}
    docs = {**dict(documents()), **files}
    plain = {name: no_nulls(doc) if "extends" in doc else doc for name, doc in docs.items()}
    raw = {**plain, **{f"{name}, spoiled {i}": spoiled(doc, rng) for name, doc in plain.items() for i in range(6)}}
    boards, modules = boards_gen.read_all(ROOT / "catalog")
    wired = {board["name"]: resolve.resolve(json.loads((ROOT / "catalog" / "boards" / board["name"] / "board.json").read_text())) for board in boards}
    given = {"raw": raw, "resolved": reached, "dumped": files, "wired": wired, "keywords": KEYWORDS}
    with tempfile.TemporaryDirectory() as out:
        path = pathlib.Path(out) / "given.json"
        path.write_text(json.dumps(given))
        run = subprocess.run(["node", str(TESTS / "editor_cli.js"), str(path)], capture_output=True, text=True)
    if run.returncode:
        return 0, 0, [run.stderr[:800]]
    found = json.loads(run.stdout)
    differ = [f"schema {name}" for name, doc in raw.items() if RAW.is_valid(doc) != found["raw"][name]]
    differ += [f"resolved schema {name}" for name, doc in reached.items() if RESOLVED.is_valid(doc) != found["resolved"][name]]
    differ += [f"keywords {schema} {value}" for (schema, value), valid in zip(KEYWORDS, found["keywords"]) if jsonschema.Draft202012Validator(schema).is_valid(value) != valid]
    differ += [f"dump {name}" for name, doc in files.items() if resolve.dump(doc) != found["dumped"][name]]
    for board in boards:
        theirs = found["pins"][board["name"]]
        mine = {str(pin): {**entry, "owners": sorted(entry["owners"])} for pin, entry in boards_gen.pin_map(board).items()}
        if mine != {pin: {**entry, "owners": sorted(entry["owners"])} for pin, entry in theirs["map"].items()} or boards_gen.pin_problems(board) != theirs["problems"]:
            differ.append(f"pins {board['name']}")
    return len(raw), sum(not RAW.is_valid(doc) for doc in raw.values()), differ


def package_wrong():
    """The archive of the registry holds only files git tracks, none of test/, .github/ or imported/: the manager of
    components does not read .gitignore, and an include it applies after exclude brings back what exclude took."""
    compote = pathlib.Path(sys.executable).parent / "compote"
    if not compote.exists() or not (ROOT / ".git").exists():
        print("package: not checked, compote or git is not here")
        return False
    with tempfile.TemporaryDirectory() as out:
        run = subprocess.run([str(compote), "component", "pack", "--name", "boards", "--dest-dir", out, "--project-dir", str(ROOT)], capture_output=True, text=True)
        if run.returncode:
            print(f"package: compote component pack failed: {run.stderr.strip()[-300:]}")
            return True
        with tarfile.open(next(pathlib.Path(out).glob("*.tgz"))) as archive:
            packed = {member.name.removeprefix("./") for member in archive.getmembers() if member.isfile()}
    tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.splitlines())
    wrong = sorted(packed - tracked) + sorted(name for name in packed if name.split("/")[0] in ("test", ".github", "imported", "imported-shops"))
    print(f"package: {len(packed)} files, {len(wrong)} wrong {wrong[:5]}")
    return bool(wrong)


def goods_wrong():
    """board_bom.py counts each product of a chain: two MAX7219 modules on the same wires are a line of two."""
    doc = json.loads((TESTS / "good" / "chain_of_modules.json").read_text())
    with tempfile.TemporaryDirectory() as folder:
        place = pathlib.Path(folder) / resolve.LOCAL_BOARDS / "boards" / doc["name"]
        place.mkdir(parents=True)
        (place / "board.json").write_text(json.dumps(doc))
        root = resolve.add_project(folder)
        try:
            _, lines = board_bom.lines_of(doc["name"])
        finally:
            resolve.ROOTS.remove(root)
    counted = [line["count"] for line in lines if line["title"] == "MAX7219 matrix, four 8x8 in a row"]
    wrong = [f"the chain of two counts {counted}"] if counted != [2] else []
    # a price of one piece by the cases of the page: the median of the reports of a shop, the tier one piece reaches, the
    # newest report of a seller
    for name in ("median_of_reports", "tiers_of_reports", "newest_of_a_seller"):
        case = json.loads((TESTS.parent / "solver" / f"{name}.json").read_text())
        offers = {key: offer for key, offer in case["change"]["esp32_devkit"]["price"].items() if offer}
        costs = board_bom.costs_of({"title": "the case", "price": offers}, 1, None)
        if costs != (1, {"EUR": (case["cost"]["low"], case["cost"]["high"]) * 2}):
            wrong.append(f"{name}: one piece costs {costs}")
    # what is sold by the pack is bought by the pack, as test/solver/pack_price.json for the page: twenty for two
    pack = json.loads((TESTS.parent / "solver" / "pack_price.json").read_text())["modules"]["pack_reader"]
    costs = board_bom.costs_of(pack, 2, None)
    if costs != (20, {"EUR": (1, 1, 20, 20)}):
        wrong.append(f"two of a pack of twenty cost {costs}")
    # a low of 0 is a bound, "less than 3", and counts as 3, as on the page
    costs = board_bom.costs_of({"title": "the case", "price": {"less": {"shop": "aliexpress", "currency": "EUR", "range": [0, 3], "date": "2026-11-04"}}}, 1, None)
    if costs != (1, {"EUR": (3, 3, 3, 3)}):
        wrong.append(f"less than 3 costs {costs}")
    print(f"goods: {'0 wrong' if not wrong else '; '.join(wrong)}")
    return len(wrong)


def presets_wrong():
    """board_select.py writes for one board what it writes for several, a preset for each in the order named, and leaves a
    CMakePresets.json or a file of defaults of another alone."""
    wrong = []

    def select(*words, fails=False):
        """board_select.py with these words on the project; a result it should not give is one of the wrong."""
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "board_select.py"), *words, str(project)], capture_output=True, text=True)
        if bool(done.returncode) != fails:
            wrong.append(f"board_select.py {' '.join(words)}: exit {done.returncode}: {(done.stderr.strip().splitlines() or [''])[-1]}")
        return done.returncode

    def presets(*fields):
        written = project / "CMakePresets.json"
        return [tuple(item[field] if field in item else item["cacheVariables"][field] for field in fields)
                for item in json.loads(written.read_text())["configurePresets"]] if written.exists() else None

    with tempfile.TemporaryDirectory() as folder:
        project = pathlib.Path(folder)
        (project / "CMakeLists.txt").write_text("")
        lock = "dependencies:\n  idf:\n    version: 6.1.0\n"
        (project / "dependencies.lock").write_text(lock)
        # one board gets what several get: its file of defaults and its preset
        select("cyd_s028r")
        files = sorted(path.name for path in project.glob("sdkconfig.defaults*"))
        if presets("name", "binaryDir") != [("default", "build/cyd_s028r"), ("cyd_s028r", "build/cyd_s028r")] or files != ["sdkconfig.defaults.cyd_s028r"]:
            wrong.append(f"one board made the presets {presets('name', 'binaryDir')} and {files}")
        select("cyd_s028r", "jc4827w543c")
        # the lock of the project is where the lock of each board starts
        if not all((project / f"dependencies.lock.{board}").exists() and (project / f"dependencies.lock.{board}").read_text() == lock for board in ("cyd_s028r", "jc4827w543c")):
            wrong.append("the lock of a board is not a copy of the lock of the project")
        made = presets("name", "binaryDir", "IDF_TARGET")
        if made != [("default", "build/cyd_s028r", "esp32"), ("cyd_s028r", "build/cyd_s028r", "esp32"), ("jc4827w543c", "build/jc4827w543c", "esp32s3")]:
            wrong.append(f"the presets are {made}")
        # another current board changes default only
        select("--current", "jc4827w543c")
        if presets("name", "binaryDir") != [("default", "build/jc4827w543c"), ("cyd_s028r", "build/cyd_s028r"), ("jc4827w543c", "build/jc4827w543c")]:
            wrong.append(f"after --current the presets are {presets('name', 'binaryDir')}")
        # a board named alone again becomes the current one, and the boards keep their order
        select("cyd_s028r")
        if presets("name", "binaryDir") != [("default", "build/cyd_s028r"), ("cyd_s028r", "build/cyd_s028r"), ("jc4827w543c", "build/jc4827w543c")]:
            wrong.append(f"a board named again made the presets {presets('name', 'binaryDir')}")
        # a file of defaults it did not write is not replaced
        own = project / "sdkconfig.defaults.esp32_devkit"
        own.write_text('CONFIG_IDF_TARGET="esp32"\n')
        select("esp32_devkit", fails=True)
        if own.read_text() != 'CONFIG_IDF_TARGET="esp32"\n':
            wrong.append("a file of defaults written by hand was replaced")
        own.unlink()
        # a copy of the file of one board under the name of another would build the first under that name
        own.write_text((project / "sdkconfig.defaults.cyd_s028r").read_text())
        select("--again", fails=True)
        own.unlink()
        # the files a page writes first, the command in their first line and the order in selection.json: --again makes the rest
        for path in project.glob("sdkconfig.defaults.*"):
            path.write_text(f"# board_select.py {path.name.split('.')[-1]}\n")
        (project / "CMakePresets.json").unlink()
        page = {"boards": [{"board": "jc4827w543c"}, {"board": "cyd_s028r"}], "current": "cyd_s028r"}
        (project / "selection.json").write_text(json.dumps(page))
        select("--again")
        made = presets("name", "binaryDir")
        if made != [("default", "build/cyd_s028r"), ("jc4827w543c", "build/jc4827w543c"), ("cyd_s028r", "build/cyd_s028r")] or "CONFIG_IDF_TARGET" not in (project / "sdkconfig.defaults.cyd_s028r").read_text():
            wrong.append(f"--again from the files of a page made the presets {made}")
        # a current board a command chose stays through --again, and selection.json names it, so the page shows it
        select("--current", "jc4827w543c")
        select("--again")
        if presets("name", "binaryDir")[0] != ("default", "build/jc4827w543c"):
            wrong.append(f"--again undid the current board of --current: {presets('name', 'binaryDir')}")
        if json.loads((project / "selection.json").read_text()).get("current") != "jc4827w543c":
            wrong.append("--current left another current board in selection.json")
        # the board current before a command, named on the page again, is taken
        (project / "selection.json").write_text(json.dumps({**page, "current": "cyd_s028r"}))
        select("--again")
        if presets("name", "binaryDir")[0] != ("default", "build/cyd_s028r"):
            wrong.append(f"--again did not take back the current board the page named: {presets('name', 'binaryDir')}")
        # presets with no record were made with no selection.json: the current board the page wrote since is taken
        select("--current", "cyd_s028r")
        doc = json.loads((project / "CMakePresets.json").read_text())
        doc["vendor"]["jef-sure/boards"].pop("follows", None)
        (project / "CMakePresets.json").write_text(json.dumps(doc))
        (project / "selection.json").write_text(json.dumps({**page, "current": "jc4827w543c"}))
        select("--again")
        if presets("name", "binaryDir") != [("default", "build/jc4827w543c"), ("jc4827w543c", "build/jc4827w543c"), ("cyd_s028r", "build/cyd_s028r")]:
            wrong.append(f"--again did not take the current board the page wrote over presets with no record: {presets('name', 'binaryDir')}")
        for path in project.glob("sdkconfig.defaults.*"):
            path.unlink()
        (project / "CMakePresets.json").write_text('{"version": 3, "configurePresets": []}\n')
        select("cyd_s028r", "jc4827w543c", fails=True)
        if list(project.glob("sdkconfig.defaults.*")) or presets("name"):
            wrong.append("a CMakePresets.json of another was replaced, or defaults written beside it")
    print(f"presets: {'0 wrong' if not wrong else '; '.join(wrong)}")
    return len(wrong)


def taken_back_wrong():
    """board_project.py --selection takes back a kit the page wired: its board of the program under the new name, the stub of
    its defaults, the library the program calls in the manifest, and the wires in the README."""
    wrong = []
    board = {"format": "jef-sure/boards", "format_version": 2, "kind": "project", "name": "old_esp32_devkit", "extends": "esp32_devkit",
             "title": "ESP32 DevKit, 4 MB with Round 1.53-inch TFT on an ST77916, PN532 module",
             "buses": {"qspi": {"spi2": {"sclk": 4, "d0": 21, "d1": 22, "d2": 25, "d3": 26, "hz": 40000000}}, "spi": {"spi3": {"mosi": 23, "miso": 19, "sclk": 18}}},
             "devices": {"led": {"used": False}},
             "modules": {"display": {"module": "tft153_st77916", "on": {"qspi.spi2": {"cs": 27}}, "pins": {"rst": 32, "backlight": 33}, "supply": {"VCC": "3V3"}},
                         "nfc": {"module": "pn532_module", "on": {"spi.spi3": {"cs": 5}}, "supply": {"VCC": "3V3"}}}}
    entry = {"board": "old_esp32_devkit", "base": "esp32_devkit", "modules": [{"name": "tft153_st77916", "count": 1, "on": "qspi"}, {"name": "pn532_module", "count": 1, "on": "spi"}],
             "libraries": [{"name": "jef-sure/dgx", "version": "0.10.3"}, {"name": "jef-sure/pn532", "version": "0.8.1"}], "says": []}
    with tempfile.TemporaryDirectory() as folder:
        old, new = pathlib.Path(folder) / "old", pathlib.Path(folder) / "new"
        (old / "components" / "local-boards" / "boards" / "old_esp32_devkit").mkdir(parents=True)
        (old / "components" / "local-boards" / "boards" / "old_esp32_devkit" / "board.json").write_text(json.dumps(board))
        (old / "selection.json").write_text(json.dumps({"format": "jef-sure/boards", "format_version": 3, "name": "old", "currency": "EUR", "answers": {"blocks": []},
                                                        "boards": [entry], "current": "old_esp32_devkit", "others": [], "rejected": []}))
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "board_project.py"), str(new), "--selection", str(old / "selection.json"), "--name", "fresh"], capture_output=True, text=True)
        if done.returncode:
            wrong.append(f"board_project.py --selection: {(done.stderr.strip().splitlines() or [''])[-1]}")
        else:
            local = new / "components" / "local-boards" / "boards" / "fresh_esp32_devkit" / "board.json"
            if not local.exists() or json.loads(local.read_text())["name"] != "fresh_esp32_devkit" or "nfc" not in json.loads(local.read_text())["modules"]:
                wrong.append("the board of the program is not taken under the new name")
            if not (new / "sdkconfig.defaults.fresh_esp32_devkit").read_text().startswith("# board_select.py fresh_esp32_devkit\n"):
                wrong.append("the stub of the defaults does not name the board of the program")
            manifest = (new / "main" / "idf_component.yml").read_text()
            if 'jef-sure/pn532: "^0.8.1"' not in manifest or "jef-sure/dgx" in manifest:
                wrong.append("the manifest does not name the library the program calls, or names one the board starts")
            if "| PN532 module | CS | GPIO 5 of spi.spi3 |" not in (new / "README.md").read_text():
                wrong.append("the README has not the wires of the board of the program")
            selection = json.loads((new / "selection.json").read_text())
            if (selection["name"], selection["current"]) != ("fresh", "fresh_esp32_devkit"):
                wrong.append(f"selection.json names {selection['name']}, {selection['current']}")
    print(f"taken back: {'0 wrong' if not wrong else '; '.join(wrong)}")
    return len(wrong)


def canonical_wrong(fix):
    """The documents of the catalog lie in the form resolve.dump writes, as the page and the tools write them: one in
    another form shows on the page as edited, and a tool that writes into it changes every line. --fix writes them so.
    The schema, the rules, the questions and the roles are written by hand and read only."""
    off = []
    for path in [*documents_under(ROOT / "catalog"), ROOT / "catalog" / "shops.json"]:
        text = path.read_text()
        made = resolve.dump(json.loads(text)) + "\n"
        if text != made:
            if fix:
                path.write_text(made)
            else:
                off.append(str(path.relative_to(ROOT)))
    return [f"{name}: not in the form resolve.dump writes: check_format.py --fix" for name in off]


def snippets_differ():
    """The lines of editor/skeleton/CMakeLists.txt that read the defaults of the board and set its lock, word for word in
    the examples and in the documents a person copies them from."""
    text = (ROOT / "editor" / "skeleton" / "CMakeLists.txt").read_text()
    start = text.index("# BOARD=<board>")
    defaults = text[start:text.index("\nendif()\n", start) + len("\nendif()\n")]
    lock = re.search(r"^if\(BOARD\)\n    idf_build_set_property\(DEPENDENCIES_LOCK [^\n]*\nendif\(\)\n", text, flags=re.M)[0]
    # the quick start takes the CMake with the example of the registry, which example_wrong() compares whole
    copies = ["docs/en/choosing-a-board.md", "docs/ru/choosing-a-board.md", "examples/hello_board/CMakeLists.txt",
              "examples/hello_lvgl/CMakeLists.txt", "examples/local_boards/CMakeLists.txt", "examples/multi_board/CMakeLists.txt", "examples/sound_level/CMakeLists.txt"]
    wrong = [f"{name}: the lines that read the defaults of the board differ from editor/skeleton/CMakeLists.txt" for name in copies
             if defaults not in (ROOT / name).read_text() or lock not in (ROOT / name).read_text()]
    # the program of the quick start is the example the registry hands out, which a new project of the page takes
    program = (project_writer.EXAMPLE / "main" / "main.c").read_text()
    return wrong + [f"{guide}: its program is not examples/hello/main/main.c" for guide in ("docs/en/quick-start.md", "docs/ru/quick-start.md")
                    if re.search(r"```c\n(.*?)```", (ROOT / guide).read_text(), flags=re.S)[1] != program]


def example_wrong(fix):
    """examples/hello is what editor/skeleton/ makes for the registry: a project made from it is one board_project.py makes."""
    off = []
    for target, text in project_writer.example_files().items():
        path = project_writer.EXAMPLE / target
        if path.exists() and path.read_text() == text:
            continue
        if fix:
            path.write_text(text)
        else:
            off.append(target)
    return [f"examples/hello/{target}: not what editor/skeleton/ makes: check_format.py --fix" for target in off]


def shop_problems():
    """Every offer of the data names a shop of catalog/shops.json or none, and a seller only on a marketplace or classifieds."""
    known = json.loads((ROOT / "catalog" / "shops.json").read_text())["shops"]
    found = []
    for root in ("catalog", "imported", "imported-shops"):
        for path in sorted((ROOT / root).glob("*/*/*.json")):
            doc = json.loads(path.read_text())
            for key, offer in ((doc.get("price") or {}) if isinstance(doc, dict) else {}).items():
                if "shop" in offer and offer["shop"] not in known:
                    found.append(f"{path.relative_to(ROOT)}: price {key}: the shop {offer['shop']} is not in catalog/shops.json")
                elif "seller" in offer and known.get(offer.get("shop"), {}).get("kind", "store") == "store":
                    found.append(f"{path.relative_to(ROOT)}: price {key}: a seller, and the shop {offer.get('shop')} sells its own stock")
    return found


def reports_refused():
    """take_report.py takes a price from an issue and nothing else: the text of an issue comes from anyone."""
    wrong = 0
    with tempfile.TemporaryDirectory() as folder:
        catalog = pathlib.Path(folder)
        shutil.copytree(ROOT / "catalog" / "modules" / "pn532_module", catalog / "modules" / "pn532_module")
        shutil.copy(ROOT / "catalog" / "shops.json", catalog / "shops.json")
        body = ("### Item\n\n{item}\n\n### Shop\n\n{shop}\n\n### Seller\n\n{seller}\n\n### Currency\n\n{currency}\n\n### Price of one\n\n{price}\n\n"
                "### Pack of\n\n{qty}\n")
        fine = {"item": "modules/pn532_module", "shop": "https://de.aliexpress.com/item/1.html", "currency": "USD", "price": "3-5", "qty": "_No response_",
                "seller": "_No response_"}
        take_report.take(body.format(**fine), 7, catalog, "2026-11-01")
        offer = json.loads((catalog / "modules" / "pn532_module" / "module.json").read_text())["price"]["report_7"]
        if offer != {"shop": "aliexpress", "currency": "USD", "range": [3.0, 5.0], "date": "2026-11-01", "source": "Issue 7, as reported"}:
            print(f"take_report.py wrote {offer}")
            wrong += 1
        take_report.take(body.format(**{**fine, "price": "3,76", "shop": "aliexpress"}), 9, catalog, "2026-11-01")
        offer = json.loads((catalog / "modules" / "pn532_module" / "module.json").read_text())["price"]["report_9"]
        if offer["range"] != [3.76, 3.76] or offer["shop"] != "aliexpress":
            print(f"take_report.py took 3,76 of aliexpress as {offer['range']} of {offer['shop']}")
            wrong += 1
        # an issue edited is taken again: its offer is replaced where it stands, not written twice
        take_report.take(body.format(**{**fine, "price": "4,10", "shop": "aliexpress"}), 9, catalog, "2026-11-02")
        text = (catalog / "modules" / "pn532_module" / "module.json").read_text()
        if text.count('"report_9"') != 1 or json.loads(text)["price"]["report_9"]["range"] != [4.1, 4.1]:
            print(f"take_report.py took issue 9 again as {text.count(chr(34) + 'report_9' + chr(34))} offers")
            wrong += 1
        # prices as they are written in one country or another
        for text, currency, value in (("1.234,56", "EUR", [1234.56] * 2), ("1,234.56", "USD", [1234.56] * 2), ("1 234,56", "EUR", [1234.56] * 2),
                                      ("1'234.56", "CHF", [1234.56] * 2), ("1,20,000", "INR", [120000.0] * 2), ("0,082", "EUR", [0.082] * 2),
                                      ("3,5 – 4,2", "EUR", [3.5, 4.2]), ("3,76 €", "EUR", [3.76] * 2), ("$5", "USD", [5.0] * 2)):
            if take_report.price_of(text, currency) != value:
                print(f"take_report.py read {text} as {take_report.price_of(text, currency)}")
                wrong += 1
        for field, value in (("item", "../../etc/passwd"), ("item", "modules/pn5180_module"), ("item", "modules/x; rm -rf /"), ("currency", "dollars"),
                             ("price", "free"), ("price", "5-3"), ("price", "1,200"), ("price", "1.200"), ("price", "€3"), ("price", "1.234.5"),
                             ("price", "1-2-3"), ("qty", "many"), ("shop", "x" * 201), ("shop", "amazon"), ("shop", "amazn"), ("shop", "<b>"),
                             ("shop", "Чип и Дип"), ("seller", "<a href=x>"), ("seller", "x" * 61)):
            try:
                take_report.take(body.format(**{**fine, field: value}), 8, catalog, "2026-11-01")
                print(f"take_report.py took {field}: {value}")
                wrong += 1
            except ValueError:
                pass
        # a shop by its address, its name or a name close to one; a shop the list lacks is added with no title
        known = json.loads((catalog / "shops.json").read_text())["shops"]
        for text, name in (("Amazon.de", "amazon_de"), ("https://www.amazon.de/dp/B0C", "amazon_de"), ("ebay.co.uk", "ebay"), ("Ali Express", "aliexpress"),
                           ("aliexpres", "aliexpress"), ("LCSC", "lcsc")):
            if resolve.shop_of(text, known) != (name, None):
                print(f"take_report.py found {resolve.shop_of(text, known)} for {text}")
                wrong += 1
        take_report.take(body.format(**{**fine, "seller": "Tenstar Robot", "qty": "5"}), 11, catalog, "2026-11-01")
        offer = json.loads((catalog / "modules" / "pn532_module" / "module.json").read_text())["price"]["report_11"]
        if (offer.get("seller"), offer.get("qty")) != ("Tenstar Robot", 5):
            print(f"take_report.py took the seller and the pack as {offer.get('seller')}, {offer.get('qty')}")
            wrong += 1
        try:
            take_report.take(body.format(**{**fine, "shop": "LCSC", "seller": "Somebody"}), 12, catalog, "2026-11-01")
            print("take_report.py took a seller of LCSC, which sells its own stock")
            wrong += 1
        except ValueError:
            pass
        said, new_shop = take_report.take(body.format(**{**fine, "shop": "amzn.eu"}), 10, catalog, "2026-11-01")
        added = json.loads((catalog / "shops.json").read_text())["shops"].get("amzn_eu")
        if not new_shop or added != {"domains": ["amzn.eu"]}:
            print(f"take_report.py added the shop amzn.eu as {added}")
            wrong += 1
    print(f"reports: {'0' if not wrong else wrong} wrong")
    return wrong


def bridge_problems():
    """tools/boards_mcp.py over its real stdio and HTTP: it answers MCP, it gives out only the page, and it writes a project only
    where it was started, when the person allows it, and never over what a person changed."""
    folder = tempfile.TemporaryDirectory()
    project, config = pathlib.Path(folder.name) / "garland", pathlib.Path(folder.name) / "config"
    project.mkdir()
    # what VS Code makes in a folder it opens: the folder is still empty of a program
    (project / ".vscode").mkdir()
    process = subprocess.Popen([sys.executable, str(ROOT / "tools" / "boards_mcp.py"), "--project", str(project)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, env={**os.environ, "XDG_CONFIG_HOME": str(config)})

    def asked(ident, method, params=None):
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())["result"]

    def status(path, **headers):
        try:
            return urllib.request.urlopen(urllib.request.Request(f"{base}{path}", headers=headers), timeout=5).status
        except urllib.error.HTTPError as error:
            return error.code

    problems = []
    try:
        if asked(1, "initialize")["serverInfo"]["name"] != "boards" or not asked(2, "tools/list")["tools"]:
            problems.append("no tools")
        # a row that is no request, or a call the tools do not take, is answered with an error, and the server goes on
        for row, code in (("this is not json", -32700), ("[1, 2, 3]", -32600), ('{"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "nosuch"}}', -32602),
                          ('{"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "say", "arguments": {"text": 5}}}', -32602)):
            process.stdin.write(row + "\n")
            process.stdin.flush()
            answer = process.stdout.readline()
            if not answer:
                return problems + [f"the server of MCP stopped on {row}"]
            if json.loads(answer).get("error", {}).get("code") != code:
                problems.append(f"the server of MCP on {row}: not the error {code}")
        link = json.loads(asked(3, "tools/call", {"name": "page_link"})["content"][0]["text"])["link"]
        base = link.split("/editor/")[0]
        for path, headers, wanted in (("/editor/index.html", {}, 200), ("/agent/messages?seen=0", {}, 401), ("/editor/index.html", {"Host": "evil.example"}, 403), ("/CLAUDE.md", {}, 404),
                                      ("/.git/config", {}, 404), ("/editor/../CLAUDE.md", {}, 404), ("/editor/%2e%2e/CLAUDE.md", {}, 404), ("/tools/boards_mcp.py", {}, 404),
                                      ("/examples/hello/main/main.c", {}, 200), ("/examples/hello/CMakeLists.txt", {}, 404),
                                      ("/imported-shops/index.json", {}, 200)):
            if status(path, **headers) != wanted:
                problems.append(f"the server of the page: {path} {headers}: not {wanted}")
        # a body of the wrong form is refused, and the tools still answer after it
        token = link.split("agent=")[1]
        own = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Origin": base}
        for path, body in (("/agent/state", b"[1, 2]"), ("/agent/state", b'{"blocks": 7}'), ("/agent/state", b'{"blocks": [3]}'), ("/agent/say", b'{"text": 5}'), ("/agent/state", b"{not json")):
            request = urllib.request.Request(f"{base}{path}", data=body, method="POST", headers=own)
            try:
                code = urllib.request.urlopen(request, timeout=5).status
            except urllib.error.HTTPError as error:
                code = error.code
            if code != 400:
                problems.append(f"the server of the page takes {body!r} on {path}: {code}")
        if status("/agent/messages?seen=x", Authorization=f"Bearer {token}") != 400:
            problems.append("the server of the page: a count that is not one is not refused")
        for ident, name in ((4, "page_state"), (5, "edit_blocks")):
            answer = asked(ident, "tools/call", {"name": name, "arguments": {"why": "a check", "remove": ["x"]}})
            if answer.get("isError") and name == "page_state":
                problems.append(f"{name} fails after a refused body")
        problems += project_problems(base, own, project, config)
    finally:
        process.stdin.close()
        process.wait(timeout=5)
        folder.cleanup()
    return problems


def serve_problems():
    """boards_mcp.py --serve, with no agent: it prints the link of the page, which says no model talks, and knows its project."""
    problems = []
    with tempfile.TemporaryDirectory() as folder:
        process = subprocess.Popen([sys.executable, str(ROOT / "tools" / "boards_mcp.py"), "--serve", "--project", folder], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, env={**os.environ, "XDG_CONFIG_HOME": folder})
        try:
            link = process.stdout.readline().strip()
            base, token = link.split("/editor/")[0], re.search(r"agent=([^&]+)", link)[1]
            if not link.endswith("&model=none"):
                problems.append(f"--serve: the link does not say that no model talks: {link}")
            with urllib.request.urlopen(urllib.request.Request(f"{base}/agent/project", headers={"Authorization": f"Bearer {token}"}), timeout=5) as answer:
                if json.loads(answer.read())["mode"] != "create":
                    problems.append("--serve: the empty folder is no project to create")
        except (OSError, TypeError, KeyError, ValueError) as error:
            problems.append(f"--serve: {error!r}")
        finally:
            process.terminate()
            process.wait(timeout=5)
    return problems


def project_problems(base, own, project, config):
    """The writes of a project through the bridge, over its HTTP."""
    def post(path, body, headers=own):
        request = urllib.request.Request(f"{base}{path}", data=json.dumps(body).encode(), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as error:
            return error.code, None
        except (urllib.error.URLError, ConnectionError, http.client.HTTPException):
            return None, None  # the server dropped the connection with no answer

    def got(path):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{base}{path}", headers=own), timeout=5) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as error:
            return error.code, None

    problems = []
    files = {"CMakeLists.txt": "project(garland)\n", "selection.json": json.dumps({"boards": [{"board": "jc4827w543c"}, {"board": "cyd_s028r"}], "current": "cyd_s028r"}),
             "sdkconfig.defaults.jc4827w543c": "# board_select.py jc4827w543c\n", "sdkconfig.defaults.cyd_s028r": "# board_select.py cyd_s028r\n",
             "sdkconfig.defaults.esp32p4": "CONFIG_PARTITION_TABLE_CUSTOM=y\n"}
    if got("/agent/project")[1] != {"path": str(project.resolve()), "name": "garland", "mode": "create", "for_ever": False}:
        problems.append(f"the project of the bridge: {got('/agent/project')}")
    if post("/agent/project/plan", {"files": files}, {**own, "Origin": "http://evil.example"})[0] != 401:
        problems.append("a plan from another site is not refused")
    code, plan = post("/agent/project/plan", {"files": files})
    if code != 200 or "CMakePresets.json" not in plan["made"] or any((project / name).exists() for name in files):
        problems.append(f"a plan: {code}, it wrote something or made no presets")
    if post("/agent/project/write", {"files": files})[0] != 403 or (project / "CMakeLists.txt").exists():
        problems.append("a write the person did not allow is not refused")
    code, done = post("/agent/project/write", {"files": files, "allow": "once"})
    if code != 200 or "CMakePresets.json" not in done["written"] or "CONFIG_IDF_TARGET" not in (project / "sdkconfig.defaults.cyd_s028r").read_text():
        problems.append(f"a write allowed once: {code} {done}")
    # the lock the program had is where the lock of each board starts
    (project / "dependencies.lock").write_text("dependencies:\n  idf:\n    version: 6.1.0\n")
    # a file the server writes is readable as any the person makes
    umask = os.umask(0)
    os.umask(umask)
    mode = stat.S_IMODE((project / "CMakeLists.txt").stat().st_mode) if (project / "CMakeLists.txt").exists() else None
    if mode != 0o666 & ~umask:
        problems.append(f"a new file has the mode {oct(mode) if mode is not None else 'of none'}")
    # a file a person changed is replaced only when ticked, and nothing of a refused write lands
    edited = project / "sdkconfig.defaults.cyd_s028r"
    edited.write_text(edited.read_text() + "CONFIG_MINE=y\n")
    code, done = post("/agent/project/write", {"files": {**files, "main/main.c": "void app_main(void) {}\n"}, "allow": "once"})
    if code != 200 or "sdkconfig.defaults.cyd_s028r" not in done["refused"] or (project / "main" / "main.c").exists() or "CONFIG_MINE" not in edited.read_text():
        problems.append(f"a change of a person is not kept: {done}")
    # a tick replaces what the plan showed: changed again since, the file is refused
    shown = post("/agent/project/plan", {"files": files})[1]["made"]["sdkconfig.defaults.cyd_s028r"]["digest"]
    edited.write_text(edited.read_text() + "CONFIG_MINE_AGAIN=y\n")
    code, done = post("/agent/project/write", {"files": files, "replace": {"sdkconfig.defaults.cyd_s028r": shown}, "allow": "once"})
    if code != 200 or "sdkconfig.defaults.cyd_s028r" not in done["refused"] or "CONFIG_MINE_AGAIN" not in edited.read_text():
        problems.append(f"a tick replaced a file changed after the plan: {done}")
    shown = post("/agent/project/plan", {"files": files})[1]["made"]["sdkconfig.defaults.cyd_s028r"]["digest"]
    code, done = post("/agent/project/write", {"files": files, "replace": {"sdkconfig.defaults.cyd_s028r": shown}, "allow": "once"})
    if code != 200 or "CONFIG_MINE" in edited.read_text():
        problems.append(f"a change ticked to replace is not replaced: {done}")
    # a plan puts nothing outside the project, not even through the copy it runs --again on, which lies in the temp folder
    outside = [pathlib.Path(tempfile.gettempdir()) / f"boards-escape-{os.getpid()}.txt", config / "escape-absolute.txt", config / "escape-deep.txt"]
    tried = {f"../{outside[0].name}": "x", str(outside[1]): "x", "../" * 32 + str(outside[2]).lstrip("/"): "x"}
    code, plan = post("/agent/project/plan", {"files": {**files, **tried}})
    if code != 200 or any(path.exists() for path in outside) or any(plan["files"][rel]["state"] != "refused" for rel in tried):
        problems.append(f"a plan wrote outside the project: {code}, {[str(path) for path in outside if path.exists()]}")
    for path in outside:
        path.unlink(missing_ok=True)
    for path in (".git/hooks/pre-commit", "../outside.txt", "build/x.c", "dependencies.lock.cyd_s028r"):
        code, done = post("/agent/project/write", {"files": {path: "x"}, "allow": "once"})
        if code != 200 or path not in done["refused"] or done["written"]:
            problems.append(f"{path} is not refused: {code} {done}")
    if got("/agent/project/file?path=../outside.txt")[0] != 400 or got("/agent/project/file?path=selection.json")[0] != 200:
        problems.append("the files of a project are read by another rule than they are written")
    # for ever: kept for the user, by the path and the name of the project; then no allow is needed
    if post("/agent/project/write", {"files": files, "allow": "for ever"})[0] != 200 or post("/agent/project/write", {"files": files})[0] != 200:
        problems.append("a write allowed for ever asks again")
    if json.loads((config / "jef-sure-boards" / "allowed.json").read_text()) != {str(project.resolve()): "garland"}:
        problems.append("for ever is not kept by the path and the name of the project")
    # a file that cannot be written leaves the others unwritten, and the page gets an answer
    (project / "main").mkdir(exist_ok=True)
    os.chmod(project / "main", 0o555)
    try:
        code, done = post("/agent/project/write", {"files": {"NOTES.md": "x\n", "main/new.c": "x\n"}, "allow": "once"})
    finally:
        os.chmod(project / "main", 0o755)
    if os.geteuid() and (code != 500 or (project / "NOTES.md").exists() or any(path.name.startswith(".NOTES") for path in project.iterdir())):
        problems.append(f"a write that failed on its second file: {code}, the first is there: {(project / 'NOTES.md').exists()}")
    # what board_select.py makes again stays the page's: a command that changes the presets records them in the list
    subprocess.run([sys.executable, str(ROOT / "tools" / "board_select.py"), "--current", "jc4827w543c", str(project)], capture_output=True)
    listed = json.loads((project / ".boards" / "written.json").read_text()).get("CMakePresets.json")
    if listed != hashlib.sha256((project / "CMakePresets.json").read_text().encode()).hexdigest():
        problems.append("presets changed by board_select.py are a person's for the bridge")
    # a file of ESP-IDF for a target is no board: the locks are seeded for the two boards only
    if sorted(path.name for path in project.glob("dependencies.lock.*")) != ["dependencies.lock.cyd_s028r", "dependencies.lock.jc4827w543c"]:
        problems.append(f"locks seeded: {sorted(path.name for path in project.glob('dependencies.lock.*'))}")
    return problems


def roles_problems(doc):
    """The schema of roles.json, one name for one role, and words that compile."""
    problems = errors_of(ROLES, doc, "roles")
    roles = [role for group in doc["groups"] for role in group["roles"]]
    names = [role["id"] for role in roles]
    problems += [f"role {name} twice" for name in sorted({name for name in names if names.count(name) > 1})]
    for item in [*roles, *(variant for role in roles for variant in role.get("variants", []))]:
        try:
            re.compile(item.get("words", ""))
        except re.error as error:
            problems.append(f"{item['id']}: {error}")
    return problems


def library_list_problems():
    """The list of libraries leads: the index only points into it, and need not cover it."""
    folder = ROOT / "catalog" / "libraries"
    libraries = json.loads((folder / "libraries.json").read_text())["libraries"]
    index = json.loads((folder / "chip_libraries.json").read_text())["chips"]
    problems = [f"chip_libraries.json: {chip}: {library} is not in libraries.json" for chip, names in index.items() for library in names if library not in libraries]
    problems += [f"chip_libraries.json: {chip}: {library} does not name it" for chip, names in index.items() for library in names if library in libraries and chip not in libraries[library]["chips"]]
    problems += [f"libraries.json: {library} requires {needed}, which is not in it" for library, entry in libraries.items() for needed in entry.get("requires", []) if needed not in libraries]
    records = resolve.all_libraries((ROOT / "catalog",))
    problems += [f"libraries.json has no {library}, which has a record" for library in records if library not in libraries]
    problems += [f"libraries.json: {library} is {libraries[library].get('version')}, its record describes {record.get('described')}"
                 for library, record in records.items() if library in libraries and libraries[library].get("version") != record.get("described")]
    return problems + audit_problems()


def audit_problems():
    problems = [f"{path.relative_to(ROOT)}: {problem}" for path in sorted((ROOT / "catalog" / "libraries").glob("*/*/*/audit.json")) for problem in audit.problems_of(path, json.loads(path.read_text()))]
    path = ROOT / "catalog" / "libraries" / "esp-idf" / "jef-sure" / "pn532" / "audit.json"
    good = json.loads(path.read_text())
    entry = good["audits"][0]
    spoiled = {
        "an item left out": lambda doc: doc["audits"][0]["items"].pop("frames.ack_checked"),
        "an item the rubric lacks": lambda doc: doc["audits"][0]["items"].update({"frames.no_such": entry["items"]["frames.ack_checked"]}),
        "a rubric that does not exist": lambda doc: doc["audits"][0].update({"rubric": "no_such"}),
        "a version of the rubric to come": lambda doc: doc["audits"][0].update({"rubric_version": 99}),
        "one commit read twice": lambda doc: doc["audits"].append(doc["audits"][0]),
        "another name": lambda doc: doc.update({"name": "other"}),
    }
    for what, spoil in spoiled.items():
        doc = json.loads(path.read_text())
        spoil(doc)
        if not audit.problems_of(path, doc):
            problems.append(f"audit.py takes {what}")
    schema_spoiled = {
        "yes with no evidence": lambda doc: doc["audits"][0]["items"]["frames.ack_checked"].pop("evidence"),
        "no with nothing searched": lambda doc: doc["audits"][0]["items"]["cards.iso14443b"].pop("searched"),
        "a short commit": lambda doc: doc["audits"][0].update({"commit": "b5048d3"}),
        "a place with no line": lambda doc: doc["audits"][0]["defects"][0].update({"evidence": ["src/pn532.c"]}),
        "a defect with no place": lambda doc: doc["audits"][0]["defects"][0].update({"evidence": []}),
    }
    for what, spoil in schema_spoiled.items():
        doc = json.loads(path.read_text())
        spoil(doc)
        if not errors_of(RAW, doc, "schema"):
            problems.append(f"the schema takes {what}")
    return problems


def audit_changes_wrong():
    """audit.py against a real repository: the lines of the old commit a newer one changed, and the files it added."""
    with tempfile.TemporaryDirectory() as folder:
        def git(*args):
            subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "-C", folder, *args], check=True, capture_output=True)
        git("init", "--quiet")
        (pathlib.Path(folder) / "a.c").write_text("one\ntwo\nthree\nfour\n")
        git("add", ".")
        git("commit", "--quiet", "-m", "first")
        (pathlib.Path(folder) / "a.c").write_text("one\n2\nthree\nfour\n")
        (pathlib.Path(folder) / "b.c").write_text("new\n")
        git("add", ".")
        (pathlib.Path(folder) / "c.c").write_text("not tracked\n")
        worktree = audit.changed_lines(folder, "HEAD", None)
        git("commit", "--quiet", "-m", "second")
        between = audit.changed_lines(folder, "HEAD~1", "HEAD")
        (pathlib.Path(folder) / "a.c").write_text("zero\none\n2\nthree\nfour\n")
        shifted = audit.changed_lines(folder, "HEAD", None)[2]
    lines, in_file = audit.touched(["a.c:2", "a.c:4"], between[0])
    wrong = [] if between[:2] == ({"a.c": {2}}, ["b.c"]) and worktree[:2] == ({"a.c": {2}}, ["c.c", "b.c"]) and lines == ["a.c:2"] and in_file else [f"audit.py changes reads {between}, {worktree}, {lines}"]
    wrong += [] if audit.touched(["a.c:4"], between[0]) == ([], True) else ["audit.py changes takes an unchanged line for a changed one"]
    return wrong + ([] if audit.moved("a.c:4", shifted) == "a.c:5" and audit.moved("a.c:4", between[2]) == "a.c:4" else [f"audit.py moves lines wrongly: {shifted}"])


def imported_problems(doc):
    """What an import must keep to: where a board came from, how far it is trusted, and what is never taken from a pack."""
    problems = [] if "origin" in doc else ["no origin"]
    if {entry.get("level") for entry in doc.get("checked", {}).values()} != {"extracted"}:
        problems.append("its level is not extracted")
    if "shared_pins" in doc:
        problems.append("shared_pins is for a person to write")
    on_dsi = [name for name, device in doc["devices"].items() if "timing" in (device.get("config") or {}) and any(bus.startswith("dsi.") for bus in device.get("on") or {})]
    problems += [f"{name}: DSI timings are measured on a board" for name in on_dsi]
    return problems + [f"{name}: {address} is the 8-bit form of {address_of_chip}" for name, address, address_of_chip in shifted_addresses(doc)]


def shifted_addresses(doc):
    """The addresses of a board that are twice one its chip has: the packs give the 8-bit form, and the import must shift it."""
    for name, device in doc["devices"].items():
        on_chip = (resolve.load("devices", device["chip"]).get("on") or {}).get("i2c", {}) if "chip" in device else {}
        known = [on_chip["address"]] if "address" in on_chip else on_chip.get("address_try", [])
        for connection in (device.get("on") or {}).values():
            for address in known:
                if int(connection.get("address", "0"), 16) == 2 * int(address, 16):
                    yield name, connection["address"], address


def main():
    failed = 0
    reached = {}

    files = [path for root in (ROOT / "catalog", ROOT / "imported", ROOT / "imported-shops", TESTS / "catalog") for path in documents_under(root)]
    for path in files:
        doc = json.loads(path.read_text())
        problems = errors_of(RAW, doc, "schema")
        if doc["kind"] == "project" and ROOT / "catalog" in path.parents:
            problems.append(f"a project is somebody's own board: its place is {resolve.LOCAL_BOARDS} of the program")
        if not problems and doc["kind"] == "library" and path.parent.parts[-3:] != tuple(resolve.library_id(doc).split("/")):
            problems.append(f"it lies apart from its id {resolve.library_id(doc)}")
        # a board inherits what it covers, so its rules wait for the resolved board below
        if doc["kind"] not in ("board", "project"):
            problems += [f"rule {found['rule']}: {found['message']}" for found in rules.check(doc, FILE_RULES)]
        for problem in problems:
            print(f"{path.relative_to(ROOT)}: {problem}")
        failed += bool(problems)
    print(f"catalog: {len(files)} files")

    for path in sorted((ROOT / "catalog").glob("boards/*/board.json")) + sorted((ROOT / "catalog").glob("modules/*/module.json")):
        problems, resolved = stages(json.loads(path.read_text()))
        for problem in problems:
            print(f"{path.relative_to(ROOT)}: {problem}")
        if resolved:
            reached[f"data_{path.parent.name}.json"] = resolved
        failed += bool(problems)

    # a chip of the cases may share its name with a stub of imported/: the cases stay out of its way here
    resolve.ROOTS.remove(TESTS / "catalog")
    imported = [path for root in ("imported", "imported-shops") for pattern in ("boards/*/board.json", "modules/*/module.json") for path in sorted((ROOT / root).glob(pattern))]
    for path in imported:
        doc = json.loads(path.read_text())
        problems, resolved = stages(doc)
        problems += imported_problems(doc)
        for problem in problems:
            print(f"{path.relative_to(ROOT)}: {problem}")
        if resolved:
            reached[f"data_{path.parent.name}.json"] = resolved
        failed += bool(problems)
    resolve.ROOTS.insert(1, TESTS / "catalog")
    print(f"imported: {len(imported)} boards and modules")

    # what a revision of a chip sets
    for revision, expected in (("1.3", ["CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y", "CONFIG_ESP32P4_REV_MIN_100=y", "CONFIG_SPIRAM_SPEED_200M=y", "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_360=y"]),
                               ("3.2", ["CONFIG_ESP32P4_REV_MIN_301=y", "CONFIG_SPIRAM_SPEED_250M=y", "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_400=y"])):
        settings = resolve.chip_settings({"target": "esp32p4", "psram_mb": 32, "revision": revision})
        if settings != expected:
            print(f"the settings of revision {revision}: {settings}")
            failed += 1

    # the order of versions
    ordered = (("0.9.3", "0.10.2", "decimal"), ("2.0.0-beta9", "2.0.0-beta10", "decimal"), ("2.0.0-beta5", "2.0.0", "decimal"), ("1.5.9", "2.0.0-beta1", "decimal"),
               ("1.2.0", "1.2.0~1", "decimal"), ("1.2.0~3", "1.2.1", "decimal"), ("3.4", "3.A", "hex"), ("3.A", "3.10", "hex"), ("V1.07.2209", "V1.10.2209", "decimal"))
    for older, newer, scheme in ordered:
        if not resolve.version_key(older, scheme) < resolve.version_key(newer, scheme):
            print(f"versions: {older} is not older than {newer} in {scheme}")
            failed += 1
    if resolve.version_key("1.0") != resolve.version_key("1.0.0"):
        print("versions: 1.0 is not 1.0.0")
        failed += 1

    # history of a library: the case of test/format/catalog has a chip that came late and grew
    record = resolve.library("esp-idf/owner_a/idf_library")
    for version, expected in (("1.1.0", ["uid", "pages_read"]), ("1.0.0", ["uid"]), ("0.8.0", None)):
        chip = resolve.library_at(record, version)["chips"].get("two_libraries")
        if (chip["supports"]["ntag"] if chip else None) != expected:
            print(f"history of idf_library at {version}: not {expected}")
            failed += 1

    # history of a firmware: a control that the older ones do not have
    for version, expected in (("3.A", True), ("3.9", False), ("3.4", False)):
        if ("lpcd_reference" in resolve.apply_type({"chip": "pn5180", "firmware_version": version})["controls"]) != expected:
            print(f"history of the PN5180 firmware at {version}: lpcd_reference is not {expected}")
            failed += 1

    good = sorted((TESTS / "good").glob("*.json"))
    for path in good:
        problems, resolved = stages(json.loads(path.read_text()))
        for problem in problems:
            print(f"good/{path.name}: {problem}")
        if resolved:
            reached[f"good_{path.stem}.json"] = resolved
        failed += bool(problems)
    print(f"good: {len(good)}")

    bad = sorted((TESTS / "bad").glob("*.json"))
    for path in bad:
        case = json.loads(path.read_text())
        problems, resolved = stages(case["board"])
        if not any(case["expect"] in problem for problem in problems):
            print(f"bad/{path.name}: not refused as expected: {problems[0][:120] if problems else 'no problems'}")
            failed += 1
        if resolved:
            reached[f"bad_{path.stem}.json"] = resolved
    print(f"bad: {len(bad)}")

    # what a tool outside reads of a resolved board reaches it from every layer
    gt911 = {"chip": "gt911", "on": {}}
    for device, field, expected in ((gt911, "maker", "goodix"), (gt911, "compat", "goodix,gt911"), ({**gt911, "part": "GT911QM"}, "part", "GT911QM"),
                                    ({"chip": "scd4x", "variant": "scd41"}, "part", "SCD41"), ({"chip": "scd4x", "variant": "scd41"}, "compat", "sensirion,scd41")):
        if resolve.apply_type(device).get(field) != expected:
            print(f"{device['chip']}: {field} is not {expected}")
            failed += 1
    module = reached["good_physical_module_power.json"]
    if module["modules"]["reader"]["chain"][0].get("revision") != "V2" or [step.get("name") for step in module["power"]][-1] != "reader_3V3" or "reader_chip" not in module["power"][-1]["feeds"]:
        print("a module on a board lost its revision or the names of its power")
        failed += 1

    # a part of a module takes the figures of its chip and can replace them
    nfc = reached["good_nfc_module_measured.json"]["devices"]["reader_nfc"]
    figures = nfc["provides"]["nfc"]
    if figures.get("freq_mhz") != [13.56, 13.56] or figures.get("tx_mw_max") != 330 or figures.get("radiated_mw") != 20 or nfc["draw"]["rf_on"]["ma_peak"] != 150:
        print(f"a module lost a figure of its chip or its own: {figures}")
        failed += 1

    # a graphics display in a module reaches the generator through the project that wires it
    display = boards_gen.read_board(TESTS / "good" / "display_module_wired.json").get("display") or {}
    if display.get("driver") != "st77916":
        print(f"a display in a module did not reach the generator: {display}")
        failed += 1

    # the CMake of a program gets a primary group as board_display_init gives it: two 128x128 side by side
    dotview = boards_gen.read_board(TESTS / "good" / "dotview_clock.json")
    primary = boards_gen.primary_shown(dotview)
    if primary != (256, 128, 54, 27):
        print(f"the primary group of dotview_clock is {primary}, not 256x128 and 54x27 mm")
        failed += 1
    # and the glue of a board with a group still names the board, not its group
    if '.name = "dotview_clock"' not in boards_gen.gen_c({**dotview, "description": "a case"}):
        print("the glue of dotview_clock does not name the board in board_data")
        failed += 1

    # a GPIO of a power step or a divider is taken, and the glue refuses what it cannot set
    taken = {pin for pin, _, _ in boards_gen.pins_of(reached["good_physical_switched_rail.json"])} & {14}
    taken |= {pin for pin, _, _ in boards_gen.pins_of(reached["good_physical_divider_switch.json"])} & {15}
    if taken != {14, 15}:
        print(f"pins_of: only {sorted(taken)} of 14 and 15 are seen as taken")
        failed += 1
    try:
        boards_gen.read_board(TESTS / "good" / "physical_switched_rail.json")
        print("the generator took a line of power it cannot set")
        failed += 1
    except ValueError as error:
        if "cannot set the lines of power" not in str(error):
            print(f"the generator refused for another reason: {error}")
            failed += 1

    with tempfile.TemporaryDirectory() as out:
        for name, doc in reached.items():
            (pathlib.Path(out) / name).write_text(json.dumps(doc))
        run = subprocess.run(["node", str(TESTS / "rules_cli.js"), out], capture_output=True, text=True)
    if run.returncode:
        print(run.stderr[:800])
        failed += 1
    else:
        found = json.loads(run.stdout)
        key = lambda item: (item["rule"], item["message"])
        differ = [name for name, doc in reached.items() if sorted(rules.check(doc, RULES), key=key) != sorted(found[name], key=key)]
        print(f"rules.py and rules.js: {len(reached)} boards, {sum(map(len, found.values()))} findings, {len(differ)} differ {differ[:5]}")
        failed += bool(differ)

    documents_read, refused, differ = loaders_differ(ordered)
    print(f"resolve.py and resolve.js: {documents_read} documents, {refused} refused, {len(differ)} differ {differ[:5]}")
    failed += bool(differ)

    documents_read, refused, differ = editor_differs(reached)
    print(f"Python and the editor: {documents_read} documents, {refused} refused by the schema, {len(differ)} differ {differ[:5]}")
    failed += bool(differ)

    problems = errors_of(QUESTIONS, json.loads((ROOT / "catalog" / "questions.json").read_text()), "questions")
    problems += errors_of(RATES, json.loads((ROOT / "catalog" / "rates.json").read_text()), "rates")
    problems += errors_of(SHOPS, json.loads((ROOT / "catalog" / "shops.json").read_text()), "shops")
    problems += shop_problems()
    problems += errors_of(JUDGEMENTS, json.loads((ROOT / "catalog" / "judgements.json").read_text()), "judgements")
    problems += roles_problems(json.loads((ROOT / "catalog" / "roles.json").read_text()))
    problems += snippets_differ()
    problems += example_wrong("--fix" in sys.argv)
    problems += canonical_wrong("--fix" in sys.argv)
    problems += bridge_problems()
    problems += serve_problems()
    problems += library_list_problems()
    problems += audit_changes_wrong()
    failed += reports_refused()
    failed += goods_wrong()
    failed += presets_wrong()
    failed += taken_back_wrong()
    failed += package_wrong()
    run = subprocess.run(["node", str(TESTS / "page_cli.js")], capture_output=True, text=True)
    print(run.stdout.strip() + run.stderr.strip()[-300:])
    failed += run.returncode != 0
    run = subprocess.run(["node", str(TESTS / "lang_cli.js")], capture_output=True, text=True)
    print(run.stdout.strip())
    failed += run.returncode != 0
    run = subprocess.run(["node", str(TESTS / "solver_cli.js")], capture_output=True, text=True)
    if run.returncode:
        problems.append(run.stderr[:800])
    else:
        found = json.loads(run.stdout)
        problems += found["wrong"]
        with tempfile.TemporaryDirectory() as out:
            for at, project in enumerate(found["projects"]):
                path = pathlib.Path(out) / "boards" / f"kit{at}" / "board.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({**project, "name": f"kit{at}"}))
                try:
                    board = boards_gen.read_board(path)
                except ValueError as error:
                    problems.append(f"the generator refuses a kit over {project['extends']}: {error}")
                    continue
                unused = {part for part, device in (project.get("devices") or {}).items() if device.get("used") is False}
                # a button a kit wires is a button of its glue, which board_button_count() sees and pulls up
                pressed = {part for part, device in (project.get("devices") or {}).items() if device.get("class") == "button"}
                if pressed - {button["name"] for button in board["buttons"]}:
                    problems.append(f"the glue of a kit over {project['extends']} has no button for {', '.join(sorted(pressed - {button['name'] for button in board['buttons']}))}")
                if unused & {part["name"] for part in (*(board.get("displays") or ()), *board["touches"], *board["sounds"])}:
                    problems.append(f"the glue of a kit over {project['extends']} starts what the kit leaves alone")
        print(f"the solver: {found['cases']} cases, {len(found['projects'])} kits, {len(problems)} wrong")
    for problem in problems:
        print(problem)
    failed += bool(problems)

    # the page loads the catalog by its index: a file the index misses is not in the page, so the index is checked here too
    index = ROOT / "catalog" / boards_gen.CATALOG_INDEX
    if index.read_text() != boards_gen.gen_catalog_index(ROOT):
        print(f"{index.relative_to(ROOT)} is not what the data says (run tools/boards_gen.py --all)")
        failed += 1
    else:
        print("the index of the catalog: as the data says")

    for name, path in (("data_jc4827w543c.json", "devices.sound"), ("data_cyd_s028r.json", "devices.touch"), ("good_cyd_s028r_v3.json", "devices.touch"), ("good_imported_like.json", "devices.lcd")):
        print(f"{name[:-5]} {path}: {resolve.trust(reached[name], path, LEVELS)}")

    print("FAILED" if failed else "all pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
