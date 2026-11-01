// The state of the editor: the catalog read, the document open, its checks. Everything it decides about
// the data comes from schema.js, resolve.js, rules.js and pins.js, the same as the tools in Python check.
'use strict';

const FILES = { boards: 'board.json', modules: 'module.json', devices: 'device.json', mcu: 'mcu.json', connectors: 'connector.json' };
const READ_ONLY_GROUPS = new Set(['mcu']); // written by tools/make_mcu.py
const LOADED = ['facts', 'classes', 'libraries', 'inputs']; // what the loader adds, not a field to edit
const ROOT_FIELDS = new Set(['format', 'format_version', 'kind', 'name', 'title', 'description', 'extends', 'notes', 'images', 'origin', 'provides']);
const FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const NAME = /^[a-z0-9_]+$/;
const REPOSITORY_ONLY = /^(\.git|\.gitignore|\.gitattributes|README.*|LICENSE.*)$/i; // a folder with only these is still empty for a new project
const LOCAL_BOARD = (name) => `components/local-boards/boards/${name}/board.json`;
const COMPONENT_LINE = 'jef-sure/boards';
const SKELETON = [
    ['skeleton/CMakeLists.txt', 'CMakeLists.txt'],
    ['skeleton/gitignore', '.gitignore'],
    ['skeleton/README.md', 'README.md'],
    ['skeleton/main/CMakeLists.txt', 'main/CMakeLists.txt'],
    ['skeleton/main/idf_component.yml', 'main/idf_component.yml'],
    ['../examples/hello_board/main/main.c', 'main/main.c'],
    ['../examples/hello_board/sdkconfig.defaults', 'sdkconfig.defaults'],
];
const TREE_ORDER = ['mcu', 'power', 'buses', 'devices', 'modules', 'connectors', 'shared_pins', 'display_groups', 'price', 'checked'];

const isPlain = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const copied = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const valueAt = (doc, path) => path.reduce((node, key) => (node === undefined || node === null ? undefined : node[key]), doc);
const isCollection = (v) => (isPlain(v) || Array.isArray(v)) && Object.keys(v).length > 0 && Object.values(v).every(isPlain);

// What the page has read, kept out of reactive state: the loader clones entries, which a proxy does not allow.
const PREFERENCES = { language: 'boards.language', currency: 'boards.currency' }; // keys of localStorage
const library = { catalog: null, entries: {}, localFiles: null, schema: null, rules: null, reader: null, loader: null, levels: [], checksOf: null, questions: [], rates: null, solver: null };

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
    library.loader = boardResolver(catalog);
    library.levels = library.schema.$defs.level.enum;
    library.checksOf = documentChecks({ schema: library.schema, rules: library.rules, loader: library.loader, schemaReader, check, pinProblems });
    library.questions = JSON.parse(files['questions.json']).questions;
    library.rates = JSON.parse(files['rates.json']);
    library.solver = kitSolver({ catalog, loader: library.loader, questions: library.questions, rates: library.rates.rates, t: (text, ...values) => translate(useEditor().language, text, ...values), checksOf: library.checksOf, pinMap });
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

function wiresText(kit) {
    if (!kit.wires.length) return 'None: the board has it all.';
    const rows = kit.wires.map((wire) => `| ${wire.what} | ${wire.line} | ${wire.pin} |`);
    return ['| what | line | GPIO |', '|---|---|---|', ...rows].join('\n');
}

