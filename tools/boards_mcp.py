#!/usr/bin/env python3
"""
An MCP server that puts the agent of a person beside the editor: the dialog about a device, the advice on what the
solver chose, and the description a project gets in the end.

The solver runs in the editor, so the editor is served here, on 127.0.0.1, and tells this server what it has. The agent
reads that with MCP tools over stdio and answers in the editor. No key and no model live here: the model is the agent
that started this server. Standard library only, so the Python of ESP-IDF runs it.

Usage, as a server in the MCP configuration of a client: python3 tools/boards_mcp.py [--port N] [--project DIR]
Once, to give it to the agent: python3 tools/boards_mcp.py --install
With no agent, the editor and its solver for the folder it runs in: python3 tools/boards_mcp.py --serve [--project DIR]

The project is the folder the agent works in, or --project: the editor may write its files there through this server, by
the rules of project_writer.py, when the person allows it. A project with its own copy of the component in
managed_components/ is served by that copy: this server hands over to it at the start, so one --install serves every
project, each with the catalog and the board_select.py of its own version. It is how the editor writes from the
integrated browser of VS Code: the files go through this server, not through the browser.
"""
import argparse
import http.server
import json
import os
import pathlib
import posixpath
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse

import project_writer

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTOCOL = "2025-06-18"
NAME = "boards"
VERSION = "0.0.1"
SERVED = ("/editor/", "/catalog/", "/imported/", "/imported-shops/")
HANDED = "BOARDS_MCP_HANDED"  # set at a handover, so the copy that takes it hands over no further
IMPORTED_INDEXES = ("/imported/index.json", "/imported-shops/index.json")
# the files a new project takes from outside editor/, as editor/skeleton/files.json names them: those and no others of their folders
SKELETON_FILES = {posixpath.normpath(f"/editor/{source}") for source, _ in json.loads((ROOT / "editor" / "skeleton" / "files.json").read_text())["files"]}
LONGEST_BODY = 4 * 1024 * 1024
LONGEST_POLL_S = 25
LONGEST_WAIT_S = 120
THEME_QUIET_S = 3  # a theme is told once the person stopped typing it this long
STATE_WAIT_S = 10  # how long page_state waits for the editor to show the last edit of the blocks
# A model thinks between its calls; this long after its last one with no wait open it has most likely ended its turn.
WORKING_S = 90
ACTIVITIES = ("listening", "working", "away")
MOST_PARTS = 40
# a block names a module of the board of the program, so its name is a name of the format
BLOCK_NAME = json.loads((ROOT / "catalog" / "format.schema.json").read_text())["$defs"]["name"]["pattern"]
# where VS Code, its remote server and Cursor keep extensions, under the home folder
EXTENSION_FOLDERS = (".vscode/extensions", ".vscode-insiders/extensions", ".vscode-server/extensions", ".cursor/extensions")
INSTRUCTIONS = """You help a person choose hardware for a device in the editor of jef-sure/boards. Call page_link and give the
person the link. Then loop: wait_for_person, page_state, and say what helps. The field on top of the editor is the theme the
person starts from, the task of page_state: begin from it and ask only what it leaves open, as who uses the device and where
it stands. The dialog develops the theme. wait_for_person also returns the theme when the person changed it. Set what the
device needs with edit_blocks: blocks of roles, their variants and parts, which are the conditions of the solver. What the
person fixed, a block, a part or the board, is theirs: edit_blocks refuses it, and when it leaves the task with no kit, say
why instead of working around it. When few kits fit, refusals of page_state tells what keeps them out: loosen a condition
that is not fixed and say which, or ask the person. The solver in the editor
chooses the kits: comment on them, do not invent parts or wires, and name what is not checked. The solver ranks by what
the person asked; what it only shows, as the antenna quality of a board from 0 to 10, you weigh against the task: where the
device stands and how far it is from what it talks to. When the person is done,
write the description with write_description: the task, the choice and why, and what stays unknown. library_audits tells
what was found in the libraries of a chip: use it in advice, and keep it out of the description."""
TOOLS = [
    {"name": "page_link", "description": "The link of the editor, for the person to open.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "page_state", "description": "What the person wrote and put on the canvas, with the blocks, parts and board the person fixed, the best kits of the solver with what each says, and refusals: why the boards that do not fit do not, the most common first, with how many boards each. After edit_blocks it waits for the editor to show the edit.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "wait_for_person", "description": "Waits for what the person writes in the editor. Returns the new messages, or none after seconds, and the theme of the field on top when it changed.",
     "inputSchema": {"type": "object", "properties": {"seconds": {"type": "integer", "minimum": 1, "maximum": LONGEST_WAIT_S}}}},
    {"name": "say", "description": "Shows a message to the person in the editor.", "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "edit_blocks", "description": "Changes the blocks of the canvas, with why. add: new blocks {role, variant, name, part, asks}; change: blocks by name, "
     "their variant, part or asks; remove: names. asks: the answers of the block to the questions of its role that roles lists, by id, as {\"co2_up_to\": 5000}. A block is named by its name, or by its role when it has none; a name is lowercase Latin letters, digits and _, a letter first. "
     "Blocks the person fixed stay as they are: the answer names what was refused.",
     "inputSchema": {"type": "object", "required": ["why"], "properties": {
         "why": {"type": "string"},
         "add": {"type": "array", "items": {"type": "object", "required": ["role"], "properties": {"role": {"type": "string"}, "variant": {"type": "string"}, "name": {"type": "string"}, "part": {"type": "string"}, "asks": {"type": "object"}}}},
         "change": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "variant": {"type": "string"}, "part": {"type": "string"}, "asks": {"type": "object"}}}},
         "remove": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "write_description", "description": "Sets the description of the device in Markdown: it goes into the project the editor writes.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "roles", "description": "The roles a block can have, by groups, with their variants, and the questions a block of a role can answer in asks.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "library_audits", "description": "What audits found in the libraries of a chip: for your advice, not to repeat as a ranking. The editor shows the order.",
     "inputSchema": {"type": "object", "required": ["chip"], "properties": {"chip": {"type": "string"}}}},
    {"name": "find_parts", "description": "Modules whose title or roles hold these words, from the catalog and imported data.",
     "inputSchema": {"type": "object", "required": ["words"], "properties": {"words": {"type": "string"}}}},
]


