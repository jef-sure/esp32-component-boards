#!/usr/bin/env python3
"""
An MCP server that puts the agent of a person beside the page: the dialog about a device, the advice on what the
solver chose, and the description a project gets in the end.

The solver runs in the page, so the page is served here, on 127.0.0.1, and tells this server what it has. The agent
reads that with MCP tools over stdio and answers in the page. No key and no model live here: the model is the agent
that started this server. Standard library only, so the Python of ESP-IDF runs it.

Usage, as a server in the MCP configuration of a client: python3 tools/boards_mcp.py [--port N]
"""
import argparse
import http.server
import json
import pathlib
import posixpath
import re
import secrets
import sys
import threading
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTOCOL = "2025-06-18"
NAME = "boards"
VERSION = "0.0.1"
SERVED = ("/editor/", "/catalog/", "/imported/", "/imported-shops/")
LONGEST_BODY = 4 * 1024 * 1024
LONGEST_POLL_S = 25
LONGEST_WAIT_S = 120
MOST_PARTS = 40
INSTRUCTIONS = """You help a person choose hardware for a device on the page of jef-sure/boards. Call page_link and give the
person the link. Then loop: wait_for_person, page_state, and say what helps. Ask what the device does, who uses it and
where it stands. Propose blocks of roles with propose_blocks: the person accepts them on the page. The solver on the page
chooses the kits: comment on them, do not invent parts or wires, and name what is not checked. When the person is done,
write the description with write_description: the task, the choice and why, and what stays unknown. library_audits tells
what was found in the libraries of a chip: use it in advice, and keep it out of the description."""
TOOLS = [
    {"name": "page_link", "description": "The link of the page, for the person to open.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "page_state", "description": "What the person wrote and put on the canvas, and the best kits of the solver with what each says.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "wait_for_person", "description": "Waits for what the person writes in the page. Returns the new messages, or none after seconds.",
     "inputSchema": {"type": "object", "properties": {"seconds": {"type": "integer", "minimum": 1, "maximum": LONGEST_WAIT_S}}}},
    {"name": "say", "description": "Shows a message to the person in the page.", "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "propose_blocks", "description": "Offers blocks for the canvas, with why. The person accepts or leaves them. A block: {role, variant, name}.",
     "inputSchema": {"type": "object", "required": ["blocks", "why"], "properties": {"blocks": {"type": "array", "items": {"type": "object", "required": ["role"]}}, "why": {"type": "string"}}}},
    {"name": "write_description", "description": "Sets the description of the device in Markdown: it goes into the project the page writes.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "roles", "description": "The roles a block can have, by groups, with their variants.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "library_audits", "description": "What audits found in the libraries of a chip: for your advice, not to repeat as a ranking. The page shows the order.",
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

    def add(self, sender, **fields):
        with self.changed:
            self.messages.append({"id": len(self.messages) + 1, "from": sender, **fields})
            self.changed.notify_all()

    def since(self, seen, seconds):
        """The messages after seen, waiting for one to come."""
        with self.changed:
            self.changed.wait_for(lambda: len(self.messages) > seen, timeout=seconds)
            return self.messages[seen:]

    def from_person(self, seconds):
        with self.changed:
            self.changed.wait_for(lambda: any(item["from"] == "person" for item in self.messages[self.read_by_agent:]), timeout=seconds)
            new = [item for item in self.messages[self.read_by_agent:] if item["from"] == "person"]
            self.read_by_agent = len(self.messages)
            return new


def handler_of(desk, token, port):
    class Page(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, *_):
            pass  # stdout belongs to MCP, and the log of a page says nothing here

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

        def do_GET(self):
            if not self.allowed():
                return self.answer(403)
            address = urllib.parse.urlsplit(self.path)
            if address.path == "/agent/messages":
                if not self.agent_call():
                    return self.answer(401)
                seen = int(urllib.parse.parse_qs(address.query).get("seen", ["0"])[0])
                return self.answer(200, desk.since(seen, LONGEST_POLL_S))
            # the path as it will be read, not as it was sent: /editor/../CLAUDE.md is no file of the page
            clean = posixpath.normpath(urllib.parse.unquote(address.path))
            if not f"{clean}/".startswith(SERVED):
                return self.answer(404)
            self.path = clean + ("/" if address.path.endswith("/") else "")
            return super().do_GET()

        def do_POST(self):
            if not self.allowed() or not self.agent_call():
                return self.answer(401)
            length = int(self.headers.get("Content-Length", "0"))
            if length > LONGEST_BODY:
                return self.answer(413)
            body = json.loads(self.rfile.read(length) or "{}")
            if self.path == "/agent/state":
                desk.state = body
            elif self.path == "/agent/say":
                desk.add("person", text=str(body.get("text", "")))
            else:
                return self.answer(404)
            return self.answer(200, {})

    return Page


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
        return desk.state or {"note": "The page is not open yet."}
    if name == "wait_for_person":
        return {"messages": [item["text"] for item in desk.from_person(min(arguments.get("seconds", LONGEST_WAIT_S), LONGEST_WAIT_S))]}
    if name == "say":
        desk.add("model", text=arguments["text"])
        return {"shown": True}
    if name == "propose_blocks":
        desk.add("model", text=arguments["why"], blocks=arguments["blocks"])
        return {"shown": True, "note": "The person accepts them on the page."}
    if name == "write_description":
        desk.add("model", text=arguments["text"], description=True)
        return {"shown": True}
    if name == "roles":
        return json.loads((ROOT / "catalog" / "roles.json").read_text())["groups"]
    if name == "find_parts":
        return find_parts(arguments["words"])
    if name == "library_audits":
        return library_audits(arguments["chip"])
    raise KeyError(name)


def answer_of(desk, link, request):
    """The answer to a request of MCP, or None for a notification."""
    method, ident = request.get("method"), request.get("id")
    if ident is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": {"name": NAME, "version": VERSION}, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        try:
            value = call(desk, link, params.get("name"), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
        except (KeyError, ValueError) as error:
            result = {"content": [{"type": "text", "text": f"{params.get('name')}: {error!r}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=0, help="0: any free port")
    args = parser.parse_args()

    desk = Desk()
    token = secrets.token_urlsafe(24)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), None)
    port = server.server_address[1]
    server.RequestHandlerClass = handler_of(desk, token, port)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    link = f"http://127.0.0.1:{port}/editor/#agent={token}"

    for row in sys.stdin:
        if row.strip():
            answer = answer_of(desk, link, json.loads(row))
            if answer:
                sys.stdout.write(json.dumps(answer, ensure_ascii=False) + "\n")
                sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
