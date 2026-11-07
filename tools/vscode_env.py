#!/usr/bin/env python3
"""
The environment of ESP-IDF for CMake Tools of VS Code: cmake.environment in .vscode/settings.json of a project, with
IDF_PATH, IDF_PYTHON_ENV_PATH, IDF_TOOLS_PATH and PATH as the shell of ESP-IDF has them. CMake Tools takes the presets
board_select.py writes and runs cmake in the environment of VS Code, which has no ESP-IDF; with these four it
configures and builds as idf.py does.

Usage: vscode_env.py PROJECT_DIR

project_include.cmake runs it at each configuration. It writes only for a project VS Code is used on: one with .vscode/,
or configured from VS Code. The values stay while IDF_PATH is the same, so a configuration whose PATH is in another
order changes nothing. A settings.json that is not plain JSON, as one with comments, is left as it is, and the lines it
needs are printed.
"""
import json
import os
import pathlib
import sys

KEYS = ("IDF_PATH", "IDF_PYTHON_ENV_PATH", "IDF_TOOLS_PATH", "PATH")
SETTING = "cmake.environment"


def from_vscode():
    # TERM_PROGRAM in a terminal of VS Code, VSCODE_PID in what its extensions start
    return os.environ.get("TERM_PROGRAM") == "vscode" or bool(os.environ.get("VSCODE_PID"))


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    folder = pathlib.Path(sys.argv[1]) / ".vscode"
    wanted = {key: os.environ[key] for key in KEYS if os.environ.get(key)}
    if "IDF_PATH" not in wanted or not (folder.is_dir() or from_vscode()):
        return 0
    path = folder / "settings.json"
    try:
        settings = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        settings = None
    if not isinstance(settings, dict):
        print(f"{path}: not plain JSON, left as it is. CMake Tools needs in it:\n{json.dumps({SETTING: wanted}, indent=4)}")
        return 0
    have = settings.get(SETTING) if isinstance(settings.get(SETTING), dict) else {}
    if have.get("IDF_PATH") == wanted["IDF_PATH"] and all(key in have for key in wanted):
        return 0
    settings[SETTING] = {**have, **wanted}
    folder.mkdir(exist_ok=True)
    made = path.with_name(path.name + ".new")
    made.write_text(json.dumps(settings, indent=4) + "\n")
    os.replace(made, path)
    print(f"{path}: {SETTING} for CMake Tools, from ESP-IDF {wanted['IDF_PATH']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
