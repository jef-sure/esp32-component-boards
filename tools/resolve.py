#!/usr/bin/env python3
"""
Loads a board of the catalog: the layers merged by JSON Merge Patch (RFC 7386, null removes), the
catalog under each device, the lines in one form. What it gives is what the rules and the generator
read. The order, general to particular: device, family variant, board, board variant, overlays
(mine for the model, the project).
"""
import copy
import functools
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROOTS = [ROOT / "catalog"]  # check_format.py adds the entries of its cases
LOCAL_BOARDS = "components/local-boards"  # what is a program's own, in the layout of catalog/
FILES = {"mcu": "mcu.json", "devices": "device.json", "modules": "module.json", "boards": "board.json", "libraries": "library.json", "connectors": "connector.json"}
NOT_LINES = {"hz", "lanes", "lane_mbps", "phy_ldo_chan", "phy_ldo_mv", "baud", "data"}
LINE = 120
TYPE_FIELDS = ("class", "maker", "part", "compat", "draw", "pins", "config", "controls", "provides", "start", "firmware", "ways")
LIBRARY_HISTORY = ("license", "chips", "transports", "interfaces", "groups", "values")
FIRMWARE_HISTORY = ("config", "controls", "provides")
REFERENCES = {"over", "via", "left", "right", "after", "devices", "feeds", "from", "through", "name", "logic"}  # fields of a module that name its parts
REVISION_HISTORY = ("limits", "provides", "controls", "sdkconfig")
MODULE_FACTS = ("maker", "part", "revision", "mcu", "price", "tariff")  # what a board keeps of a module beside its parts


class Refused(Exception):
    pass


def add_project(project):
    """Reads the local-boards of a program before the catalog. Returns that directory."""
    local = pathlib.Path(project).resolve() / LOCAL_BOARDS
    if local not in ROOTS:
        ROOTS.insert(0, local)
    return local


def load(kind, name):
    for root in ROOTS:
        path = root / kind / name / FILES[kind]
        if path.exists():
            return json.loads(path.read_text())
    raise Refused(f"the catalog has no {kind} entry {name}")


def library_id(record):
    return f"{record['ecosystem']}/{record['owner']}/{record['name']}"


def library(name):
    return load("libraries", name)


@functools.lru_cache
def all_libraries(roots):
    found = {}
    for root in roots:
        for path in sorted((root / "libraries").glob("*/*/*/library.json")):
            record = json.loads(path.read_text())
            found.setdefault(library_id(record), record)
    return found


def runs(text):
    return tuple((0, int(run)) if run.isdigit() else (1, run) for run in re.findall(r"\d+|\D+", text))


def version_key(version, scheme="decimal"):
    """A version in a form that compares: parts by value (in hex for that scheme), 1.0 as 1.0.0, a pre-release below its release, a revision above it."""
    text, _, revision = version.lstrip("vV").partition("+")[0].partition("~")
    text, _, pre = text.partition("-")
    parts = []
    for part in text.split("."):
        try:
            parts.append((0, int(part, 16 if scheme == "hex" else 10)))
        except ValueError:
            parts.append((1, part))
    while parts and parts[-1] == (0, 0):
        parts.pop()
    return tuple(parts), not pre, runs(pre), int(revision or 0)


def at_version(doc, versions, version, fields):
    """doc as it was in a version: versions has the version described and the history, applied from the newest step down."""
    key = functools.partial(version_key, scheme=versions.get("scheme", "decimal"))
    if key(version) > key(versions["described"]):
        raise Refused(f"only {versions['described']} and older are described, not {version}")
    for step in sorted(versions.get("history") or (), key=lambda step: key(step["before"]), reverse=True):
        if key(version) < key(step["before"]):
            doc = merge(doc, {key: step[key] for key in fields if key in step})
    return doc


def library_at(record, version):
    return at_version(record, record, version, LIBRARY_HISTORY)


