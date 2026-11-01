// The state of the editor: the catalog read, the document open, its checks. Everything it decides about
// the data comes from schema.js, resolve.js, rules.js and pins.js, the same as the tools in Python check.
'use strict';

const FILES = { boards: 'board.json', modules: 'module.json', devices: 'device.json', mcu: 'mcu.json', connectors: 'connector.json' };
const READ_ONLY_GROUPS = new Set(['mcu']); // written by tools/make_mcu.py
const LOADED = ['facts', 'classes', 'libraries', 'inputs']; // what the loader adds, not a field to edit
const ROOT_FIELDS = new Set(['format', 'format_version', 'kind', 'name', 'title', 'description', 'extends', 'notes', 'images', 'origin', 'provides']);
const FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const TREE_ORDER = ['mcu', 'power', 'buses', 'devices', 'modules', 'connectors', 'shared_pins', 'display_groups', 'price', 'checked'];

const isPlain = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const copied = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const valueAt = (doc, path) => path.reduce((node, key) => (node === undefined || node === null ? undefined : node[key]), doc);
const dropNulls = (v) => (isPlain(v) ? Object.fromEntries(Object.entries(v).filter(([, item]) => item !== null).map(([key, item]) => [key, dropNulls(item)])) : v);
const isCollection = (v) => (isPlain(v) || Array.isArray(v)) && Object.keys(v).length > 0 && Object.values(v).every(isPlain);

// What the page has read, kept out of reactive state: the loader clones entries, which a proxy does not allow.
const library = { catalog: null, entries: {}, localFiles: null, schema: null, rules: null, reader: null, resolvedReader: null, loader: null, levels: [] };

// The entries of a tree in the layout of the catalog. What a program has of its own wins over the catalog.
function readTree(files, local) {
    const add = (group, name, path) => {
        const doc = JSON.parse(files[path]);
        library.catalog[group][name] = doc;
        library.entries[`${group}/${name}`] = { key: `${group}/${name}`, group, name, path, doc, text: files[path], local };
    };
    for (const path of Object.keys(files).sort()) {
        const parts = path.split('/');
        if (parts[0] === 'libraries' && parts.length === 5) {
            const doc = JSON.parse(files[path]);
            add('libraries', `${doc.ecosystem}/${doc.owner}/${doc.name}`, path);
        } else if (parts.length === 3 && FILES[parts[0]] === parts[2]) add(parts[0], parts[1], path);
    }
}

function readCatalog(files) {
    library.catalog = { boards: {}, modules: {}, devices: {}, mcu: {}, connectors: {}, libraries: {} };
    library.entries = {};
    readTree(files, false);
    const catalog = library.catalog;
    library.schema = JSON.parse(files['format.schema.json']);
    library.rules = JSON.parse(files['rules.json']);
    library.reader = schemaReader(library.schema);
    library.resolvedReader = schemaReader({ $defs: library.schema.$defs });
    library.loader = boardResolver(catalog);
    library.levels = library.schema.$defs.level.enum;
}

function checksOf(doc) {
    const problems = [];
    const say = (stage, text, path = null) => problems.push({ stage, text, path });
    const { reader, resolvedReader, schema, rules, loader } = library;
    for (const error of reader.errors(schema, doc.extends ? dropNulls(doc) : doc)) say('schema', `${error.path.join('.') || 'the file'}: ${error.message}`, error.path);
    if (!['board', 'project', 'module'].includes(doc.kind)) {
        for (const found of check(doc, { ...rules, rules: rules.rules.filter((rule) => rule.in_files) })) say('rule', found.message);
        return { problems, resolved: null, layers: doc };
    }
    let resolved = null;
    let layers = doc;
    try {
        layers = loader.chain(structuredClone(doc));
        resolved = loader.resolve(doc);
    } catch (error) {
        say('resolve', error.message);
    }
    if (resolved) {
        for (const error of resolvedReader.errors({ $ref: '#/$defs/resolved' }, resolved)) say('resolved', `${error.path.join('.') || 'the board'}: ${error.message}`, error.path);
        try {
            for (const found of check(resolved, rules)) say('rule', found.message);
            for (const text of pinProblems(resolved)) say('pins', text);
        } catch (error) {
            say('rule', error.message);
        }
    }
    return { problems, resolved, layers };
}

