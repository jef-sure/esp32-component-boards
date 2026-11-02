#!/usr/bin/env python3
"""
Lists the known libraries in catalog/libraries/libraries.json, the leading list, beside the records and the audits. Each has
the same facts, the chips it names and the libraries it requires. A library with no chip is a library too: it may do an
algorithm and drive nothing, and what a listed library requires is listed.
Nothing here ranks them: popularity is shown and comes last, and only an audit of the code says more.
chip_libraries.json is an index from a chip to libraries of that list, and need not cover them all.

Arduino comes from library_index.json of Arduino, ESP-IDF from the catalog, from the dependencies of the board packs and
from a search of GitHub for components: the registry of Espressif closes its API to robots. The facts come from GitHub.
Nobody read these libraries: a name is all that ties most of them to a chip.

Needs gh, logged in. Usage: import_libraries.py INDEX_JSON_GZ [--date YYYY-MM-DD]
"""
import argparse
import base64
import collections
import datetime
import gzip
import json
import pathlib
import re
import subprocess
import sys
import time

import resolve

ROOT = resolve.ROOT
ORDER = "Listed by name, and nothing here ranks them: stars and dates are shown and decide nothing. Only an audit of the code against an open rubric does."
SHORTEST_CHIP = 5  # a shorter name matches too much
MOST_TO_ASK = 12  # of one chip, before the facts are known
SEARCH_PAUSE_S = 2.5  # the search of GitHub takes 30 a minute
FOUND_BY_SEARCH = 8
REPOSITORIES_A_QUERY = 80
OURS = ("esp32", "*")
COMMIT_SHOWN = 12
ARDUINO = "arduino_esp32"
ESP_IDF = "esp_idf"
BUILDS_ON = {"builds_on.arduino": ARDUINO, "builds_on.esp_idf": ESP_IDF}  # what a reading found, for a library with no versions on record
BUILT = ("yes", "partly")
GITHUB = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False).stdout


def plain(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def chips_of():
    found = {}
    for root in ("catalog", "imported"):
        for path in (ROOT / root / "devices").glob("*/device.json"):
            found.setdefault(path.parent.name, root)
    return {name: root for name, root in sorted(found.items()) if len(name.replace("_", "")) >= SHORTEST_CHIP and re.search(r"\d", name)}


def word(text):
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-")


def add(found, library, chip, **fields):
    """A library once, under its own id, however many chips name it."""
    entry = found.setdefault(library, {**fields, "chips": []})
    if chip not in entry["chips"]:
        entry["chips"].append(chip)


def arduino_id(library):
    owner = (repository_of(library) or "unknown/").split("/")[0]
    return f"arduino/{word(owner)}/{word(library['name'])}"


def arduino_entry(library, chips):
    return {"title": library["name"], "version": library["version"], "repository": library.get("repository", ""), "platforms": [ARDUINO], "chips": chips}


def arduino_requires(index, found):
    """What the listed libraries name in their manifests, and what those name: each joins the list, a chip or not."""
    last = {library["name"]: library for library in index["libraries"]}
    waiting = [name for name, library in last.items() if arduino_id(library) in found]
    while waiting:
        library = last[waiting.pop()]
        needed = [last[item["name"]] for item in library.get("dependencies") or [] if item["name"] in last]
        # a record of the catalog can say more than the manifest: a library can include another and not name it
        entry = found[arduino_id(library)]
        entry["requires"] = sorted({*entry.get("requires", ()), *(arduino_id(item) for item in needed)})
        for item in needed:
            if arduino_id(item) not in found:
                found[arduino_id(item)] = arduino_entry(item, [])
                waiting.append(item["name"])


def arduino_candidates(index, chips, found):
    last, releases = {}, collections.Counter()
    for library in index["libraries"]:
        releases[library["name"]] += 1
        last[library["name"]] = library
    usable = [library for library in last.values() if set(library.get("architectures", ())) & set(OURS) and "Retired" not in library.get("types", ())]
    for chip in chips:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(chip.replace('_', ' '))}\w*")
        named = [library for library in usable if pattern.search(plain(library["name"]))]
        named.sort(key=lambda library: -releases[library["name"]])
        for library in named[:MOST_TO_ASK]:
            found.setdefault(arduino_id(library), arduino_entry(library, []))
            add(found, arduino_id(library), chip)


def is_component(repository):
    """A component of ESP-IDF, by its own files and not by what its page says."""
    if gh("api", f"repos/{repository}/contents/idf_component.yml", "--jq", ".name").strip() == "idf_component.yml":
        return True
    text = gh("api", f"repos/{repository}/contents/CMakeLists.txt", "--jq", ".content")
    try:
        return "idf_component_register" in base64.b64decode(text).decode(errors="ignore")
    except ValueError:
        return False


