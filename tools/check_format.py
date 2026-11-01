#!/usr/bin/env python3
"""
Checks of the data format. Needs jsonschema and node: the Python of ESP-IDF has the first.

    python3 tools/check_format.py

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
   passes the schema.
"""
import copy
import json
import pathlib
import random
import subprocess
import sys
import tempfile

import jsonschema

import boards_gen
import resolve
import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "test" / "format"
SCHEMA = json.loads((ROOT / "catalog" / "format.schema.json").read_text())
jsonschema.Draft202012Validator.check_schema(SCHEMA)
RAW = jsonschema.Draft202012Validator(SCHEMA)
RESOLVED = jsonschema.Draft202012Validator({"$ref": "#/$defs/resolved", "$defs": SCHEMA["$defs"]})
QUESTIONS = jsonschema.Draft202012Validator({"$ref": "#/$defs/questions", "$defs": SCHEMA["$defs"]})
RATES = jsonschema.Draft202012Validator({"$ref": "#/$defs/rates", "$defs": SCHEMA["$defs"]})
RULES = json.loads((ROOT / "catalog" / "rules.json").read_text())
FILE_RULES = {**RULES, "rules": [rule for rule in RULES["rules"] if rule.get("in_files")]}
LEVELS = SCHEMA["$defs"]["level"]["enum"]
resolve.ROOTS.append(TESTS / "catalog")


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


def editor_differs(reached):
    """Gives jsonschema, dump and pins_of of Python and their JS the same input. Returns the counts and where the two part."""
    rng = random.Random(1)
    files = {str(path.relative_to(ROOT)): json.loads(path.read_text()) for root in (ROOT / "catalog", TESTS / "catalog") for path in sorted(root.rglob("*.json")) if path.parent != root}
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


def main():
    failed = 0
    reached = {}

    files = [path for root in (ROOT / "catalog", TESTS / "catalog") for path in sorted(root.rglob("*.json")) if path.parent != root]
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
    if module["modules"]["reader"].get("revision") != "V2" or [step.get("name") for step in module["power"]][-1] != "reader_3V3" or "reader_chip" not in module["power"][-1]["feeds"]:
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
                    boards_gen.read_board(path)
                except ValueError as error:
                    problems.append(f"the generator refuses a kit over {project['extends']}: {error}")
        print(f"the solver: {found['cases']} cases, {len(found['projects'])} kits, {len(problems)} wrong")
    for problem in problems:
        print(problem)
    failed += bool(problems)

    for name, path in (("data_jc4827w543c.json", "devices.sound"), ("data_cyd_s028r.json", "devices.touch"), ("good_cyd_s028r_v3.json", "devices.touch"), ("good_imported_like.json", "devices.lcd")):
        print(f"{name[:-5]} {path}: {resolve.trust(reached[name], path, LEVELS)}")

    print("FAILED" if failed else "all pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