function labelOf(key, value) {
    if (!isPlain(value)) return { label: String(key), note: '' };
    const label = typeof key === 'number' ? value.name ?? value.source ?? `#${key}` : key;
    const note = [value.chip, value.part, value.module, value.class, value.level, value.shop, value.target].find((item) => typeof item === 'string');
    return { label: String(label), note: note ?? '' };
}

function treeOf(value, layers, path) {
    const rank = (key) => (TREE_ORDER.includes(key) ? TREE_ORDER.indexOf(key) : TREE_ORDER.length);
    return Object.entries(value)
        .filter(([key]) => path.length || !ROOT_FIELDS.has(key))
        .filter(([key, item]) => (isPlain(item) || Array.isArray(item)) && !LOADED.includes(key) && Object.keys(item).length)
        .filter(([, item]) => path.length || isPlain(item) || isCollection(item))
        .sort(([a], [b]) => (path.length ? 0 : rank(a) - rank(b)))
        .map(([key, item]) => {
            const place = [...path, Array.isArray(value) ? +key : key];
            const id = place.join('\u0000');
            // the loader writes a line as an object: the layers tell a bus of lines from a list of entries
            const opens = isCollection(valueAt(layers, place) ?? item);
            return { id, path: place, ...labelOf(place.at(-1), item), made: valueAt(layers, place) === undefined, children: opens ? treeOf(item, layers, place) : [] };
        });
}