def chip_settings(mcu, revision=None):
    """The sdkconfig lines of a chip of a revision: what the revision takes, held down by what the board says. None for a chip whose revisions do not differ."""
    facts = load("mcu", mcu["target"])
    if "revisions" not in facts:
        return []
    revision = revision or mcu["revision"]
    at = at_version(facts, facts["revisions"], revision, REVISION_HISTORY)
    major, minor = (int(part) for part in revision.split("."))
    option = max(number for number in facts["revisions"]["options"] if number <= major * 100 + minor)
    lines = [*at["sdkconfig"]["lines"], at["sdkconfig"]["revision"].format(value=option) + "=y"]
    for name in ("psram_mhz", "cpu_mhz"):
        if name != "psram_mhz" or mcu.get("psram_mb"):
            lines.append(at["sdkconfig"][name].format(value=min(mcu.get(name, at["limits"][name]), at["limits"][name])) + "=y")
    return lines


def libraries_of(chip):
    """The libraries of the catalog that have this chip, by id: the entry of the chip in each."""
    return {name: record["chips"][chip] for name, record in all_libraries(tuple(ROOTS)).items() if chip in record.get("chips", {})}


def merge(base, patch):
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = merge(out.get(key), value)
    return out


def chain(doc):
    if not doc.get("extends"):
        return doc
    own = {key: value for key, value in doc.items() if key != "extends"}
    base = chain(load("modules" if doc.get("kind") == "module" else "boards", doc["extends"]))
    for entry in (base.get("checked") or {}).values():
        entry.setdefault("on_board", base["name"])
    return merge(base, own)


def line(value):
    return {"gpio": value} if isinstance(value, int) and not isinstance(value, bool) else value


def chips_of(device):
    """The chips a device can be: one, or those it tries at start."""
    return [device["chip"]] if "chip" in device else device.get("chip_try", [])


def apply_type(device):
    if "chip" not in device:
        for chip in chips_of(device):
            load("devices", chip)
        return device
    entry = load("devices", device["chip"])
    base = {key: entry[key] for key in TYPE_FIELDS if key in entry}
    if "variant" in device:
        variants = entry.get("variants") or {}
        if device["variant"] not in variants:
            raise Refused(f"{device['chip']} has no variant {device['variant']}")
        base = merge(base, variants[device["variant"]])
    if "firmware_version" in device:
        if "described" not in (base.get("firmware") or {}):
            raise Refused(f"{device['chip']} has no firmware versions in the catalog")
        base = at_version(base, base["firmware"], device["firmware_version"], FIRMWARE_HISTORY)
    out = merge(base, {key: value for key, value in device.items() if key != "on"})
    defaults = merge(entry.get("on") or {}, {key: value for key, value in (device.get("on") or {}).items() if "." not in key})
    concrete = {key: value for key, value in (device.get("on") or {}).items() if "." in key}
    wired = {key: merge({k: v for k, v in (defaults.get(key.split(".")[0]) or {}).items() if k != "required"}, value) for key, value in concrete.items()}
    for connection in wired.values():
        if "address" in connection:
            connection.pop("address_try", None)
    out["on"] = wired or {key: {k: v for k, v in value.items() if k != "required"} for key, value in (device.get("on") or {}).items()}
    out["wants"] = {key: {"required": bool(value.get("required")), **({"lines": value["lines"]} if "lines" in value else {})} for key, value in (entry.get("on") or {}).items()}
    libraries = libraries_of(device["chip"])
    if "library" not in out and len(libraries) == 1:
        out["library"] = next(iter(libraries))
    if out.get("library") in libraries:
        record = all_libraries(tuple(ROOTS))[out["library"]]
        out["library_at"] = out.get("library_version", record["described"])
        chips = library_at(record, out["library_at"])["chips"]
        libraries.pop(out["library"])
        if device["chip"] in chips:
            libraries[out["library"]] = chips[device["chip"]]
    out["libraries"] = libraries
    return out


def normal(device):
    cls = device.get("class")
    device["classes"] = [cls] if isinstance(cls, str) else list(cls or [])
    device.pop("class", None)
    if "pins" in device:
        device["pins"] = {key: line(value) for key, value in device["pins"].items()}
    for connection in (device.get("on") or {}).values():
        if "cs" in connection:
            connection["cs"] = line(connection["cs"])
    config = device.get("config") or {}
    if config.get("buttons"):
        config["buttons"] = {key: line(value) for key, value in config["buttons"].items()}
    if isinstance(config.get("divider"), dict) and "switch" in config["divider"]:
        config["divider"]["switch"] = line(config["divider"]["switch"])
    return device


