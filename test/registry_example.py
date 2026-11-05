#!/usr/bin/env python3
"""The example the registry hands out, examples/hello, taken as it lies in the archive compote packs, for the CI: the
component from git at the commit under test, since the registry holds only what was published.

Usage: registry_example.py DIST_DIR PROJECT_DIR COMMIT
"""

import pathlib
import re
import sys
import tarfile

REPOSITORY = "https://github.com/jef-sure/esp32-component-boards.git"
EXAMPLE = "examples/hello/"


def main():
    dist, project, commit = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
    archives = sorted(dist.glob("*.tgz"))
    if len(archives) != 1:
        raise SystemExit(f"{dist}: not one archive of compote there: {[path.name for path in archives]}")
    with tarfile.open(archives[0]) as packed:
        members = [member for member in packed.getmembers() if member.isfile() and member.name.removeprefix("./").startswith(EXAMPLE)]
        if not members:
            raise SystemExit(f"{archives[0]}: no {EXAMPLE} in it")
        for member in members:
            target = project / member.name.removeprefix("./")[len(EXAMPLE):]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(packed.extractfile(member).read())
    manifest = project / "main" / "idf_component.yml"
    text = manifest.read_text()
    taken = re.sub(r"^  jef-sure/boards: .*$", f"  jef-sure/boards:\n    git: {REPOSITORY}\n    version: {commit}", text, flags=re.M)
    if taken == text:
        raise SystemExit(f"{manifest}: no line of jef-sure/boards to take it from git")
    manifest.write_text(taken)
    print(f"{project}: {EXAMPLE} of {archives[0].name}, the component at {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
