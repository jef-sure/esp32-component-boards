// The engine of rules.json, in JS for the editor. rules.py is the same engine for the generator.
'use strict';
const MISSING = Symbol('missing');
const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const mark = (v) => JSON.stringify(sorted(v));
function sorted(v) {
    if (Array.isArray(v)) return v.map(sorted);
    if (isObject(v)) return Object.keys(v).sort().reduce((o, k) => ((o[k] = sorted(v[k])), o), {});
    return v;
}
const fill = (text, ctx) => text.replace(/\{([\w.]+)\}/g, (m, k) => (k in ctx ? String(ctx[k]) : m));

function get(doc, path, ctx) {
    let node = doc;
    for (const raw of path.split('.')) {
        const token = fill(raw, ctx);
        if (isObject(node) && token in node) node = node[token];
        else if (Array.isArray(node) && /^\d+$/.test(token) && +token < node.length) node = node[+token];
        else return MISSING;
    }
    return node;
}

function* walk(node, parts, keys) {
    if (!parts.length) {
        yield [node, keys];
        return;
    }
    const [head, ...rest] = parts;
    if (head === '*') {
        const pairs = isObject(node) ? Object.entries(node) : Array.isArray(node) ? node.map((v, i) => [String(i), v]) : [];
        for (const [key, child] of pairs) yield* walk(child, rest, [...keys, key]);
    } else if (isObject(node) && head in node) yield* walk(node[head], rest, keys);
    else if (Array.isArray(node) && /^\d+$/.test(head) && +head < node.length) yield* walk(node[+head], rest, keys);
}

function holds(doc, cond, ctx) {
    const value = 'text' in cond ? fill(cond.text, ctx) : get(doc, cond.path, ctx);
    if (value === MISSING) return false;
    if ('is' in cond) return value === cond.is;
    if ('not' in cond) return value !== cond.not;
    if ('has' in cond) return Array.isArray(value) ? value.includes(cond.has) : value === cond.has;
    if ('in' in cond) return cond.in.includes(value);
    return true;
}

function post(items, spec) {
    const out = [];
    for (const item of items) {
        const node = item.node;
        if ('with' in spec && !(isObject(node) && spec.with in node)) continue;
        if ('without' in spec && isObject(node) && spec.without in node) continue;
        let value = item.value;
        if ('take' in spec) {
            if (!(isObject(node) && spec.take in node)) continue;
            value = node[spec.take];
        }
        if ('as' in spec) value = fill(spec.as, item.ctx);
        if ('strip' in spec) value = value.replace(new RegExp(spec.strip), '');
        out.push({ ...item, value, ctx: { ...item.ctx, value } });
    }
    return out;
}

function select(doc, spec, sets) {
    if (typeof spec === 'string') return select(doc, sets[spec], sets);
    if (Array.isArray(spec)) return spec.flatMap((one) => select(doc, one, sets));
    const items = [];
    for (const [node, keys] of walk(doc, spec.path.split('.'), [])) {
        const ctx = {};
        keys.forEach((key, i) => (ctx[String(i + 1)] = key));
        if (isObject(node)) {
            for (const [k, v] of Object.entries(node)) if (['string', 'number'].includes(typeof v)) ctx[`node.${k}`] = v;
        } else if (['string', 'number'].includes(typeof node)) ctx.node = node;
        if (!(spec.where || []).every((cond) => holds(doc, cond, ctx))) continue;
        for (const [name, path] of Object.entries(spec.let || {})) {
            const value = get(doc, path, ctx);
            ctx[name] = value === MISSING ? '' : value;
        }
        ctx.owner = fill(spec.owner || '', ctx);
        ctx.group = fill(spec.group || '', ctx);
        items.push({ node, value: node, ctx });
    }
    return post(items, spec);
}

function check(doc, data) {
    const found = [];
    const sets = data.sets;
    for (const rule of data.rules) {
        if (!(rule.when || []).every((cond) => holds(doc, cond, {}))) continue;
        const items = post(select(doc, rule.each, sets), rule);
        const report = (ctx) => found.push({ rule: rule.id, message: fill(rule.message, ctx) });
        if (rule.kind === 'exists' || rule.kind === 'forbid') {
            const among = new Set(select(doc, rule.among, sets).map((item) => mark(item.value)));
            for (const item of items) if (among.has(mark(item.value)) !== (rule.kind === 'exists')) report(item.ctx);
        } else if (rule.kind === 'unique') {
            const allowed = new Set(select(doc, rule.except || [], sets).map((item) => mark(item.value)));
            const seen = new Map();
            for (const item of items) {
                const key = `${item.ctx.group}\u0000${mark(item.value)}`;
                if (!seen.has(key)) seen.set(key, { item, owners: new Set(), value: mark(item.value) });
                seen.get(key).owners.add(item.ctx.owner);
            }
            for (const entry of seen.values())
                if (entry.owners.size > 1 && !allowed.has(entry.value)) report({ ...entry.item.ctx, owners: [...entry.owners].sort().join(', ') });
        } else if (rule.kind === 'same') {
            for (const item of items) {
                const left = get(doc, rule.left, item.ctx), right = get(doc, rule.right, item.ctx);
                if (left !== MISSING && right !== MISSING && mark(left) !== mark(right)) report(item.ctx);
            }
        } else if (rule.kind === 'path') {
            for (const item of items) if (get(doc, item.value, {}) === MISSING) report(item.ctx);
        } else if (rule.kind === 'apart') {
            const groups = new Map();
            for (const item of items) groups.set(item.ctx.group, [...(groups.get(item.ctx.group) || []), item]);
            for (const group of groups.values()) {
                group.sort((a, b) => a.value[0] - b.value[0] || a.value[1] - b.value[1] || (a.ctx.owner < b.ctx.owner ? -1 : a.ctx.owner > b.ctx.owner ? 1 : 0));
                group.slice(1).forEach((high, i) => {
                    const low = group[i];
                    if (high.value[0] < low.value[1]) report({ ...low.ctx, owners: `${low.ctx.owner}, ${high.ctx.owner}` });
                });
            }
        } else if (rule.kind === 'earlier') {
            const at = new Map(select(doc, rule.among, sets).map((item) => [mark(item.value), +item.ctx['1']]));
            for (const item of items) if (!(at.get(mark(item.value)) < +item.ctx['1'])) report(item.ctx);
        } else if (rule.kind === 'within') {
            for (const item of items) {
                const { value, ctx } = item;
                const low = 'min' in rule ? get(doc, rule.min, ctx) : MISSING;
                const high = 'max' in rule ? get(doc, rule.max, ctx) : MISSING;
                const allowed = 'values' in rule ? get(doc, rule.values, ctx) : MISSING;
                let wrong = false;
                if (allowed !== MISSING) wrong = Array.isArray(allowed) ? !allowed.includes(value) : !(value in allowed);
                else if (typeof value === 'number') wrong = (low !== MISSING && value < low) || (high !== MISSING && value > high);
                if (wrong) report(ctx);
            }
        }
    }
    return found;
}

if (typeof module !== 'undefined') module.exports = { check };