class Desk:
    """What the page and the agent share: only this crosses between the threads."""

    def __init__(self):
        self.changed = threading.Condition()
        self.state = {}
        self.messages = []  # {id, from, text, ...}: the page reads them all, the agent those of the person
        self.read_by_agent = 0
        self.theme_told = None  # the theme as the agent last had it
        self.theme_at = 0.0  # when the theme last changed
        self.edited = 0  # the message of the last edit of the blocks
        self.calls = {}  # the tools being called, by name, with how many
        self.call_at = time.monotonic()  # when a call last began or ended: the server starts when the agent does

    def add(self, sender, **fields):
        with self.changed:
            self.messages.append({"id": len(self.messages) + 1, "from": sender, **fields})
            if "edits" in fields:
                self.edited = len(self.messages)
            self.changed.notify_all()

    def called(self, name, begins):
        """A call of a tool begins or ends: what the model does is told to the page."""
        with self.changed:
            self.calls[name] = self.calls.get(name, 0) + (1 if begins else -1)
            self.call_at = time.monotonic()
            self.changed.notify_all()

    def activity(self):
        """What the model does, and since when: listening in wait_for_person, working in another call or between calls,
        away once it has called nothing for WORKING_S."""
        if self.calls.get("wait_for_person", 0) > 0:
            return "listening", self.call_at
        if any(count > 0 for count in self.calls.values()) or time.monotonic() - self.call_at < WORKING_S:
            return "working", self.call_at
        return "away", self.call_at

    def activity_change(self, known, seconds):
        """The activity once it differs from known, or as it is after seconds; away comes by time alone, so the wait looks
        again each second."""
        end = time.monotonic() + seconds
        with self.changed:
            while self.activity()[0] == known and time.monotonic() < end:
                self.changed.wait(min(1.0, end - time.monotonic()))
            state, since = self.activity()
            return {"state": state, "ago_s": round(time.monotonic() - since, 1)}

    def set_state(self, state):
        with self.changed:
            if state.get("task") != self.state.get("task"):
                self.theme_at = time.monotonic()
            self.state = state
            self.changed.notify_all()

    def theme_new(self):
        """A theme the agent has not had, once the person stopped typing it."""
        task = self.state.get("task")
        return bool(task) and task != self.theme_told and time.monotonic() - self.theme_at >= THEME_QUIET_S

    def current_state(self, seconds):
        """The state, once the editor shows the last edit of the blocks, or None after seconds."""
        with self.changed:
            done = self.changed.wait_for(lambda: self.state.get("applied", 0) >= self.edited, timeout=seconds)
            return self.state if done else None

    def since(self, seen, seconds):
        """The messages after seen, waiting for one to come."""
        with self.changed:
            self.changed.wait_for(lambda: len(self.messages) > seen, timeout=seconds)
            return self.messages[seen:]

    def from_person(self, seconds):
        """What the person said since the agent last read, waiting for a message or a new theme."""
        end = time.monotonic() + seconds
        said = lambda: any(item["from"] == "person" for item in self.messages[self.read_by_agent:])
        with self.changed:
            # a theme becomes new by time alone, after the person stops typing: so the wait looks again each second
            while not said() and not self.theme_new() and time.monotonic() < end:
                self.changed.wait(min(1.0, end - time.monotonic()))
            new = [item for item in self.messages[self.read_by_agent:] if item["from"] == "person"]
            self.read_by_agent = len(self.messages)
            return new