def named(value, names):
    if isinstance(value, list):
        return [named(item, names) for item in value]
    return renamed(value, names) if isinstance(value, dict) else names.get(value, value)


def renamed(value, names):
    """A part of a module with the names it refers to as they are on the board."""
    if isinstance(value, dict):
        return {key: named(item, names) if key in REFERENCES else renamed(item, names) for key, item in value.items()}
    if isinstance(value, list):
        return [renamed(item, names) for item in value]
    return value


def joined(device, wiring):
    """The on of a part with each kind of bus it has, its own or its chip's, on the bus of the board it joins."""
    if not wiring:
        return device
    own = device.get("on") or {}
    kinds = {*own, *(kind for chip in chips_of(device) for kind in load("devices", chip).get("on") or {})}
    taken = {bus.split(".")[0]: bus for bus in wiring}
    on = {key: value for key, value in own.items() if key not in taken}
    for kind, bus in taken.items():
        if kind in kinds:
            on[bus] = merge(own.get(kind) or {}, wiring[bus])
    return {**device, "on": on}


def supplied(steps, supply, name):
    """The steps a module takes from its board, on the lines the wiring names."""
    open_steps = {step.get("name") for step in steps if step.get("source") == "connector"}
    for step in supply:
        if step not in open_steps:
            raise Refused(f"{name}: no step {step} to feed")
    return [{**{key: item for key, item in step.items() if key != "source"}, "from": supply[step["name"]]} if step.get("name") in supply else step for step in steps]


def use_module(doc, name, use):
    module = chain(load("modules", use["module"]))
    add_modules(module)
    parts = module["devices"]
    if len(parts) > 1 and ({"pins", "config"} & use.keys() or any(use.get("on", {}).values())):
        raise Refused(f"{name}: a module of several parts takes its wiring by part, in devices: {', '.join(parts)}")
    own = [*parts, *(step["name"] for step in module.get("power") or [] if "name" in step), *(["mcu"] if "mcu" in module else [])]
    names = {part: f"{name}_{part}" for part in own}
    for part in use.get("devices") or {}:
        if part not in parts:
            raise Refused(f"{name}: the module {use['module']} has no part {part}")
    for part, template in parts.items():
        device = joined(renamed(template, names), use.get("on"))
        wiring = {key: use[key] for key in ("config", "pins") if key in use}
        doc["devices"][names[part]] = merge(merge(device, wiring), (use.get("devices") or {}).get(part) or {})
    for field in ("display_groups", "shared_pins", "connectors"):
        for own, entry in (module.get(field) or {}).items():
            doc.setdefault(field, {})[f"{name}_{own}"] = renamed(entry, names)
    doc["power"] = (doc.get("power") or []) + supplied(renamed(module.get("power") or [], names), {names.get(step, step): line for step, line in (use.get("supply") or {}).items()}, name)
    if not doc["power"]:
        del doc["power"]
    return {"module": use["module"], "title": module["title"], **{key: module[key] for key in MODULE_FACTS if key in module}}


def add_modules(doc):
    doc.setdefault("devices", {})
    doc["modules"] = {name: use_module(doc, name, use) for name, use in (doc.pop("modules", None) or {}).items()}


