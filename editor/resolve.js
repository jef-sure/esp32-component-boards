// The loader of tools/resolve.py, in JS for the editor: the layers merged by JSON Merge Patch, the
// catalog under each device, the lines in one form. tools/check_format.py compares the two.
// catalog is {boards, modules, devices, mcu, connectors, libraries}: entries by name, libraries by id.
'use strict';

function boardResolver(catalog) {
    const NOT_LINES = new Set(['hz', 'lanes', 'lane_mbps', 'phy_ldo_chan', 'phy_ldo_mv', 'baud', 'data']);
    const TYPE_FIELDS = ['class', 'maker', 'part', 'compat', 'draw', 'pins', 'config', 'controls', 'provides', 'start', 'firmware', 'ways'];
    const LIBRARY_HISTORY = ['license', 'chips', 'transports', 'interfaces', 'groups', 'values'];
    const FIRMWARE_HISTORY = ['config', 'controls', 'provides'];
    const REFERENCES = new Set(['over', 'via', 'left', 'right', 'after', 'devices', 'feeds', 'from', 'through', 'name', 'logic']); // fields of a module that name its parts
    const REVISION_HISTORY = ['limits', 'provides', 'controls', 'sdkconfig'];
    const MODULE_FACTS = ['maker', 'part', 'revision', 'mcu', 'price', 'tariff']; // what a board keeps of a module beside its parts

    class Refused extends Error {}

    const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
    const has = (object, key) => Object.hasOwn(object, key);
    const picked = (object, keys) => Object.fromEntries(keys.filter((key) => has(object, key)).map((key) => [key, object[key]]));
    const without = (object, drop) => Object.fromEntries(Object.entries(object).filter(([key]) => !drop(key)));
    const mapped = (object, change) => Object.fromEntries(Object.entries(object).map(([key, value]) => [key, change(value, key)]));
    const isFilled = (v) => (isObject(v) ? Object.keys(v).length > 0 : Array.isArray(v) ? v.length > 0 : Boolean(v));
    const listed = (value) => (Array.isArray(value) ? value : value === undefined || value === null ? [] : [value]);
    const line = (value) => (Number.isInteger(value) ? { gpio: value } : value);

    function load(kind, name) {
        const entries = catalog[kind] || {};
        if (!has(entries, name)) throw new Refused(`the catalog has no ${kind} entry ${name}`);
        return structuredClone(entries[name]);
    }

    function merge(base, patch) {
        if (!isObject(patch)) return structuredClone(patch);
        const out = isObject(base) ? structuredClone(base) : {};
        for (const [key, value] of Object.entries(patch)) {
            if (value === null) delete out[key];
            else out[key] = merge(out[key], value);
        }
        return out;
    }

    function runs(text) {
        return (text.match(/\d+|\D+/g) || []).map((run) => (/^\d+$/.test(run) ? [0, Number(run)] : [1, run]));
    }

    // A version in a form that compares: parts by value (in hex for that scheme), 1.0 as 1.0.0, a pre-release below its release, a revision above it.
    function versionKey(version, scheme = 'decimal') {
        const [plain, revision = ''] = version.replace(/^[vV]+/, '').split('+')[0].split(/~(.*)/s);
        const [text, pre = ''] = plain.split(/-(.*)/s);
        const number = scheme === 'hex' ? /^[0-9a-fA-F]+$/ : /^[0-9]+$/;
        const parts = text.split('.').map((part) => (number.test(part) ? [0, parseInt(part, scheme === 'hex' ? 16 : 10)] : [1, part]));
        while (parts.length && parts.at(-1)[0] === 0 && parts.at(-1)[1] === 0) parts.pop();
        return [parts, pre ? 0 : 1, runs(pre), parseInt(revision || '0', 10)];
    }

    function compareKeys(a, b) {
        if (!Array.isArray(a)) return a < b ? -1 : a > b ? 1 : 0;
        for (let i = 0; i < Math.min(a.length, b.length); i++) {
            const order = compareKeys(a[i], b[i]);
            if (order) return order;
        }
        return a.length - b.length;
    }

    const compareVersions = (older, newer, scheme) => compareKeys(versionKey(older, scheme), versionKey(newer, scheme));

    // doc as it was in a version: versions has the version described and the history, applied from the newest step down.
    function atVersion(doc, versions, version, fields) {
        const scheme = versions.scheme || 'decimal';
        if (compareVersions(version, versions.described, scheme) > 0) throw new Refused(`only ${versions.described} and older are described, not ${version}`);
        const steps = [...(versions.history || [])].sort((a, b) => compareVersions(b.before, a.before, scheme));
        for (const step of steps) {
            if (compareVersions(version, step.before, scheme) < 0) doc = merge(doc, picked(step, fields));
        }
        return doc;
    }

    const libraryAt = (record, version) => atVersion(record, record, version, LIBRARY_HISTORY);

    // The sdkconfig lines of a chip of a revision: what the revision takes, held down by what the board says.
    function chipSettings(mcu, revision) {
        const facts = load('mcu', mcu.target);
        if (!has(facts, 'revisions')) return [];
        const chosen = revision || mcu.revision;
        const at = atVersion(facts, facts.revisions, chosen, REVISION_HISTORY);
        const [major, minor] = chosen.split('.').map(Number);
        const option = Math.max(...facts.revisions.options.filter((number) => number <= major * 100 + minor));
        const lines = [...at.sdkconfig.lines, `${at.sdkconfig.revision.replace('{value}', option)}=y`];
        for (const name of ['psram_mhz', 'cpu_mhz']) {
            if (name !== 'psram_mhz' || mcu.psram_mb) {
                const limit = at.limits[name];
                lines.push(`${at.sdkconfig[name].replace('{value}', Math.min(mcu[name] ?? limit, limit))}=y`);
            }
        }
        return lines;
    }

    // The libraries of the catalog that have this chip, by id: the entry of the chip in each.
    function librariesOf(chip) {
        const found = {};
        for (const [id, record] of Object.entries(catalog.libraries || {})) {
            if (has(record.chips || {}, chip)) found[id] = record.chips[chip];
        }
        return found;
    }

    function chain(doc) {
        if (!doc.extends) return doc;
        const own = without(doc, (key) => key === 'extends');
        const base = chain(load(doc.kind === 'module' ? 'modules' : 'boards', doc.extends));
        for (const entry of Object.values(base.checked || {})) {
            if (!has(entry, 'on_board')) entry.on_board = base.name;
        }
        return merge(base, own);
    }

    // The chips a device can be: one, or those it tries at start.
    const chipsOf = (device) => (has(device, 'chip') ? [device.chip] : device.chip_try || []);

    function applyType(device) {
        if (!has(device, 'chip')) {
            chipsOf(device).forEach((chip) => load('devices', chip));
            return device;
        }
        const entry = load('devices', device.chip);
        let base = picked(entry, TYPE_FIELDS);
        if (has(device, 'variant')) {
            const variants = entry.variants || {};
            if (!has(variants, device.variant)) throw new Refused(`${device.chip} has no variant ${device.variant}`);
            base = merge(base, variants[device.variant]);
        }
        if (has(device, 'firmware_version')) {
            if (!has(base.firmware || {}, 'described')) throw new Refused(`${device.chip} has no firmware versions in the catalog`);
            base = atVersion(base, base.firmware, device.firmware_version, FIRMWARE_HISTORY);
        }
        const out = merge(base, without(device, (key) => key === 'on'));
        const on = device.on || {};
        const defaults = merge(entry.on || {}, without(on, (key) => key.includes('.')));
        const concrete = without(on, (key) => !key.includes('.'));
        const notRequired = (value) => without(value, (key) => key === 'required');
        const wired = mapped(concrete, (value, key) => merge(notRequired(defaults[key.split('.')[0]] || {}), value));
        for (const connection of Object.values(wired)) {
            if (has(connection, 'address')) delete connection.address_try;
        }
        out.on = isFilled(wired) ? wired : mapped(on, notRequired);
        out.wants = mapped(entry.on || {}, (value) => ({ required: Boolean(value.required), ...(has(value, 'lines') ? { lines: value.lines } : {}) }));
        const libraries = librariesOf(device.chip);
        if (!has(out, 'library') && Object.keys(libraries).length === 1) out.library = Object.keys(libraries)[0];
        if (has(libraries, out.library)) {
            const record = catalog.libraries[out.library];
            out.library_at = out.library_version ?? record.described;
            const chips = libraryAt(record, out.library_at).chips;
            delete libraries[out.library];
            if (has(chips, device.chip)) libraries[out.library] = chips[device.chip];
        }
        out.libraries = libraries;
        return out;
    }

    function normal(device) {
        device.classes = Array.isArray(device.class) ? [...device.class] : device.class ? [device.class] : [];
        delete device.class;
        if (has(device, 'pins')) device.pins = mapped(device.pins, line);
        for (const connection of Object.values(device.on || {})) {
            if (has(connection, 'cs')) connection.cs = line(connection.cs);
        }
        const config = device.config || {};
        if (isFilled(config.buttons)) config.buttons = mapped(config.buttons, line);
        if (isObject(config.divider) && has(config.divider, 'switch')) config.divider.switch = line(config.divider.switch);
        return device;
    }

    function named(value, names) {
        if (Array.isArray(value)) return value.map((item) => named(item, names));
        if (isObject(value)) return renamed(value, names);
        return names.has(value) ? names.get(value) : value;
    }

    // A part of a module with the names it refers to as they are on the board.
    function renamed(value, names) {
        if (isObject(value)) return mapped(value, (item, key) => (REFERENCES.has(key) ? named(item, names) : renamed(item, names)));
        if (Array.isArray(value)) return value.map((item) => renamed(item, names));
        return value;
    }

    // The on of a part with each kind of bus it has, its own or its chip's, on the bus of the board it joins.
    function joined(device, wiring) {
        if (!isFilled(wiring)) return device;
        const own = device.on || {};
        const kinds = new Set(Object.keys(own));
        for (const chip of chipsOf(device)) Object.keys(load('devices', chip).on || {}).forEach((kind) => kinds.add(kind));
        const taken = Object.fromEntries(Object.keys(wiring).map((bus) => [bus.split('.')[0], bus]));
        const on = without(own, (key) => has(taken, key));
        for (const [kind, bus] of Object.entries(taken)) {
            if (kinds.has(kind)) on[bus] = merge(own[kind] || {}, wiring[bus]);
        }
        return { ...device, on };
    }

    // The steps a module takes from its board, on the lines the wiring names.
    function supplied(steps, supply, name) {
        const open = new Set(steps.filter((step) => step.source === 'connector').map((step) => step.name));
        for (const step of supply.keys()) if (!open.has(step)) throw new Refused(`${name}: no step ${step} to feed`);
        return steps.map((step) => {
            if (!supply.has(step.name)) return step;
            const { source, ...rest } = step;
            return { ...rest, from: supply.get(step.name) };
        });
    }

    function useModule(doc, name, use) {
        const module = chain(load('modules', use.module));
        addModules(module);
        const parts = module.devices;
        const partNames = Object.keys(parts);
        if (partNames.length > 1 && (has(use, 'pins') || has(use, 'config') || Object.values(use.on || {}).some(isFilled))) {
            throw new Refused(`${name}: a module of several parts takes its wiring by part, in devices: ${partNames.join(', ')}`);
        }
        const steps = (module.power || []).filter((step) => has(step, 'name')).map((step) => step.name);
        const own = [...partNames, ...steps, ...(has(module, 'mcu') ? ['mcu'] : [])];
        const names = new Map(own.map((part) => [part, `${name}_${part}`]));
        for (const part of Object.keys(use.devices || {})) {
            if (!has(parts, part)) throw new Refused(`${name}: the module ${use.module} has no part ${part}`);
        }
        for (const [part, template] of Object.entries(parts)) {
            const device = joined(renamed(template, names), use.on);
            const wiring = picked(use, ['config', 'pins']);
            doc.devices[names.get(part)] = merge(merge(device, wiring), (use.devices || {})[part] || {});
        }
        for (const field of ['display_groups', 'shared_pins', 'connectors']) {
            for (const [key, entry] of Object.entries(module[field] || {})) {
                doc[field] = doc[field] || {};
                doc[field][`${name}_${key}`] = renamed(entry, names);
            }
        }
        const supply = new Map(Object.entries(use.supply || {}).map(([step, line]) => [names.get(step) ?? step, line]));
        doc.power = [...(doc.power || []), ...supplied(renamed(module.power || [], names), supply, name)];
        if (!doc.power.length) delete doc.power;
        return { module: use.module, title: module.title, ...picked(module, MODULE_FACTS) };
    }

    function addModules(doc) {
        doc.devices = doc.devices || {};
        const uses = doc.modules || {};
        delete doc.modules;
        doc.modules = mapped(uses, (use, name) => useModule(doc, name, use));
    }

    // The devices a layer takes away with null, and those its bases took.
    function removed(doc) {
        const names = new Set(Object.entries(doc.devices || {}).filter(([, device]) => device === null).map(([name]) => name));
        if (!doc.extends) return names;
        return new Set([...names, ...removed(load(doc.kind === 'module' ? 'modules' : 'boards', doc.extends))]);
    }

    // A step in one form: its line, inputs that each name a step and the devices on the way from it, feeds without the devices a layer removed.
    function powerStep(step, gone) {
        if (has(step, 'line')) step.line = line(step.line);
        if (has(step, 'from')) {
            const inputs = listed(step.from).map((item) => (typeof item === 'string' ? { name: item } : item));
            const common = listed(step.through);
            delete step.from;
            delete step.through;
            step.inputs = inputs.map((item) => ({ ...item, through: [...listed(item.through), ...common] }));
        }
        if (has(step, 'feeds')) step.feeds = step.feeds.filter((name) => !gone.has(name));
        return step;
    }

    // The facts of a connector whose contacts a standard fixes.
    function connectorOf(name, connector) {
        connector.facts = load('connectors', connector.of);
        if (connector.pins.length !== connector.facts.pins.length) {
            throw new Refused(`connector ${name}: ${connector.of} has ${connector.facts.pins.length} contacts, not ${connector.pins.length}`);
        }
    }

    function resolve(doc, overlays = []) {
        const fixed = ['kind', 'name', 'title', 'extends'];
        let out = chain(structuredClone(doc));
        for (const layer of overlays) out = merge(out, without(layer, (key) => fixed.includes(key)));
        if (out.kind === 'project') out.kind = 'board';
        addModules(out);
        out.devices = mapped(out.devices, (device) => normal(applyType(device)));
        const gone = new Set([doc, ...overlays].flatMap((layer) => [...removed(layer)]).filter((name) => !has(out.devices, name)));
        if (has(out, 'power')) out.power = out.power.map((step) => powerStep(step, gone));
        for (const [name, connector] of Object.entries(out.connectors || {})) {
            if (has(connector, 'of')) connectorOf(name, connector);
        }
        if (out.kind === 'board') {
            for (const buses of Object.values(out.buses || {})) {
                for (const bus of Object.values(buses)) {
                    for (const [key, value] of Object.entries(bus)) {
                        if (!NOT_LINES.has(key)) bus[key] = line(value);
                    }
                    if (has(bus, 'data')) bus.data = bus.data.map(line);
                }
            }
            for (const group of Object.values(out.shared_pins || {})) group.line = line(group.line);
            for (const connector of Object.values(out.connectors || {})) connector.pins = connector.pins.map(line);
            if (has(out, 'mcu')) {
                let facts = load('mcu', out.mcu.target);
                if (has(out.mcu, 'revision') && has(facts, 'revisions')) facts = atVersion(facts, facts.revisions, out.mcu.revision, REVISION_HISTORY);
                out.mcu.facts = facts;
                const provides = mapped(facts.provides || {}, () => ({ by: ['mcu'] }));
                if (out.mcu.psram_mb) provides.psram = { by: ['mcu'] };
                for (const [name, device] of Object.entries(out.devices)) {
                    for (const capability of Object.keys(device.provides || {})) {
                        provides[capability] = provides[capability] || { by: [] };
                        provides[capability].by.push(name);
                    }
                }
                out.provides = provides;
            }
        }
        return out;
    }

    // What a path stands on: the best confirmed level of the entries that cover it, and those pending or refuted.
    function trust(board, path, order) {
        const covering = Object.entries(board.checked || {}).filter(
            ([, entry]) => !has(entry, 'covers') || entry.covers.some((covered) => path === covered || path.startsWith(`${covered}.`))
        );
        const best = (levels) => levels.reduce((low, level) => (order.indexOf(level) < order.indexOf(low) ? level : low));
        const result = (entry) => entry.result ?? 'confirmed';
        const confirmed = covering.filter(([, entry]) => result(entry) === 'confirmed' && !has(entry, 'on_board')).map(([, entry]) => entry.level);
        const inherited = covering.filter(([, entry]) => has(entry, 'on_board')).map(([, entry]) => entry.level);
        const open = covering.filter(([, entry]) => result(entry) !== 'confirmed').map(([name, entry]) => `${name}: ${entry.result}`);
        return [confirmed.length ? best(confirmed) : inherited.length ? `only inherited ${best(inherited)}` : 'nothing', open];
    }

    return { Refused, load, merge, chain, resolve, compareVersions, atVersion, libraryAt, chipSettings, librariesOf, chipsOf, applyType, trust };
}