def handler_of(desk, token, port, project=None):
    class Page(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, *_):
            pass  # stdout belongs to MCP, and the log of a page says nothing here

        def end_headers(self):
            # every file asked again: a page cached from another copy or version would run one script of each
            if not any(line.lower().startswith(b"cache-control") for line in getattr(self, "_headers_buffer", [])):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def allowed(self):
            """Only this address: another site in the browser can reach 127.0.0.1, but not with this Host and token."""
            return self.headers.get("Host") == f"127.0.0.1:{port}"

        def answer(self, code, value=None):
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def agent_call(self):
            return self.path.startswith("/agent/") and secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}")

        def own_origin(self):
            """A page of another site can send to 127.0.0.1 without reading the answer: what changes anything comes from this one."""
            return self.headers.get("Origin") == f"http://127.0.0.1:{port}"

        def do_GET(self):
            if not self.allowed():
                return self.answer(403)
            address = urllib.parse.urlsplit(self.path)
            if address.path == "/agent/messages":
                if not self.agent_call():
                    return self.answer(401)
                seen = urllib.parse.parse_qs(address.query).get("seen", ["0"])[0]
                if not seen.isdigit():
                    return self.answer(400, {"error": "seen is a count"})
                return self.answer(200, desk.since(int(seen), LONGEST_POLL_S))
            if address.path == "/agent/activity":
                if not self.agent_call():
                    return self.answer(401)
                known = urllib.parse.parse_qs(address.query).get("known", [""])[0]
                if known and known not in ACTIVITIES:
                    return self.answer(400, {"error": f"known is one of {', '.join(ACTIVITIES)}"})
                return self.answer(200, desk.activity_change(known, LONGEST_POLL_S))
            if address.path == "/agent/installed":
                return self.answer(200, installed()) if self.agent_call() else self.answer(401)
            if address.path == "/agent/project":
                if not self.agent_call():
                    return self.answer(401)
                if not project:
                    return self.answer(404, {"error": "no project: the server was started for none"})
                return self.answer(200, {"path": str(project.root), "name": project.name(), "mode": project.mode(), "for_ever": project.allowed_for_ever()})
            if address.path == "/agent/project/file":
                # what lies in the project, for the page to show what a write would change: by the rule of a write
                if not self.agent_call():
                    return self.answer(401)
                rel = urllib.parse.parse_qs(address.query).get("path", [""])[0]
                problem = project_writer.problem_of(project.root, rel) if project and project.mode() else "no project"
                if problem:
                    return self.answer(400, {"error": problem})
                path = project.root / rel
                return self.answer(200, {"text": path.read_text(errors="replace")}) if path.is_file() else self.answer(404)
            # the path as it will be read, not as it was sent: /editor/../CLAUDE.md is no file of the page
            clean = posixpath.normpath(urllib.parse.unquote(address.path))
            if not f"{clean}/".startswith(SERVED) and clean not in SKELETON_FILES:
                return self.answer(404)
            # a tree of imported data this copy does not have is an empty one, as imported-shops/ of the package
            if clean in IMPORTED_INDEXES and not (ROOT / clean.lstrip("/")).is_file():
                return self.answer(200, [])
            self.path = clean + ("/" if address.path.endswith("/") else "")
            return super().do_GET()

        def do_POST(self):
            if not self.allowed() or not self.agent_call() or not self.own_origin():
                return self.answer(401)
            length = int(self.headers.get("Content-Length", "0"))
            if length > LONGEST_BODY:
                return self.answer(413)
            try:
                body = json.loads(self.rfile.read(length) or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self.answer(400, {"error": "not JSON"})
            if self.path in ("/agent/project/plan", "/agent/project/write"):
                return self.project_post(body)
            # only a body of the form the page sends: the tools read the state later, in the thread of MCP
            problem = state_problem(body) if self.path == "/agent/state" else say_problem(body) if self.path == "/agent/say" else None
            if problem:
                return self.answer(400, {"error": problem})
            if self.path == "/agent/state":
                desk.set_state(body)
            elif self.path == "/agent/say":
                desk.add("person", text=body["text"])
            else:
                return self.answer(404)
            return self.answer(200, {})

        def project_post(self, body):
            """A plan of a write, or the write: files by their paths in the project; what is a person's is replaced only
            when replace names it with the digest the plan showed, and nothing is written without allow, once or for ever,
            unless the person gave it for ever."""
            if not project or not project.mode():
                return self.answer(404, {"error": "no project to write: the server was started in no folder of a program"})
            files, replace = body.get("files") if isinstance(body, dict) else None, body.get("replace", {}) if isinstance(body, dict) else None
            if not isinstance(files, dict) or not isinstance(replace, dict):
                return self.answer(400, {"error": "files by their paths, and replace the digests the plan showed by the paths"})
            try:
                if self.path == "/agent/project/plan":
                    return self.answer(200, project.plan(files))
                if not project.allowed_for_ever():
                    if body.get("allow") not in ("once", "for ever"):
                        return self.answer(403, {"error": "the person has not allowed it: ask, once or for ever"})
                    if body["allow"] == "for ever":
                        project.allow_for_ever()
                return self.answer(200, project.write(files, replace))
            except OSError as error:
                # a folder that may not be written, a full disk: the page is told, and the server goes on
                return self.answer(500, {"error": f"{error.filename or 'the project'}: {error.strerror or error}"})

    return Page


def state_problem(body):
    """What is wrong with a state the page sent, or None: an object whose blocks, kits and refusals are lists of objects."""
    if not isinstance(body, dict):
        return "the state is an object"
    lists = {"blocks": dict, "kits": dict, "refusals": dict}
    for key, kind in lists.items():
        if key in body and not (isinstance(body[key], list) and all(isinstance(item, kind) for item in body[key])):
            return f"{key} is a list of objects"
    if any(not isinstance(block.get("role"), str) for block in body.get("blocks", [])):
        return "a block has a role"
    if "task" in body and not isinstance(body["task"], str):
        return "task is a text"
    if "applied" in body and not (isinstance(body["applied"], int) and not isinstance(body["applied"], bool)):
        return "applied is the number of a message"
    return None


def say_problem(body):
    """What is wrong with what the person said, or None: an object with a text."""
    return None if isinstance(body, dict) and isinstance(body.get("text"), str) else "a text"


def find_parts(words):
    wanted = [word for word in re.split(r"\W+", words.lower()) if word]
    found = []
    for root in ("catalog", "imported-shops", "imported"):
        for path in sorted((ROOT / root).glob("modules/*/module.json")):
            doc = json.loads(path.read_text())
            roles = sorted({role for device in doc.get("devices", {}).values() for role in device.get("provides") or {}})
            text = " ".join([doc.get("title", ""), *roles, *(str(device.get("chip", "")) for device in doc.get("devices", {}).values())]).lower()
            if all(word in text for word in wanted) and doc["name"] not in {item["name"] for item in found}:
                found.append({"name": doc["name"], "title": doc.get("title"), "roles": roles, "from": root, "checked": sorted({entry.get("level") for entry in doc.get("checked", {}).values()})})
    return found[:MOST_PARTS]


def library_audits(chip):
    """The last audit of each library of a chip, with what it requires: the order itself is the solver's."""
    folder = ROOT / "catalog" / "libraries"
    listed = json.loads((folder / "libraries.json").read_text())["libraries"]
    found = []
    for library in json.loads((folder / "chip_libraries.json").read_text())["chips"].get(chip, []):
        path = folder / library / "audit.json"
        if path.exists():
            last = json.loads(path.read_text())["audits"][-1]
            found.append({"library": library, "version": last.get("version"), "commit": last["commit"], "requires": listed[library].get("requires", []), "not_there": sorted(name for name, item in last["items"].items() if item["status"] == "no"),
                          "defects": [{key: defect[key] for key in ("severity", "what", "evidence") } for defect in last["defects"]]})
    return found


def call(desk, link, name, arguments):
    if name == "page_link":
        return {"link": link}
    if name == "page_state":
        state = desk.current_state(STATE_WAIT_S)
        if state is None:
            state = {**desk.state, "note": f"The editor has not shown the last edit of the blocks in {STATE_WAIT_S} s: this is the state before it."}
        desk.theme_told = state.get("task")
        return state or {"note": "The editor is not open yet."}
    if name == "wait_for_person":
        said = {"messages": [item["text"] for item in desk.from_person(min(arguments.get("seconds", LONGEST_WAIT_S), LONGEST_WAIT_S))]}
        theme = desk.state.get("task")
        if theme and theme != desk.theme_told:
            desk.theme_told = theme
            said["theme"] = theme
        return said
    if name == "say":
        desk.add("model", text=arguments["text"])
        return {"shown": True}
    if name == "edit_blocks":
        # the person's fixed blocks are refused here and again by the page, which holds the canvas
        fixed = {block.get("name") or block.get("role") for block in desk.state.get("blocks", []) if block.get("fixed")}
        wanted = [item["name"] for item in arguments.get("change", [])] + list(arguments.get("remove", [])) + [item.get("name") or item["role"] for item in arguments.get("add", [])]
        roles = {role["id"] for group in json.loads((ROOT / "catalog" / "roles.json").read_text())["groups"] for role in group["roles"]}
        unknown = [item["role"] for item in arguments.get("add", []) if item["role"] not in roles]
        misnamed = [item["name"] for item in arguments.get("add", []) if item.get("name") and not re.fullmatch(BLOCK_NAME, item["name"])]
        refused = sorted({name for name in wanted if name in fixed})
        edits = {"add": [item for item in arguments.get("add", []) if (item.get("name") or item["role"]) not in fixed and item["role"] in roles
                         and item.get("name", "") not in misnamed],
                 "change": [item for item in arguments.get("change", []) if item["name"] not in fixed],
                 "remove": [name for name in arguments.get("remove", []) if name not in fixed]}
        desk.add("model", text=arguments["why"], edits=edits)
        return {"applied": edits, "refused": [{"name": name, "why": "the person fixed it"} for name in refused] + [{"name": role, "why": "no such role: see roles"} for role in unknown]
                + [{"name": name, "why": f"a name should match {BLOCK_NAME}: it names a module of the board of the program"} for name in misnamed]}
    if name == "write_description":
        desk.add("model", text=arguments["text"], description=True)
        return {"shown": True}
    if name == "roles":
        asks = [question for question in json.loads((ROOT / "catalog" / "questions.json").read_text())["questions"] if question.get("limit", {}).get("field") or question.get("asked") == "block"]
        return {"groups": json.loads((ROOT / "catalog" / "roles.json").read_text())["groups"], "asks": asks}
    if name == "find_parts":
        return find_parts(arguments["words"])
    if name == "library_audits":
        return library_audits(arguments["chip"])
    raise KeyError(name)


KINDS = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float)}


