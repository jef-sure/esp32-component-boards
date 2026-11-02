#!/usr/bin/env python3
"""
Keeps what audits found in a library beside its record, in audit.json: one entry for each commit that was read, so that a
newer version shows what it changed in what was read.

take reads the result of a reading, checks that every quote stands in the copy that was read, and adds an entry. The quotes
stay out of the catalog: a file, a line and the commit say the same, and the code of others stays out of this repository.
changes compares the last entry with a newer commit of a clone and lists what has to be read again. Nothing from the clone
runs.

carry makes the entry of a newer commit from the last one: entries on lines that did not change stay, with their lines moved,
and a reading of what changed replaces the others. It refuses when something the changes touched was not read again.

Usage:
  audit.py take LIBRARY RESULT --src DIR --rubric NAME --rubric-version N --commit SHA --by WHO [--version V] [--tag T] [--blind] [--date YYYY-MM-DD]
  audit.py changes LIBRARY --clone DIR [--to REF]   with no --to: against the working tree
  audit.py carry LIBRARY RESULT --src DIR --clone DIR --to REF --commit SHA --by WHO [--version V] [--tag T] [--blind] [--date YYYY-MM-DD]
LIBRARY is ecosystem/owner/name, as the record lies under catalog/libraries/.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

import resolve

ROOT = resolve.ROOT
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def rubric_of(name):
    return json.loads((ROOT / "catalog" / "rubrics" / name / "rubric.json").read_text())


def items_of(rubric, version):
    """The items of a rubric at one of its versions: an item stays once it is added."""
    return [f"{section}.{name}" for section, items in rubric["sections"].items() for name, item in items.items() if item.get("since", 1) <= version]


def problems_of(path, doc):
    """What the schema cannot see: the folder, the rubric each entry names, and one entry for a commit and rubric."""
    library = path.parent
    problems = [] if (library / "library.json").exists() else ["no library.json beside it"]
    if doc["name"] != library.name:
        problems.append(f"its name is not {library.name}")
    seen = set()
    for entry in doc["audits"]:
        where = entry["commit"][:12]
        key = (entry["commit"], entry["rubric"], entry["rubric_version"])
        if key in seen:
            problems.append(f"{where}: read twice against one rubric")
        seen.add(key)
        rubric_path = ROOT / "catalog" / "rubrics" / entry["rubric"] / "rubric.json"
        if not rubric_path.exists():
            problems.append(f"{where}: no rubric {entry['rubric']}")
            continue
        rubric = json.loads(rubric_path.read_text())
        if entry["rubric_version"] > rubric["version"]:
            problems.append(f"{where}: {entry['rubric']} has no version {entry['rubric_version']}")
        wanted = set(items_of(rubric, entry["rubric_version"]))
        problems += [f"{where}: {item} is missing" for item in sorted(wanted - set(entry["items"]))]
        problems += [f"{where}: {item} is not in the rubric" for item in sorted(set(entry["items"]) - wanted)]
    return problems


def quote_problems(src, where, evidence):
    problems = []
    for place in evidence:
        path = (src / str(place.get("file", ""))).resolve()
        rows = path.read_bytes().decode("utf-8", "replace").splitlines() if path.is_relative_to(src.resolve()) and path.is_file() else []
        line = place.get("line")
        quote = " ".join(str(place.get("quote", "")).split())
        if not isinstance(line, int) or not 1 <= line <= len(rows) or not quote or quote not in " ".join(rows[line - 1].split()):
            problems.append(f"{where}: {place.get('file')}:{line} does not hold {quote!r}")
    return problems


def places(evidence):
    return [f"{place['file']}:{place['line']}" for place in evidence]


def entry_of(result, args):
    """An entry from the result of a reading, or the list of quotes that do not stand in the copy."""
    src = args.src
    problems, items, defects = [], {}, []
    for name, item in result["items"].items():
        problems += quote_problems(src, name, item.get("evidence") or [])
        kept = {key: item[key] for key in ("status", "searched", "note") if item.get(key)}
        items[name] = {**kept, **({"evidence": places(item["evidence"])} if item.get("evidence") else {})}
    for defect in result["defects"]:
        problems += quote_problems(src, defect["what"][:40], defect["evidence"])
        defects.append({**{key: defect[key] for key in ("what", "severity", "read_as", "judged", "measured") if key in defect}, "evidence": places(defect["evidence"])})
    optional = {"version": args.version, "tag": args.tag, "blind": args.blind or None}
    entry = {**{key: value for key, value in optional.items() if value}, "commit": args.commit, "rubric": args.rubric, "rubric_version": args.rubric_version, "date": args.date, "by": args.by, "items": items, "defects": defects}
    return entry, problems


def take(args):
    folder = ROOT / "catalog" / "libraries" / args.library
    record = json.loads((folder / "library.json").read_text())
    entry, problems = entry_of(json.loads(args.result.read_text()), args)
    target = folder / "audit.json"
    doc = json.loads(target.read_text()) if target.exists() else {"format": record["format"], "format_version": record["format_version"], "kind": "audit", "name": record["name"], "title": record["title"], "audits": []}
    doc["audits"].append(entry)
    problems += problems_of(target, doc)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    target.write_text(resolve.dump(doc) + "\n")
    print(f"{args.library}: {len(entry['items'])} items, {len(entry['defects'])} defects at {args.commit[:12]}")
    return 0


def changed_lines(clone, old, new):
    """file -> the lines of the old commit that the new one changed, the files it added, and file -> (old line, shift of the lines after it)."""
    # no external diff, no hooks and no write to its index: the clone is data, or the work of someone else
    command = ["git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null", "-C", str(clone), "diff", "--no-ext-diff", "--no-renames", "--no-color", "--unified=0", old]
    text = subprocess.run(command + ([new] if new else []), capture_output=True, text=True, errors="replace", check=True).stdout
    if not new:  # a diff against the working tree leaves out what git does not track yet
        untracked = subprocess.run(["git", "--no-optional-locks", "-C", str(clone), "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, check=True).stdout.split("\n")
    changed, added, current = {}, [] if new else [name for name in untracked if name], None
    shifts = {}
    rows = text.splitlines()
    for at, row in enumerate(rows):
        if row.startswith("--- "):
            current = None if row == "--- /dev/null" else row[len("--- a/"):]
            if current:
                changed.setdefault(current, set())
                shifts.setdefault(current, [])
            elif rows[at + 1].startswith("+++ b/"):
                added.append(rows[at + 1][len("+++ b/"):])
        elif current and (hunk := HUNK.match(row)):
            first, count = int(hunk[1]), 1 if hunk[2] is None else int(hunk[2])
            changed[current].update(range(first, first + max(count, 1)))
            shifts[current].append((first + count - 1 if count else first, (1 if hunk[3] is None else int(hunk[3])) - count))
    return changed, added, shifts


def touched(evidence, changed):
    """The places that changed, and whether the file of any place changed elsewhere."""
    lines = [place for place in evidence if int(place.rsplit(":", 1)[1]) in changed.get(place.rsplit(":", 1)[0], ())]
    return lines, any(place.rsplit(":", 1)[0] in changed for place in evidence)


def changes(args):
    doc = json.loads((ROOT / "catalog" / "libraries" / args.library / "audit.json").read_text())
    last = doc["audits"][-1]
    changed, added, _ = changed_lines(args.clone, last["commit"], args.to)
    read_again, same_file, unmoved = [], [], 0
    subjects = [(name, item.get("evidence", [])) for name, item in last["items"].items()] + [(f"defect, {defect['severity']}: {defect['what']}", defect["evidence"]) for defect in last["defects"]]
    for subject, evidence in subjects:
        lines, in_file = touched(evidence, changed)
        if lines:
            read_again.append(f"{subject}: {', '.join(lines)}")
        elif in_file:
            same_file.append(subject)
        elif evidence:
            unmoved += 1
    print(f"{args.library}: {last['commit'][:12]} ({last.get('version', 'no version')}) to {args.to or 'the working tree'}, {len(changed)} files changed, {len(added)} added")
    for title, rows in (("read again, its lines changed:", read_again), ("its file changed, not its lines:", same_file), ("new files, read them:", added)):
        if rows:
            print(title)
            print("\n".join(f"  {row}" for row in rows))
    absent = [name for name, item in last["items"].items() if item["status"] == "no"]
    if changed or added:
        print(f"a no has no line to compare, so new code can change any of them: {', '.join(absent)}")
    print(f"{unmoved} entries stand on lines that did not change")
    return 0


def moved(place, shifts):
    """A place of the old commit in the new one: the lines changed above it move it."""
    file, line = place.rsplit(":", 1)
    return f"{file}:{int(line) + sum(shift for after, shift in shifts.get(file, ()) if after < int(line))}"


def carried(subject, shifts):
    return {**subject, "evidence": [moved(place, shifts) for place in subject["evidence"]]} if "evidence" in subject else subject


def carry(args):
    path = ROOT / "catalog" / "libraries" / args.library / "audit.json"
    doc = json.loads(path.read_text())
    last = doc["audits"][-1]
    changed, _, shifts = changed_lines(args.clone, last["commit"], args.to)
    result = json.loads(args.result.read_text())
    read, problems = entry_of(result, args)
    gone = set(result.get("gone", ()))
    items = {name: read["items"].get(name) or carried(item, shifts) for name, item in last["items"].items()}
    problems += [f"{name} stands on changed lines and was not read again" for name, item in last["items"].items() if touched(item.get("evidence", []), changed)[0] and name not in read["items"]]
    kept = [defect for defect in last["defects"] if defect["what"] not in gone and defect["what"] not in result.get("restated", ())]
    problems += [f"defect on changed lines, not read again: {defect['what'][:80]}" for defect in kept if touched(defect["evidence"], changed)[0]]
    entry = {**read, "over": last["commit"], "rubric": last["rubric"], "rubric_version": last["rubric_version"], "items": items, "defects": [carried(defect, shifts) for defect in kept] + read["defects"]}
    doc["audits"].append(entry)
    problems += problems_of(path, doc)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    path.write_text(resolve.dump(doc) + "\n")
    print(f"{args.library}: {len(read['items'])} items read again, {len(kept)} defects carried, {len(read['defects'])} read, {len(gone)} gone, at {args.commit[:12]}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("take", help="add the result of a reading to the catalog")
    add.add_argument("library")
    add.add_argument("result", type=pathlib.Path)
    add.add_argument("--src", type=pathlib.Path, required=True, help="the copy that was read")
    add.add_argument("--rubric", required=True)
    add.add_argument("--rubric-version", type=int, required=True)
    add.add_argument("--commit", required=True)
    add.add_argument("--by", required=True)
    add.add_argument("--version")
    add.add_argument("--tag")
    add.add_argument("--blind", action="store_true", help="the copy was read with the names of its owners removed")
    add.add_argument("--date", default=datetime.date.today().isoformat())
    compare = commands.add_parser("changes", help="what a newer commit changed in what was read")
    compare.add_argument("library")
    compare.add_argument("--clone", type=pathlib.Path, required=True)
    compare.add_argument("--to", help="a commit or a tag; none: the working tree of the clone")
    forward = commands.add_parser("carry", help="the entry of a newer commit from the last one and a reading of what changed")
    forward.add_argument("library")
    forward.add_argument("result", type=pathlib.Path)
    forward.add_argument("--src", type=pathlib.Path, required=True, help="the copy that was read")
    forward.add_argument("--clone", type=pathlib.Path, required=True)
    forward.add_argument("--to", required=True)
    forward.add_argument("--commit", required=True)
    forward.add_argument("--by", required=True)
    forward.add_argument("--version")
    forward.add_argument("--tag")
    forward.add_argument("--blind", action="store_true")
    forward.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()
    if args.command == "carry":
        args.rubric, args.rubric_version = None, None
    return {"take": take, "changes": changes, "carry": carry}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
