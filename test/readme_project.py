#!/usr/bin/env python3
"""A project of idf.py create-project changed as docs/en/quick-start.md says, for the CI: its lines of CMake in place of
the include of project.cmake, its program as main/hello.c, and the component from git at the commit under test (the
quick start takes it from the registry, which holds only what was published).

Usage: readme_project.py PROJECT_DIR COMMIT
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "en" / "quick-start.md"
REPOSITORY = "https://github.com/jef-sure/esp32-component-boards.git"
INCLUDE = "include($ENV{IDF_PATH}/tools/cmake/project.cmake)\n"


def main():
    project, commit = pathlib.Path(sys.argv[1]), sys.argv[2]
    guide = GUIDE.read_text()
    cmake = re.search(r"```cmake\n(.*?)```", guide, flags=re.S)[1]
    program = re.search(r"```c\n(.*?)```", guide, flags=re.S)[1]
    lists = project / "CMakeLists.txt"
    text = lists.read_text()
    if text.count(INCLUDE) != 1:
        raise SystemExit(f"{lists}: not one line {INCLUDE.strip()} to put the lines of the quick start in")
    lists.write_text(text.replace(INCLUDE, cmake))
    (project / "main" / "idf_component.yml").write_text(f"dependencies:\n  jef-sure/boards:\n    git: {REPOSITORY}\n    version: {commit}\n")
    for source in (project / "main").glob("*.c"):
        source.unlink()
    (project / "main" / "hello.c").write_text(program)
    print(f"{project}: the CMake lines and the program of the quick start, the component at {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