def catalog_libraries(found):
    """Every record of the catalog, with the chips it has and those of the rubrics it was read against."""
    for path in sorted((ROOT / "catalog" / "libraries").glob("*/*/*/library.json")):
        record = json.loads(path.read_text())
        audits = path.with_name("audit.json")
        read = json.loads(audits.read_text())["audits"] if audits.exists() else []
        chips = {*record.get("chips", {}), *(chip for name in {entry["rubric"] for entry in read} for chip in json.loads((ROOT / "catalog" / "rubrics" / name / "rubric.json").read_text()).get("chips", []))}
        built = {name for entry in record.get("versions", {}).values() for name in entry.get("platforms", {})}
        built |= {platform for item, platform in BUILDS_ON.items() for entry in read[-1:] if entry["items"].get(item, {}).get("status") in BUILT}
        fields = {"title": record.get("title", record["name"]), "version": record.get("described", ""), "repository": record.get("url", ""), "platforms": sorted(built)}
        newest = record.get("versions", {}).get(record.get("described")) or next(iter(record.get("versions", {}).values()), {})
        needed = sorted(newest.get("requires", {}))
        found.setdefault(resolve.library_id(record), {**fields, "chips": [], "requires": needed, **({"audited": [entry.get("version", entry["commit"][:COMMIT_SHOWN]) for entry in read]} if read else {})})
        for library in needed:
            found.setdefault(library, {"title": library, "repository": "", "platforms": sorted(built), "chips": []})
        for chip in sorted(chips):
            add(found, resolve.library_id(record), chip)


def idf_candidates(chips, found):
    for name, chip_names in json.loads((ROOT / "imported" / "report.json").read_text())["libraries"].items():
        owner, _, rest = name.partition("/")
        for chip in chip_names:
            add(found, f"esp-idf/{word(owner)}/{word(rest or owner)}", chip, title=name, repository="", platforms=[ESP_IDF])
    for chip, root in chips.items():
        if root != "catalog":
            continue  # the search takes a minute for a few: the chips we describe by hand
        time.sleep(SEARCH_PAUSE_S)
        names = gh("api", "-X", "GET", "search/repositories", "-f", f"q={chip.replace('_', ' ')} esp-idf in:name,description,readme fork:false", "-f", f"per_page={FOUND_BY_SEARCH}", "--jq", ".items[].full_name").split()
        known = {item["repository"].lower().removesuffix(".git"): library for library, item in found.items() if item["repository"]}
        for repository in names:
            url = f"https://github.com/{repository}"
            if url.lower() in known:
                add(found, known[url.lower()], chip)
            elif is_component(repository):
                add(found, f"github/{word(repository.split('/')[0])}/{word(repository.split('/')[1])}", chip, title=repository, repository=url, platforms=[ESP_IDF])


def repository_of(candidate):
    match = GITHUB.search(candidate.get("repository", ""))
    return f"{match[1]}/{match[2]}" if match else None


def facts_of(repositories):
    """The same facts about every repository, from one query of many."""
    facts = {}
    names = sorted(repositories)
    for at in range(0, len(names), REPOSITORIES_A_QUERY):
        part = names[at:at + REPOSITORIES_A_QUERY]
        fields = "stargazerCount pushedAt isArchived licenseInfo { spdxId }"
        query = "query {" + " ".join(f'r{i}: repository(owner: "{name.split("/")[0]}", name: "{name.split("/")[1]}") {{ {fields} }}' for i, name in enumerate(part)) + "}"
        answer = json.loads(gh("api", "graphql", "-f", f"query={query}") or "{}").get("data") or {}
        for i, name in enumerate(part):
            item = answer.get(f"r{i}")
            if item:
                facts[name] = {"stars": item["stargazerCount"], "changed": item["pushedAt"][:10], "archived": item["isArchived"], "license": (item["licenseInfo"] or {}).get("spdxId") or ""}
    return facts


def chips_index(libraries):
    """From a chip to its libraries: an index of the list, nothing of its own."""
    found = collections.defaultdict(list)
    for library, entry in sorted(libraries.items()):
        for chip in entry["chips"]:
            found[chip].append(library)
    return dict(sorted(found.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("index", type=pathlib.Path)
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()
    chips = chips_of()
    found = {}
    catalog_libraries(found)
    index = json.load(gzip.open(args.index))
    arduino_candidates(index, chips, found)
    arduino_requires(index, found)
    idf_candidates(chips, found)
    facts = facts_of({repository_of(entry) for entry in found.values()} - {None})
    libraries = {library: {key: value for key, value in {**entry, "chips": sorted(entry["chips"]), **facts.get(repository_of(entry), {})}.items() if value != "" and (value or key != "requires")} for library, entry in sorted(found.items())}
    out = ROOT / "catalog" / "libraries"
    (out / "libraries.json").write_text(resolve.dump({"date": args.date, "order": ORDER, "libraries": libraries}) + "\n")
    (out / "chip_libraries.json").write_text(resolve.dump({"date": args.date, "chips": chips_index(libraries)}) + "\n")
    print(f"{len(libraries)} libraries, {sum(1 for entry in libraries.values() if entry['chips'])} with chips, {len(chips_index(libraries))} chips, {len(facts)} with facts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
