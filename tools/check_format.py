#!/usr/bin/env python3
"""
Checks of the data format. Needs jsonschema and node: the Python of ESP-IDF has the first.

    python3 tools/check_format.py

1. every file of catalog/ and of test/format/catalog/ passes the schema;
2. every board of the catalog passes the schema, the merge, the schema of the result and the rules;
3. every case of test/format/good/ passes all of them;
4. every case of test/format/bad/ fails with the message it expects;
5. rules.py and editor/rules.js find the same in every board that reaches the rules.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import jsonschema

import resolve
import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "test" / "format"
SCHEMA = json.loads((ROOT / "catalog" / "format.schema.json").read_text())
jsonschema.Draft202012Validator.check_schema(SCHEMA)
RAW = jsonschema.Draft202012Validator(SCHEMA)
RESOLVED = jsonschema.Draft202012Validator({"$ref": "#/$defs/resolved", "$defs": SCHEMA["$defs"]})
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


def main():
    failed = 0
    reached = {}

    files = [path for root in (ROOT / "catalog", TESTS / "catalog") for path in sorted(root.rglob("*.json")) if path.parent != root]
    for path in files:
        doc = json.loads(path.read_text())
        problems = errors_of(RAW, doc, "schema")
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

    for name, path in (("data_jc4827w543c.json", "devices.sound"), ("data_cyd_s028r.json", "devices.touch"), ("good_cyd_s028r_v3.json", "devices.touch"), ("good_imported_like.json", "devices.lcd")):
        print(f"{name[:-5]} {path}: {resolve.trust(reached[name], path, LEVELS)}")

    print("FAILED" if failed else "all pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
