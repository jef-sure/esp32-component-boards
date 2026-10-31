#!/usr/bin/env python3
"""The engine of rules.json, in Python for the generator. rules.js is the same engine for the editor."""
import json
import re

MISSING = object()


def fill(text, ctx):
    return re.sub(r"\{([\w.]+)\}", lambda m: str(ctx[m[1]]) if m[1] in ctx else m[0], text)


def get(doc, path, ctx):
    node = doc
    for token in path.split("."):
        token = fill(token, ctx)
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            return MISSING
    return node


def walk(node, parts, keys):
    if not parts:
        yield node, keys
        return
    head, rest = parts[0], parts[1:]
    if head == "*":
        pairs = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
        for key, child in pairs:
            yield from walk(child, rest, keys + [str(key)])
    elif isinstance(node, dict) and head in node:
        yield from walk(node[head], rest, keys)
    elif isinstance(node, list) and head.isdigit() and int(head) < len(node):
        yield from walk(node[int(head)], rest, keys)


def holds(doc, cond, ctx):
    value = fill(cond["text"], ctx) if "text" in cond else get(doc, cond["path"], ctx)
    if value is MISSING:
        return False
    if "is" in cond:
        return value == cond["is"]
    if "not" in cond:
        return value != cond["not"]
    if "has" in cond:
        return cond["has"] in value if isinstance(value, list) else value == cond["has"]
    if "in" in cond:
        return value in cond["in"]
    return True


def post(items, spec):
    out = []
    for item in items:
        node = item["node"]
        if "with" in spec and not (isinstance(node, dict) and spec["with"] in node):
            continue
        value = item["value"]
        if "take" in spec:
            if not (isinstance(node, dict) and spec["take"] in node):
                continue
            value = node[spec["take"]]
        if "as" in spec:
            value = fill(spec["as"], item["ctx"])
        if "strip" in spec:
            value = re.sub(spec["strip"], "", value)
        out.append({**item, "value": value, "ctx": {**item["ctx"], "value": value}})
    return out


def select(doc, spec, sets):
    if isinstance(spec, str):
        return select(doc, sets[spec], sets)
    if isinstance(spec, list):
        return [item for one in spec for item in select(doc, one, sets)]
    items = []
    for node, keys in walk(doc, spec["path"].split("."), []):
        ctx = {str(i + 1): key for i, key in enumerate(keys)}
        if isinstance(node, dict):
            ctx.update({f"node.{k}": v for k, v in node.items() if isinstance(v, (str, int, float))})
        elif isinstance(node, (str, int, float)):
            ctx["node"] = node
        if not all(holds(doc, cond, ctx) for cond in spec.get("where", [])):
            continue
        for name, path in spec.get("let", {}).items():
            value = get(doc, path, ctx)
            ctx[name] = "" if value is MISSING else value
        ctx["owner"] = fill(spec.get("owner", ""), ctx)
        ctx["group"] = fill(spec.get("group", ""), ctx)
        items.append({"node": node, "value": node, "ctx": ctx})
    return post(items, spec)


def mark(value):
    return json.dumps(value, sort_keys=True)


def check(doc, data):
    found = []
    sets = data["sets"]
    for rule in data["rules"]:
        if not all(holds(doc, cond, {}) for cond in rule.get("when", [])):
            continue
        items = post(select(doc, rule["each"], sets), rule)
        kind, message = rule["kind"], rule["message"]
        if kind in ("exists", "forbid"):
            among = {mark(item["value"]) for item in select(doc, rule["among"], sets)}
            for item in items:
                if (mark(item["value"]) in among) != (kind == "exists"):
                    found.append({"rule": rule["id"], "message": fill(message, item["ctx"])})
        elif kind == "unique":
            allowed = {mark(item["value"]) for item in select(doc, rule.get("except", []), sets)}
            seen = {}
            for item in items:
                key = (item["ctx"]["group"], mark(item["value"]))
                seen.setdefault(key, {"item": item, "owners": set()})["owners"].add(item["ctx"]["owner"])
            for (_, value), entry in seen.items():
                if len(entry["owners"]) > 1 and value not in allowed:
                    found.append({"rule": rule["id"], "message": fill(message, {**entry["item"]["ctx"], "owners": ", ".join(sorted(entry["owners"]))})})
        elif kind == "same":
            for item in items:
                left, right = get(doc, rule["left"], item["ctx"]), get(doc, rule["right"], item["ctx"])
                if left is not MISSING and right is not MISSING and left != right:
                    found.append({"rule": rule["id"], "message": fill(message, item["ctx"])})
        elif kind == "path":
            for item in items:
                if get(doc, item["value"], {}) is MISSING:
                    found.append({"rule": rule["id"], "message": fill(message, item["ctx"])})
        elif kind == "within":
            for item in items:
                value, ctx = item["value"], item["ctx"]
                low = get(doc, rule["min"], ctx) if "min" in rule else MISSING
                high = get(doc, rule["max"], ctx) if "max" in rule else MISSING
                allowed = get(doc, rule["values"], ctx) if "values" in rule else MISSING
                if allowed is not MISSING:
                    wrong = value not in allowed
                elif isinstance(value, (int, float)):
                    wrong = (low is not MISSING and value < low) or (high is not MISSING and value > high)
                else:
                    wrong = False
                if wrong:
                    found.append({"rule": rule["id"], "message": fill(message, ctx)})
    return found
