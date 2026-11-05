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
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
WRITTEN = ".boards/written.json"
NEW_FILE_MODE = 0o666  # the umask of the person takes from it
ALLOWED = "allowed.json"
# what the build and the component manager make, and the folder of git, whose hooks are code: never written here
MADE_BY_OTHERS = re.compile(r"^(build.*|managed_components)$")
LOCK = re.compile(r"^dependencies\.lock.*$")
# a folder of only these is empty: hidden ones, as .git and the .vscode VS Code makes in any folder it opens, a README, a licence
EMPTY = re.compile(r"^(\..*|README.*|LICENSE.*)$", re.I)
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


def beside(path, text):
    """The text in a hidden file beside path, to be renamed over it. A new file is readable as any file the person makes
    (0666 under the umask), one that is replaced keeps its mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    near = path.parent / f".{path.name}.{secrets.token_hex(4)}"
    descriptor = os.open(near, os.O_WRONLY | os.O_CREAT | os.O_EXCL, NEW_FILE_MODE)
    try:
        with os.fdopen(descriptor, "w") as file:
            file.write(text)
        if path.exists():
            os.chmod(near, stat.S_IMODE(path.stat().st_mode))
    except OSError:
        near.unlink(missing_ok=True)
        raise
    return near


def put(path, text):
    """A file written whole or not at all: beside it first, then renamed over it."""
    os.replace(beside(path, text), path)


def keep_ours(root, paths):
    """Files the component made again, as board_select.py does, stay the page's when its list has them: their new digests
    go into the list. A file the list does not have stays a person's."""
    root = pathlib.Path(root).resolve()
    listed = root / WRITTEN
    if not listed.is_file():
        return
    written = json.loads(listed.read_text())
    kept = {rel: digest((root / rel).read_text()) for rel in (pathlib.Path(path).resolve().relative_to(root).as_posix() for path in paths) if rel in written}
    if kept:
        put(listed, json.dumps({**written, **kept}, indent=2, sort_keys=True) + "\n")


def component_source():
    """Where a project takes the component from, as this copy came: git at its commit for a checkout, or what the lock of
    the project says for one in its managed_components/, git at a commit or the registry at a version. A copy of neither
    names the registry at the version of its manifest, the form of a published component."""
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True) if shutil.which("git") and (ROOT / ".git").exists() else None
    if head and head.returncode == 0:
        return {"git": head.stdout.strip()}
    if ROOT.parent.name == "managed_components":
        for lock in sorted(ROOT.parent.parent.glob("dependencies.lock*")):
            # the entry of the component in the lock, up to the next one: a version and the type of its source
            entry = re.search(r"^  jef-sure/boards:\n((?:    .*\n|      .*\n)*)", lock.read_text(), re.M)
            version = re.search(r"^    version: '?([^'\s]+)'?$", entry[1], re.M) if entry else None
            if version:
                return {"git": version[1]} if re.search(r"^      type: git$", entry[1], re.M) else {"registry": version[1]}
    # quoted in the repository, bare in the manifest the registry ships
    manifest = re.search(r"""^version:\s*["']?([^"'\s#]+)""", (ROOT / "idf_component.yml").read_text(), re.M)
    return {"registry": manifest[1]} if manifest else None


def component_lines(source):
    """The entry of the component in main/idf_component.yml, as the page writes it (COMPONENT_LINES of store.js)."""
    if source and "registry" in source:
        return f'  jef-sure/boards: ">={source["registry"]}"'  # a caret on 0.0.x would take that version alone
    return f"  jef-sure/boards:\n    git: https://github.com/jef-sure/esp32-component-boards.git\n    version: {(source or {}).get('git', 'main')}"


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
        """For each file: refused with why, new, same, ours (unchanged since written here) or changed (a person's), with
        the digest of what lies there now: a tick to replace a person's file names it, so it replaces what was shown."""
        written = self.written()
        found = {}
        for rel, text in files.items():
            problem = problem_of(self.root, rel) or (None if isinstance(text, str) else "not a text")
            if problem:
                found[rel] = {"state": "refused", "why": problem}
                continue
            path = self.root / rel
            old = path.read_text(errors="replace") if path.exists() else None
            state = "new" if old is None else "same" if old == text else "ours" if written.get(rel) == digest(old) else "changed"
            found[rel] = {"state": state, **({"digest": digest(old)} if old is not None else {})}
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
            # only a path the project may get goes into the copy: ../x would land beside it, /x anywhere
            for rel, text in files.items():
                if problem_of(self.root, rel) or not isinstance(text, str) or not (copy / rel).resolve().is_relative_to(copy.resolve()):
                    continue
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

    def write(self, files, replace=None):
        """Writes files and what --again makes after them, all or nothing: refused when one is refused, or is a person's
        and replace does not name it with the digest of what lies there, as the plan showed it: a file changed again
        since is refused. Returns the paths written and those refused."""
        replace = replace or {}
        made, failed = self.made_again(files)
        if failed:
            return {"written": [], "refused": {}, "failed": failed}
        every = {**files, **made}
        states = self.states(every)
        refused = {rel: state for rel, state in states.items() if state["state"] == "refused" or (state["state"] == "changed" and replace.get(rel) != state["digest"])}
        if refused:
            return {"written": [], "refused": refused}
        written = self.written()
        done = [rel for rel in every if states[rel]["state"] != "same"]
        # every file beside its place first: when one cannot be written, no file of the project changes
        ready = []
        try:
            for rel in done:
                ready.append((beside(self.root / rel, every[rel]), self.root / rel))
        except OSError:
            for near, _ in ready:
                near.unlink(missing_ok=True)
            raise
        for near, path in ready:
            os.replace(near, path)
        written.update({rel: digest(text) for rel, text in every.items()})
        put(self.root / WRITTEN, json.dumps(written, indent=2, sort_keys=True) + "\n")
        # each board's lock starts as the project's, once: a file of the component manager, neither hashed nor replaced here
        sys.path.insert(0, str(ROOT / "tools"))
        import board_select

        boards = board_select.boards_of(self.root)
        if boards:
            # stdout of the bridge is the channel of MCP: what the tool says goes to stderr
            with contextlib.redirect_stdout(sys.stderr):
                board_select.seed_locks(self.root, boards)
        return {"written": sorted(done), "refused": {}}