def argument_problem(schema, value, at="arguments"):
    """What in the arguments of a tool its inputSchema does not take, in words, or None."""
    kind = schema.get("type")
    if kind and (not isinstance(value, KINDS[kind]) or (kind in ("integer", "number") and isinstance(value, bool))):
        return f"{at} is not {'an' if kind[0] in 'aeiou' else 'a'} {kind}"
    if kind in ("integer", "number") and not schema.get("minimum", value) <= value <= schema.get("maximum", value):
        return f"{at} is out of {schema.get('minimum', '…')}..{schema.get('maximum', '…')}"
    if kind == "object":
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            return f"{at} has no {', '.join(missing)}"
        return next((found for name, part in schema.get("properties", {}).items() if name in value
                     for found in [argument_problem(part, value[name], f"{at}.{name}")] if found), None)
    if kind == "array" and "items" in schema:
        return next((found for i, item in enumerate(value) for found in [argument_problem(schema["items"], item, f"{at}[{i}]")] if found), None)
    return None


def answer_of(desk, link, request, tools=TOOLS, instructions=INSTRUCTIONS):
    """The answer to a request of MCP, or None for a notification."""
    if not isinstance(request, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "a request is an object"}}
    method, ident = request.get("method"), request.get("id")
    if ident is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": {"name": NAME, "version": VERSION}, "instructions": instructions}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tools}
    elif method == "tools/call":
        params = request.get("params")
        tool = next((item for item in tools if isinstance(params, dict) and item["name"] == params.get("name")), None)
        arguments = (params.get("arguments") or {}) if tool else None
        problem = ("tools/call takes params with the name of a tool of tools/list" if not tool else argument_problem(tool["inputSchema"], arguments))
        if problem:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": problem}}
        desk.called(tool["name"], True)
        try:
            value = call(desk, link, tool["name"], arguments)
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
        except Exception as error:  # a tool that fails answers with an error: the conversation goes on
            result = {"content": [{"type": "text", "text": f"{tool['name']} failed: {error}"}], "isError": True}
        finally:
            desk.called(tool["name"], False)
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def installed():
    """The versions of the platforms on this computer: ESP-IDF of EIM, of IDF_PATH and in ~/esp, read from version.cmake, and the
    Arduino core of ESP32 by its folder. The kit names those that take it, so the person builds with what is there."""
    home = pathlib.Path.home()
    trees = [*home.glob(".espressif/v*/esp-idf"), *home.glob("esp/esp-idf*"), *([pathlib.Path(os.environ["IDF_PATH"])] if os.environ.get("IDF_PATH") else [])]
    idf = set()
    for tree in trees:
        cmake = tree / "tools" / "cmake" / "version.cmake"
        if cmake.is_file():
            parts = dict(re.findall(r"set\(IDF_VERSION_(MAJOR|MINOR|PATCH) (\d+)\)", cmake.read_text()))
            if len(parts) == 3:
                idf.add(f"{parts['MAJOR']}.{parts['MINOR']}.{parts['PATCH']}")
    arduino = {folder.name for folder in home.glob(".arduino15/packages/esp32/hardware/esp32/*") if re.fullmatch(r"\d+\.\d+\.\d+", folder.name)}
    newest = lambda versions: sorted(versions, key=lambda text: [int(part) for part in text.split(".")], reverse=True)
    return {"esp_idf": newest(idf), "arduino_esp32": newest(arduino), "component": project_writer.component_source()}