// The files of a new project: the templates of the page, and the smallest program of the component.
async function skeletonOf(kit, name, board) {
    const parts = [`- ${kit.title}`, ...kit.modules.map((item) => `- ${item.count} x ${item.title}, on ${item.on.toUpperCase()}`)];
    const notes = kit.says.filter((line) => line.level === 'do').map((line) => `- ${line.text}`);
    const fill = {
        '@NAME@': name,
        '@TITLE@': name,
        '@BOARD_TITLE@': kit.title,
        '@BOARD@': board,
        '@PARTS@': [...parts, ...notes].join('\n'),
        '@WIRES@': wiresText(kit),
    };
    const files = {};
    for (const [from, to] of SKELETON) {
        const answer = await fetch(from);
        if (!answer.ok) throw new Error(`${from}: ${answer.status}`);
        files[to] = Object.entries(fill).reduce((text, [mark, value]) => text.replaceAll(mark, value), await answer.text());
    }
    return files;
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
        page: 'select',
        answers: { outputs: [] },
        language: localStorage.getItem(PREFERENCES.language) || (navigator.language.startsWith('ru') ? 'ru' : 'en'),
        currency: localStorage.getItem(PREFERENCES.currency) || 'EUR',
        projectName: 'my_project',
        plan: null, // what a project is about to get, shown before anything is written
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
            return this.plain ? library.checksOf(this.plain) : { problems: [], resolved: null, layers: null };
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
        questions(state) {
            state.stamp;
            return library.questions.filter((question) => !question.top && library.solver.holds(question, state.answers));
        },
        topQuestions(state) {
            state.stamp;
            return library.questions.filter((question) => question.top);
        },
        currencies(state) {
            state.stamp;
            return library.rates ? [library.rates.base, ...Object.keys(library.rates.rates)] : [];
        },
        kits(state) {
            state.stamp;
            state.language;
            return state.loaded ? library.solver.solve({ ...copied(state.answers), currency: state.currency }) : [];
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
        // What a project gets: the folder decides. Nothing is written here.
        async planProject(kit) {
            await this.run(async () => {
                const name = this.projectName;
                if (!NAME.test(name)) throw new Error('a project name is lowercase letters, digits and _');
                if (kit.project && library.catalog.boards[name]) throw new Error(`the catalog has a board ${name}: give the project another name`);
                const { folder, names } = await host.pickProject();
                const mode = names.includes('CMakeLists.txt') ? 'update' : names.every((item) => REPOSITORY_ONLY.test(item)) ? 'create' : null;
                if (!mode) throw new Error(`${folder.name}: not empty and not a program: nothing is written there`);
                const files = {};
                const board = kit.project ? name : kit.name;
                if (kit.project) files[LOCAL_BOARD(name)] = `${catalogJson({ ...kit.project, name, title: `${kit.title} with ${kit.modules.map((item) => item.title).join(', ')}` })}\n`;
                if (mode === 'create') Object.assign(files, await skeletonOf(kit, name, board));
                const rows = [];
                for (const [path, text] of Object.entries(files)) {
                    const old = await host.readIn(folder, path);
                    const state = old === null ? 'new' : old === text ? 'same' : path === LOCAL_BOARD(name) ? 'changes' : 'kept';
                    rows.push({ path, text, old, state, replace: false });
                }
                const manifest = mode === 'update' ? await host.readIn(folder, 'main/idf_component.yml') : null;
                this.plan = { folder: Vue.markRaw(folder), folderName: folder.name, mode, rows, board, written: null, needsComponent: mode === 'update' && !(manifest ?? '').includes(COMPONENT_LINE) };
            });
        },
        // Writes what is new and what was ticked. Nothing else is touched and nothing is removed.
        async writeProject() {
            await this.run(async () => {
                const plan = this.plan;
                const chosen = plan.rows.filter((row) => row.state === 'new' || (row.state === 'changes' && row.replace));
                // the folder may have changed since the list was made: a file that appeared is somebody's
                for (const row of chosen) {
                    if ((await host.readIn(plan.folder, row.path)) !== row.old) throw new Error(`${row.path} changed after the list was made: nothing is written, make the list again`);
                }
                for (const row of chosen) {
                    await host.writeIn(plan.folder, row.path, row.text);
                    if ((await host.readIn(plan.folder, row.path)) !== row.text) throw new Error(`${row.path}: what lies there is not what was written`);
                }
                plan.written = chosen.map((row) => row.path);
            });
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
