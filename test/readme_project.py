#!/usr/bin/env python3
"""A project of idf.py create-project changed as README.md says, for the CI: the lines of CMake of the README in its
CMakeLists.txt, the component from git at a commit in main/idf_component.yml, the sample of C of the README in app_main.

Usage: readme_project.py PROJECT_DIR COMMIT
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INCLUDE = "include($ENV{IDF_PATH}/tools/cmake/project.cmake)\n"


def main():
    project, commit = pathlib.Path(sys.argv[1]), sys.argv[2]
    readme = (ROOT / "README.md").read_text()
    cmake = re.search(r"```cmake\n(.*?)```", readme, flags=re.S)[1]
    sample = re.search(r"```c\n(.*?)```", readme, flags=re.S)[1].splitlines()
    url = re.search(r"`git: (\S+)`", readme)[1]
    lists = project / "CMakeLists.txt"
    text = lists.read_text()
    if text.count(INCLUDE) != 1:
        raise SystemExit(f"{lists}: not one line {INCLUDE.strip()} to put the lines of the README in")
    lists.write_text(text.replace(INCLUDE, cmake))
    (project / "main" / "idf_component.yml").write_text(f"dependencies:\n  jef-sure/boards:\n    git: {url}\n    version: {commit}\n")
    includes = [line for line in sample if line.startswith("#include")]
    body = "\n".join(f"    {line}" if line.strip() else "" for line in sample if not line.startswith("#include")).strip("\n")
    source = next((project / "main").glob("*.c"))
    source.write_text("\n".join([*includes, "", "void app_main(void)", "{", body, "}", ""]))
    print(f"{project}: the CMake lines, the dependency at {commit} and the sample of C of README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