def listed(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def removed(doc):
    """The devices a layer takes away with null, and those its bases took."""
    names = {name for name, device in (doc.get("devices") or {}).items() if device is None}
    return names | removed(load("modules" if doc.get("kind") == "module" else "boards", doc["extends"])) if doc.get("extends") else names


def power_step(step, gone):
    """A step in one form: its line, inputs that each name a step and the devices on the way from it, feeds without the devices a layer removed."""
    if "line" in step:
        step["line"] = line(step["line"])
    if "from" in step:
        inputs = [{"name": item} if isinstance(item, str) else item for item in listed(step.pop("from"))]
        common = listed(step.pop("through", None))
        step["inputs"] = [{**item, "through": listed(item.get("through")) + common} for item in inputs]
    if "feeds" in step:
        step["feeds"] = [name for name in step["feeds"] if name not in gone]
    return step


def connector_of(name, connector):
    """The facts of a connector whose contacts a standard fixes."""
    connector["facts"] = load("connectors", connector["of"])
    if len(connector["pins"]) != len(connector["facts"]["pins"]):
        raise Refused(f"connector {name}: {connector['of']} has {len(connector['facts']['pins'])} contacts, not {len(connector['pins'])}")


def resolve(doc, overlays=()):
    out = chain(doc)
    for layer in overlays:
        out = merge(out, {key: value for key, value in layer.items() if key not in ("kind", "name", "title", "extends")})
    if out.get("kind") == "project":
        out["kind"] = "board"
    add_modules(out)
    out["devices"] = {name: normal(apply_type(device)) for name, device in (out.get("devices") or {}).items()}
    gone = set().union(removed(doc), *map(removed, overlays)) - out["devices"].keys()
    if "power" in out:
        out["power"] = [power_step(step, gone) for step in out["power"]]
    for name, connector in (out.get("connectors") or {}).items():
        if "of" in connector:
            connector_of(name, connector)
    if out.get("kind") == "board":
        for named in (out.get("buses") or {}).values():
            for bus in named.values():
                for key, value in bus.items():
                    if key not in NOT_LINES:
                        bus[key] = line(value)
                if "data" in bus:
                    bus["data"] = [line(value) for value in bus["data"]]
        for group in (out.get("shared_pins") or {}).values():
            group["line"] = line(group["line"])
        for connector in (out.get("connectors") or {}).values():
            connector["pins"] = [line(value) for value in connector["pins"]]
        if "mcu" in out:
            facts = load("mcu", out["mcu"]["target"])
            if "revision" in out["mcu"] and "revisions" in facts:
                facts = at_version(facts, facts["revisions"], out["mcu"]["revision"], REVISION_HISTORY)
            out["mcu"]["facts"] = facts
            provides = {name: {"by": ["mcu"]} for name in out["mcu"]["facts"].get("provides") or {}}
            if out["mcu"].get("psram_mb"):
                provides["psram"] = {"by": ["mcu"]}
            for name, device in out["devices"].items():
                for capability in device.get("provides") or {}:
                    provides.setdefault(capability, {"by": []})["by"].append(name)
            out["provides"] = provides
    return out


def dump(value, indent=0, used=0):
    """JSON of the catalog: what fits a line stays on one, the rest opens up."""
    one = json.dumps(value, ensure_ascii=False)
    if not isinstance(value, (dict, list)) or not value or (indent and indent + used + len(one) <= LINE):
        return one
    pad = " " * (indent + 4)
    if isinstance(value, dict):
        body = ",\n".join(f"{pad}{json.dumps(key, ensure_ascii=False)}: {dump(item, indent + 4, len(key) + 4)}" for key, item in value.items())
        return "{\n" + body + "\n" + " " * indent + "}"
    return "[\n" + ",\n".join(pad + dump(item, indent + 4) for item in value) + "\n" + " " * indent + "]"


def trust(board, path, order):
    """What a path stands on: the best confirmed level of the entries that cover it, and those pending or refuted."""
    entries = []
    for name, entry in (board.get("checked") or {}).items():
        covers = entry.get("covers")
        if covers is None or any(path == c or path.startswith(c + ".") for c in covers):
            entries.append((name, entry))
    confirmed = [e["level"] for _, e in entries if e.get("result", "confirmed") == "confirmed" and "on_board" not in e]
    open_ones = [f"{n}: {e.get('result')}" for n, e in entries if e.get("result", "confirmed") != "confirmed"]
    inherited = [e["level"] for _, e in entries if "on_board" in e]
    best = min(confirmed, key=order.index) if confirmed else (f"only inherited {min(inherited, key=order.index)}" if inherited else "nothing")
    return best, open_ones
