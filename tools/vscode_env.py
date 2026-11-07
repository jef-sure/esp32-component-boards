#!/usr/bin/env python3
"""
The settings of VS Code a project of boards needs, in its .vscode/settings.json:

- cmake.environment with IDF_PATH, IDF_PYTHON_ENV_PATH, IDF_TOOLS_PATH and PATH as the shell of ESP-IDF has them.
  CMake Tools takes the presets board_select.py writes and runs cmake in the environment of VS Code, which has no
  ESP-IDF; with these four it configures and builds as idf.py does. project_include.cmake writes them at each
  configuration: vscode_env.py PROJECT_DIR.
- the current board for the ESP-IDF extension: idf.customExtraVars.IDF_TARGET, idf.sdkconfigFilePath,
  build/<board>/sdkconfig, and idf.buildPath, build/<board>, where its build goes with no project configuration chosen. The extension gives its terminals the IDF_TARGET of that sdkconfig, of that setting when the
  board was not built yet, and of the sdkconfig of the project's folder, or esp32, when neither is set; idf.py stops when
  it differs from the target of the board a preset builds. board_select.py writes them when the current board changes:
  vscode_env.py PROJECT_DIR --current BOARD TARGET. The extension keeps the target it took and reads it again later, as
  after a reload of the window and the preset of the board chosen: till then its terminals keep the old IDF_TARGET.

Only a project VS Code is used on gets them: one with .vscode/, or worked on from VS Code. Values already there are not
written again. A settings.json that is not plain JSON, as one with comments, is left as it is, and the lines it needs
are printed.

Usage: vscode_env.py PROJECT_DIR [--current BOARD TARGET]
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


def update(project, change, said):
    """Applies change, a function of the settings that returns them changed or None for nothing to do, to the settings of
    the project, under the rules above; said names what was written."""
    folder = pathlib.Path(project) / ".vscode"
    if not (folder.is_dir() or from_vscode()):
        return
    path = folder / "settings.json"
    try:
        settings = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        settings = None
    if not isinstance(settings, dict):
        print(f"{path}: not plain JSON, left as it is. It needs:\n{json.dumps(change({}) or {}, indent=4)}")
        return
    changed = change(dict(settings))
    if changed is None:
        return
    folder.mkdir(exist_ok=True)
    made = path.with_name(path.name + ".new")
    made.write_text(json.dumps(changed, indent=4) + "\n")
    os.replace(made, path)
    print(f"{path}: {said}")


def environment(project):
    """cmake.environment from the shell of ESP-IDF, kept while IDF_PATH is the same, so a configuration whose PATH is in
    another order changes nothing."""
    wanted = {key: os.environ[key] for key in KEYS if os.environ.get(key)}
    if "IDF_PATH" not in wanted:
        return

    def change(settings):
        have = settings.get(SETTING) if isinstance(settings.get(SETTING), dict) else {}
        if have.get("IDF_PATH") == wanted["IDF_PATH"] and all(key in have for key in wanted):
            return None
        return {**settings, SETTING: {**have, **wanted}}

    update(project, change, f"{SETTING} for CMake Tools, from ESP-IDF {wanted['IDF_PATH']}")


def current(project, board, target):
    """The target of the current board and its sdkconfig, for the ESP-IDF extension and the terminals it opens."""
    build = (pathlib.Path(project) / "build" / board).resolve()
    sdkconfig = str(build / "sdkconfig")

    def change(settings):
        extra = settings.get("idf.customExtraVars") if isinstance(settings.get("idf.customExtraVars"), dict) else {}
        if extra.get("IDF_TARGET") == target and settings.get("idf.sdkconfigFilePath") == sdkconfig and settings.get("idf.buildPath") == str(build):
            return None
        # the build of the extension with no project configuration chosen goes to the board's directory, which has its BOARD
        return {**settings, "idf.customExtraVars": {**extra, "IDF_TARGET": target}, "idf.sdkconfigFilePath": sdkconfig, "idf.buildPath": str(build)}

    update(project, change, f"the ESP-IDF extension takes {board}, {target} when it reads the target again; till then, unset IDF_TARGET in its terminal")


def main():
    args = sys.argv[1:]
    if len(args) == 1:
        environment(args[0])
    elif len(args) == 4 and args[1] == "--current":
        current(args[0], args[2], args[3])
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