def claude_command():
    """The command of Claude Code: on PATH, or the newest in its extension for VS Code, which does not put it on PATH."""
    found = shutil.which("claude")
    if found:
        return found
    home = pathlib.Path.home()
    inside = [path for folder in EXTENSION_FOLDERS for path in home.glob(f"{folder}/anthropic.claude-code-*/resources/native-binary/claude*")
              if path.is_file() and os.access(path, os.X_OK)]
    version = lambda path: [int(part) for part in re.findall(r"\d+", path.parents[2].name.split("-")[2])]
    return str(max(inside, key=version)) if inside else None


def install():
    """Gives this server to the agent of the person: to Claude Code for every folder when its command is there, otherwise in
    .mcp.json of the folder it runs in, beside the servers that file names. Full paths, so the folder of the agent does not matter."""
    server = {"command": sys.executable, "args": [str(pathlib.Path(__file__).resolve())]}
    claude = claude_command()
    if claude:
        done = subprocess.run([claude, "mcp", "add", "-s", "user", NAME, "--", server["command"], *server["args"]], capture_output=True, text=True)
        print((done.stdout + done.stderr).strip())
        if done.returncode:
            print(f"To give it again: {claude} mcp remove -s user {NAME}, then this command once more.")
            return done.returncode
    else:
        path = pathlib.Path(".mcp.json")
        config = json.loads(path.read_text()) if path.exists() else {}
        config.setdefault("mcpServers", {})[NAME] = server
        path.write_text(json.dumps(config, indent=2) + "\n")
        print(f"{path.resolve()}: the server {NAME} is there. A client other than Claude Code may want it in its own settings:")
        print(json.dumps({"mcpServers": {NAME: server}}, indent=2))
    print("Start the agent again and ask it to help choose the hardware of a device: it gives the link of the editor.")
    return 0