// JSON of the catalog, as dump of tools/resolve.py writes it: what fits a line stays on one, the rest opens up.
const CATALOG_LINE = 120;

function catalogLine(value) {
    if (Array.isArray(value)) return `[${value.map(catalogLine).join(', ')}]`;
    if (value !== null && typeof value === 'object') return `{${Object.entries(value).map(([key, item]) => `${JSON.stringify(key)}: ${catalogLine(item)}`).join(', ')}}`;
    return JSON.stringify(value);
}

function catalogJson(value, indent = 0, used = 0) {
    const one = catalogLine(value);
    const opens = value !== null && typeof value === 'object' && Object.keys(value).length > 0;
    if (!opens || (indent && indent + used + [...one].length <= CATALOG_LINE)) return one;
    const pad = ' '.repeat(indent + 4);
    const end = ' '.repeat(indent);
    if (Array.isArray(value)) return `[\n${value.map((item) => pad + catalogJson(item, indent + 4)).join(',\n')}\n${end}]`;
    const body = Object.entries(value).map(([key, item]) => `${pad}${JSON.stringify(key)}: ${catalogJson(item, indent + 4, [...key].length + 4)}`);
    return `{\n${body.join(',\n')}\n${end}}`;
}

if (typeof module !== 'undefined') module.exports = { boardResolver, catalogJson };