const useEditor = Pinia.defineStore('editor', {
    state: () => ({
        loaded: false,
        error: '',
        note: '',
        key: null,
        doc: null,
        selected: [],
        view: 'card',
        filter: '',
        freeOnly: false,
        jsonResolved: false,
        hasLocal: false, // a program's local-boards is open: what is new goes there
        stamp: 0, // changes when something outside the reactive state does
    }),
    getters: {
        entry(state) {
            state.stamp;
            return state.key ? library.entries[state.key] : null;
        },
        readOnly() {
            return !this.entry || READ_ONLY_GROUPS.has(this.entry.group);
        },
        groups(state) {
            state.stamp;
            const all = Object.values(library.entries);
            const words = state.filter.toLowerCase();
            const shown = (entry) => !words || `${entry.name} ${entry.doc.title ?? ''}`.toLowerCase().includes(words);
            const of = (title, test) => ({ title, entries: all.filter((entry) => test(entry) && shown(entry)) });
            return [
                of('Local boards', (entry) => entry.local),
                of('Boards', (entry) => !entry.local && entry.group === 'boards'),
                of('Modules', (entry) => !entry.local && entry.group === 'modules'),
                of('Devices', (entry) => !entry.local && entry.group === 'devices'),
                of('Connectors', (entry) => !entry.local && entry.group === 'connectors'),
                of('Libraries', (entry) => !entry.local && entry.group === 'libraries'),
                of('Chips', (entry) => !entry.local && entry.group === 'mcu'),
            ].filter((group) => group.entries.length);
        },
        plain(state) {
            return copied(state.doc);
        },
        checks() {
            return this.plain ? checksOf(this.plain) : { problems: [], resolved: null, layers: null };
        },
        shown() {
            return this.checks.resolved ?? this.plain;
        },
        tree() {
            return this.shown ? treeOf(this.shown, this.checks.layers, []) : [];
        },
        pins() {
            const board = this.checks.resolved;
            return board?.mcu?.facts?.gpio ? pinMap(board) : null;
        },
        saved() {
            return this.plain ? `${catalogJson(this.plain)}\n` : '';
        },
        edited() {
            return (entry) => !READ_ONLY_GROUPS.has(entry.group) && `${catalogJson(entry.doc)}\n` !== entry.text;
        },
    },
    actions: {
        async start() {
            await this.run(async () => {
                const files = await host.fetchCatalog();
                if (files) this.load(files);
            });
        },
        async openFolder() {
            await this.run(async () => this.take(await host.openFolder()));
        },
        async openPicked(list) {
            await this.run(async () => this.take(await host.readPicked(list)));
        },
        take({ local, files }) {
            if (!local) {
                this.load(files);
                return;
            }
            if (!this.loaded) throw new Error('these boards stand on the catalog: open the folder of this repository first, or serve the page from it');
            library.localFiles = files;
            readTree(files, true);
            this.hasLocal = true;
            this.stamp++;
            const first = Object.values(library.entries).find((entry) => entry.local && entry.group === 'boards');
            if (first) this.open(first.key);
        },
        async run(work) {
            this.error = '';
            try {
                await work();
            } catch (error) {
                if (error.name !== 'AbortError') this.error = error.message;
            }
        },
        load(files) {
            readCatalog(files);
            if (library.localFiles) readTree(library.localFiles, true);
            this.loaded = true;
            this.key = null;
            this.doc = null;
            this.stamp++;
            const first = Object.values(library.entries).find((entry) => entry.group === 'boards');
            if (first) this.open(first.key);
        },
        open(key) {
            this.key = key;
            this.doc = copied(library.entries[key].doc);
            this.selected = [];
            this.note = '';
            this.stamp++;
        },
        select(path) {
            this.selected = path;
            this.view = 'card';
        },
        changed() {
            const entry = this.entry;
            entry.doc = this.plain;
            library.catalog[entry.group][entry.name] = entry.doc;
            this.note = '';
            this.stamp++;
        },
        // undefined takes the field out of this file. A layer holds null to take out what it inherits.
        setValue(path, value) {
            let node = this.doc;
            path.slice(0, -1).forEach((key, i) => {
                if (node[key] === undefined || node[key] === null) {
                    const merged = valueAt(this.checks.layers, path.slice(0, i + 1));
                    // a layer replaces a list whole, so it starts from the whole list
                    node[key] = Array.isArray(merged) ? copied(merged) : typeof path[i + 1] === 'number' ? [] : {};
                }
                node = node[key];
            });
            const last = path.at(-1);
            if (value !== undefined) node[last] = value;
            else if (Array.isArray(node)) node.splice(last, 1);
            else delete node[last];
            this.changed();
        },
        // A field a layer takes out of what it inherits stays in the file as null.
        removeInherited(path) {
            this.setValue(path, null);
        },
        // Inherits it again, and takes out what stood only for that null.
        inheritAgain(path) {
            this.setValue(path, undefined);
            for (let at = path.length - 1; at > 0; --at) {
                const place = path.slice(0, at);
                const left = valueAt(this.doc, place);
                if (!isPlain(left) || Object.keys(left).length) break;
                this.setValue(place, undefined);
            }
        },
        async save() {
            await this.run(async () => {
                const entry = this.entry;
                const written = await host.write(entry.path, this.saved, entry.local);
                entry.text = this.saved;
                this.stamp++;
                const then = entry.local ? 'python3 tools/board_select.py' : 'python3 tools/boards_gen.py --all';
                this.note = written ? `${entry.path} written. Now ${then}` : `${entry.path} downloaded: put it in place, then ${then}`;
            });
        },
        create(group, kind, name, title, base) {
            const file = FILES[group];
            const key = `${group}/${name}`;
            if (library.entries[key]) {
                this.error = `${key} is there already`;
                return;
            }
            const doc = { ...FORMAT, kind, name, title, ...(base ? { extends: base } : {}), ...(kind === 'board' ? { mcu: { target: 'esp32s3' } } : {}) };
            library.catalog[group][name] = doc;
            library.entries[key] = { key, group, name, path: `${group}/${name}/${file}`, doc, text: '', local: this.hasLocal };
            this.error = '';
            this.open(key);
        },
    },
});
