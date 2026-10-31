#!/usr/bin/env python3
"""
Fills "versions" of the libraries of the esp-idf ecosystem: from the component registry what each
version is built against and requires, from the tags of git the versions the registry has not.
Run by hand when a library has a new release. A version the registry does not have stays as the
catalog has it.
"""
import json
import re
import subprocess
import urllib.request

import resolve

REGISTRY = "https://components.espressif.com/api/components/{owner}/{name}"
REGISTRY_TIMEOUT_S = 30


def version_of(entry):
    """A version of the registry in the form of the catalog."""
    out = {"targets": entry.get("targets"), "requires": {}}
    for dep in entry.get("dependencies") or []:
        if dep["source"] == "idf":
            out["frameworks"] = {"esp-idf": dep["spec"]}
        elif dep["source"] == "service":
            conditions = [rule["if"] for rule in (dep.get("rules") or []) + (dep.get("matches") or [])]
            name = f"esp-idf/{dep['namespace']}/{dep['name']}"
            out["requires"][name] = {"version": dep["spec"], "if": conditions} if conditions else dep["spec"]
    return {key: value for key, value in out.items() if value}


def registry_versions(record):
    """The versions of the registry in the form of the catalog, and the license of the version described."""
    with urllib.request.urlopen(REGISTRY.format(**record), timeout=REGISTRY_TIMEOUT_S) as reply:
        entries = json.load(reply)["versions"]
    described = next((entry for entry in entries if entry["version"] == record.get("described")), {})
    return {entry["version"]: version_of(entry) for entry in entries}, (described.get("license") or {}).get("name")


def tagged_versions(way):
    """The versions the tags of a repository give, when its ref says how a tag is made of a version."""
    if "{version}" not in way.get("ref", ""):
        return []
    before, after = way["ref"].split("{version}")
    tags = subprocess.run(["git", "ls-remote", "--tags", way["url"]], capture_output=True, text=True, timeout=REGISTRY_TIMEOUT_S, check=True).stdout
    tags = [line.rsplit("/", 1)[1] for line in tags.splitlines() if not line.endswith("^{}")]
    return [tag[len(before):len(tag) - len(after)] for tag in tags if re.fullmatch(re.escape(before) + r"\d.*" + re.escape(after), tag)]


def main():
    for path in sorted((resolve.ROOT / "catalog" / "libraries" / "esp-idf").glob("*/*/library.json")):
        record = json.loads(path.read_text())
        ways = {way["via"]: way for way in record["install"]}
        if "registry" not in ways:
            continue
        versions, license_name = registry_versions(record)
        if license_name:
            record["license"] = license_name
        for version, entry in (record.get("versions") or {}).items():
            versions.setdefault(version, entry)
        for version in tagged_versions(ways.get("git", {})):
            versions.setdefault(version, {"via": ["git"]})
        record["versions"] = dict(sorted(versions.items(), key=lambda item: resolve.version_key(item[0]), reverse=True))
        path.write_text(resolve.dump(record) + "\n")
        newest = next(iter(record["versions"]))
        stale = "" if resolve.version_key(newest) <= resolve.version_key(record["described"]) else f", newer than the {record['described']} it describes: read it"
        print(f"{resolve.library_id(record)}: {len(record['versions'])} versions, newest {newest}{stale}")


if __name__ == "__main__":
    main()
