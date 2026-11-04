#!/usr/bin/env python3
"""
Writes the files of a project for the bridge of boards_mcp.py: into the one directory the bridge was started for, and
never over a file a person wrote or changed.

What it wrote is kept with the hash of each file in .boards/written.json of the project, a local list as build/ is: a
file not in it, or in it with another hash, is a person's and is replaced only when the person ticks it. After a clone
the list is empty, so every file is a person's and the first write asks. The files board_select.py --again makes are
found on a copy of the project first and go through the same rule. A write is all or nothing; each file and the list
go to disk by a rename, the list last.

Whether the bridge may write at all is the person's, asked by the page every time or kept for ever: that record is the
user's, in $XDG_CONFIG_HOME/jef-sure-boards/allowed.json by the path and the name of the project, so a project cannot
give itself the right and another project at the same path is asked again.
"""
import contextlib
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
WRITTEN = ".boards/written.json"
ALLOWED = "allowed.json"
# what the build and the component manager make, and the folder of git, whose hooks are code: never written here
MADE_BY_OTHERS = re.compile(r"^(build.*|managed_components)$")
LOCK = re.compile(r"^dependencies\.lock.*$")
EMPTY = re.compile(r"^(\.git|\.gitignore|\.gitattributes|README.*|LICENSE.*)$", re.I)  # a folder of only these is empty, as store.js says
# what board_select.py --again reads of a project
AGAIN_READS = ("CMakeLists.txt", "selection.json", "CMakePresets.json", "dependencies.lock")


def problem_of(root, rel):
    """Why the path rel may not be written in the project root, or None."""
    if not isinstance(rel, str) or not rel or "\\" in rel or "\0" in rel or rel.startswith("/"):
        return "not a path inside the project"
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "not a plain path"
    if any(part.startswith(".") and part != ".gitignore" for part in parts):
        return "a hidden path, as .git: not written by the page"
    if MADE_BY_OTHERS.match(parts[0]) or LOCK.match(parts[-1]):
        return "made by the build or by the component manager"
    here = root
    for part in parts[:-1]:
        here = here / part
        if here.is_symlink() or (here.exists() and not here.is_dir()):
            return "a link or a file on its way"
    target = root / rel
    if target.is_symlink() or (target.exists() and not target.is_file()):
        return "not a file"
    return None


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def put(path, text):
    """A file written whole or not at all: beside it first, then renamed over it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
        file.write(text)
    os.replace(file.name, path)


def config_dir():
    return pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config") / "jef-sure-boards"


class Project:
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()

    def name(self):
        """The name of the project, as project() of its CMakeLists.txt says it, else of its directory."""
        cmake = self.root / "CMakeLists.txt"
        found = re.search(r"^\s*project\(\s*([^\s)]+)", cmake.read_text(), re.M) if cmake.is_file() else None
        return found[1] if found else self.root.name

    def mode(self):
        """create for a folder with nothing of a program yet, update for a program, None for anything else."""
        if self.root == ROOT or ROOT in self.root.parents:
            return None  # the component itself is no project of the page
        if (self.root / "CMakeLists.txt").is_file():
            return "update"
        return "create" if all(EMPTY.match(item.name) for item in self.root.iterdir()) else None

    def written(self):
        path = self.root / WRITTEN
        return json.loads(path.read_text()) if path.is_file() else {}

    def allowed_for_ever(self):
        path = config_dir() / ALLOWED
        return path.is_file() and json.loads(path.read_text()).get(str(self.root)) == self.name()

    def allow_for_ever(self):
        path = config_dir() / ALLOWED
        allowed = json.loads(path.read_text()) if path.is_file() else {}
        allowed[str(self.root)] = self.name()
        put(path, json.dumps(allowed, indent=2, sort_keys=True) + "\n")

    def states(self, files):
        """For each file: refused with why, new, same, ours (unchanged since written here) or changed (a person's)."""
        written = self.written()
        found = {}
        for rel, text in files.items():
            problem = problem_of(self.root, rel) or (None if isinstance(text, str) else "not a text")
            if problem:
                found[rel] = {"state": "refused", "why": problem}
                continue
            path = self.root / rel
            old = path.read_text(errors="replace") if path.exists() else None
            found[rel] = {"state": "new" if old is None else "same" if old == text else "ours" if written.get(rel) == digest(old) else "changed"}
        return found

    def made_again(self, files):
        """The files board_select.py --again makes when files are written: run on a copy of the project, so nothing of
        the project changes before the person has seen what would."""
        with tempfile.TemporaryDirectory() as folder:
            copy = pathlib.Path(folder)
            for name in AGAIN_READS:
                if (self.root / name).is_file():
                    shutil.copyfile(self.root / name, copy / name)
            for path in self.root.glob("sdkconfig.defaults.*"):
                shutil.copyfile(path, copy / path.name)
            if (self.root / "components" / "local-boards").is_dir():
                shutil.copytree(self.root / "components" / "local-boards", copy / "components" / "local-boards", symlinks=True)
            for rel, text in files.items():
                (copy / rel).parent.mkdir(parents=True, exist_ok=True)
                (copy / rel).write_text(text)
            before = {path: path.read_text(errors="replace") for path in copy.rglob("*") if path.is_file()}
            if not any(path.read_text(errors="replace").startswith("# board_select.py ") for path in copy.glob("sdkconfig.defaults.*")):
                return {}, None
            run = subprocess.run([sys.executable, str(ROOT / "tools" / "board_select.py"), "--again", str(copy)], capture_output=True, text=True)
            if run.returncode:
                return {}, (run.stdout + run.stderr).strip()[-600:]
            made = {}
            for path in copy.rglob("*"):
                rel = path.relative_to(copy).as_posix()
                if path.is_file() and not LOCK.match(path.name) and before.get(path) != path.read_text(errors="replace"):
                    made[rel] = path.read_text()
            return made, None

    def plan(self, files):
        """What a write of files would do: their states and those of what --again makes after them."""
        made, failed = self.made_again(files)
        return {"files": self.states(files), "made": self.states(made), **({"failed": failed} if failed else {})}

    def write(self, files, replace=()):
        """Writes files and what --again makes after them, all or nothing: refused when one is refused or is a person's
        and not in replace. Returns the paths written and those refused."""
        made, failed = self.made_again(files)
        if failed:
            return {"written": [], "refused": {}, "failed": failed}
        every = {**files, **made}
        states = self.states(every)
        refused = {rel: state for rel, state in states.items() if state["state"] == "refused" or (state["state"] == "changed" and rel not in replace)}
        if refused:
            return {"written": [], "refused": refused}
        written = self.written()
        done = []
        for rel, text in every.items():
            if states[rel]["state"] != "same":
                put(self.root / rel, text)
                done.append(rel)
            written[rel] = digest(text)
        put(self.root / WRITTEN, json.dumps(written, indent=2, sort_keys=True) + "\n")
        # each board's lock starts as the project's, once: a file of the component manager, neither hashed nor replaced here
        boards = [path.name.split(".", 2)[2] for path in self.root.glob("sdkconfig.defaults.*") if path.name != "sdkconfig.defaults.board"]
        if len(boards) > 1:
            sys.path.insert(0, str(ROOT / "tools"))
            import board_select

            # stdout of the bridge is the channel of MCP: what the tool says goes to stderr
            with contextlib.redirect_stdout(sys.stderr):
                board_select.seed_locks(self.root, boards)
        return {"written": sorted(done), "refused": {}}