def of_boards(project):
    """Whether the editor has a use in the folder: an empty one for a new device, or a program of ESP-IDF, which may move
    onto boards. Elsewhere an install for every folder would only cost an agent a server."""
    mode = project.mode()
    cmake = project.root / "CMakeLists.txt"
    return mode == "create" or (mode == "update" and "project.cmake" in cmake.read_text(errors="replace"))


def answer_rows(answer):
    """Answers the requests of MCP on stdin until it closes."""
    for row in sys.stdin:
        if row.strip():
            try:
                request = json.loads(row)
            except json.JSONDecodeError as error:
                request = error
            reply = answer(request) if not isinstance(request, json.JSONDecodeError) else \
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"not JSON: {request.msg} at {request.pos}"}}
            if reply:
                sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
                sys.stdout.flush()


def own_copy(project):
    """The server of the project's own copy of the component, when it has one and this is not it."""
    if os.environ.get(HANDED):
        return None
    theirs = project / "managed_components" / "jef-sure__boards" / "tools" / "boards_mcp.py"
    return theirs if theirs.is_file() and theirs.resolve() != pathlib.Path(__file__).resolve() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=0, help="0: any free port")
    parser.add_argument("--install", action="store_true", help="give this server to the agent and stop")
    parser.add_argument("--serve", action="store_true", help="no agent: serve the editor and print its link, until Ctrl-C")
    parser.add_argument("--project", type=pathlib.Path, default=pathlib.Path.cwd(), help="the folder the editor may write a project into, when the person allows it")
    args = parser.parse_args()
    if args.install:
        return install()
    if not args.project.is_dir():
        parser.error(f"--project {args.project}: no such folder")
    theirs = own_copy(args.project.resolve())
    if theirs:
        print(f"boards_mcp.py: the project's own copy serves it: {theirs}", file=sys.stderr, flush=True)
        os.environ[HANDED] = "1"
        os.execv(sys.executable, [sys.executable, str(theirs), *sys.argv[1:]])

    if not args.serve and not of_boards(project_writer.Project(args.project)):
        # no tools and no editor: the agent of an unrelated folder sees an empty server
        idle = f"{args.project.resolve()} is neither an empty folder nor a program of ESP-IDF: boards offers nothing here."
        answer_rows(lambda request: answer_of(None, None, request, tools=[], instructions=idle))
        return 0

    desk = Desk()
    token = secrets.token_urlsafe(24)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), None)
    port = server.server_address[1]
    server.RequestHandlerClass = handler_of(desk, token, port, project_writer.Project(args.project))
    server.daemon_threads = True
    if args.serve:
        # no model talks: the page shows no dialog, and the solver and the writes of the project work as with one
        project = project_writer.Project(args.project)
        print(f"http://127.0.0.1:{port}/editor/#agent={token}&model=none", flush=True)
        print(f"The editor writes a project into {project.root} when you allow it" if project.mode() else
              f"{project.root} is neither empty nor a program: the editor chooses and does not write there", flush=True)
        print("Ctrl-C stops the server.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    link = f"http://127.0.0.1:{port}/editor/#agent={token}"

    answer_rows(lambda request: answer_of(desk, link, request))
    return 0


if __name__ == "__main__":
    sys.exit(main())
