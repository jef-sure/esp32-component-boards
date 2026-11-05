// The state of the editor: the catalog read, the document open, its checks. Everything it decides about
// the data comes from schema.js, resolve.js, rules.js and pins.js, the same as the tools in Python check.
'use strict';

const FILES = { boards: 'board.json', modules: 'module.json', addons: 'addon.json', platforms: 'platform.json', devices: 'device.json', mcu: 'mcu.json', connectors: 'connector.json' };
const DESCRIPTION = 'DESCRIPTION.md';
const AGENT_KITS = 12; // what a model reads of a list of hundreds
const AGENT_REFUSALS = 8; // the reasons the model gets why boards do not fit
const SHOWN_ANSWERS = ['blocks', 'task', 'outputs', 'board']; // what the canvas holds beside the questions of the top row and of its blocks
const READ_ONLY_GROUPS = new Set(['mcu']); // written by tools/make_mcu.py
const LOADED = ['facts', 'classes', 'libraries', 'inputs']; // what the loader adds, not a field to edit
const ROOT_FIELDS = new Set(['format', 'format_version', 'kind', 'name', 'title', 'description', 'extends', 'notes', 'images', 'origin', 'provides']);
const FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const NAME = /^[a-z][a-z0-9_]*$/; // as a name of the schema: a board of the program is <project>_<board>
// a name of the page from what a project calls itself: handwritten-clock is handwritten_clock
const nameOf = (text) => text.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^[^a-z]+/, '') || 'my_project';
const REPOSITORY_ONLY = /^(\.git|\.gitignore|\.gitattributes|README.*|LICENSE.*)$/i; // a folder with only these is still empty for a new project
const LOCAL_BOARD = (name) => `components/local-boards/boards/${name}/board.json`;
const STUB = (board) => `# board_select.py ${board}`; // the first line of the defaults of a board: the command that makes them
const SKELETON = 'skeleton/files.json'; // the files of a new project, which tools/board_project.py writes too
const TREE_ORDER = ['mcu', 'power', 'buses', 'devices', 'modules', 'connectors', 'shared_pins', 'display_groups', 'price', 'checked'];

const isPlain = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const copied = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const valueAt = (doc, path) => path.reduce((node, key) => (node === undefined || node === null ? undefined : node[key]), doc);
const isCollection = (v) => (isPlain(v) || Array.isArray(v)) && Object.keys(v).length > 0 && Object.values(v).every(isPlain);

// What the page has read, kept out of reactive state: the loader clones entries, which a proxy does not allow.
const COMPONENT_NAME = 'jef-sure/boards';
// until the component is in the registry it comes from git, at the commit of the catalog the page used when the server of the
// model told it, so that a build gives the same tomorrow; main when nothing told it
const COMPONENT_LINES = (version) => `  ${COMPONENT_NAME}:\n    git: https://github.com/jef-sure/esp32-component-boards.git\n    version: ${version}`;
const PREFERENCES = { language: 'boards.language', currency: 'boards.currency', answers: 'boards.answers', project: 'boards.project' }; // keys of localStorage
// a kit and an entry of selection.json are the same when the board and the modules with their counts are
// a block of a role the palette does not have would stop the solver and the canvas
const knownRole = (role) => (library.roles ?? []).some((group) => group.roles.some((item) => item.id === role));
const kitKey = (board, modules) => `${board}+${modules.map((item) => `${item.name}x${item.count ?? 1}`).sort().join(',')}`;
const SELECTION = 'selection.json';
const ISSUES = 'https://github.com/jef-sure/esp32-component-boards/issues/new';

// A form of the repository with its fields filled: the person sends it from their own account, and the page sends nothing.
const reportLink = (fields) => `${ISSUES}?${new URLSearchParams(fields)}`;
const library = { worker: null, asked: 0, sent: null, catalog: null, entries: {}, localFiles: null, schema: null, rules: null, reader: null, loader: null, levels: [], checksOf: null, questions: [], rates: null, solver: null };

// The entries of a tree in the layout of the catalog. What a program has of its own wins over the catalog.
function readTree(files, local) {
    const add = (group, name, path) => {
        const doc = JSON.parse(files[path]);
        library.catalog[group][name] = doc;
        library.entries[`${group}/${name}`] = { key: `${group}/${name}`, group, name, path, doc, text: files[path], local };
    };
    for (const path of Object.keys(files).sort()) {
        const parts = path.split('/');
        if (parts[0] === 'libraries' && parts[4] === 'library.json') {
            const doc = JSON.parse(files[path]);
            add('libraries', `${doc.ecosystem}/${doc.owner}/${doc.name}`, path);
        } else if (parts.length === 3 && FILES[parts[0]] === parts[2]) add(parts[0], parts[1], path);
    }
}

function readCatalog(files) {
    library.catalog = { boards: {}, modules: {}, addons: {}, platforms: {}, devices: {}, mcu: {}, connectors: {}, libraries: {} };
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
    library.judgements = JSON.parse(files['judgements.json'] ?? '{"judgements": []}').judgements;
    library.roles = JSON.parse(files['roles.json']).groups;
    const audits = Object.keys(files).filter((path) => /^libraries\/.*\/audit\.json$/.test(path)).map((path) => [path.split('/').slice(1, 4).join('/'), auditSummary(JSON.parse(files[path]))]);
    library.candidates = { all: JSON.parse(files['libraries/libraries.json'] ?? '{"libraries": {}}').libraries, byChip: JSON.parse(files['libraries/chip_libraries.json'] ?? '{"chips": {}}').chips, audits: Object.fromEntries(audits) };
    library.solver = kitSolver({ catalog, loader: library.loader, questions: library.questions, roles: library.roles, libraries: library.candidates, rates: library.rates.rates, levels: library.levels, judgements: library.judgements, t: (text, ...values) => translate(useEditor().language, text, ...values), checksOf: library.checksOf, pinMap });
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
    if (!kit.wiring.length) return 'None: the board has it all.';
    const rows = kit.wiring.flatMap((module) => module.lines.map((wire) => `| ${module.title} | ${wire.line} | ${wire.to} |`));
    return ['| what | line | to |', '|---|---|---|', ...rows].join('\n');
}

function librariesText(kit) {
    const rows = kit.libraries.map((library) => (library.own
        ? `- \`${library.name}\` ${library.version}, for ${library.devices.join(', ')}: in \`main/idf_component.yml\`, and the program starts it: \`${library.header}\`, \`${library.call}()\`. \`board_bus_get()\` gives its pins, by the name of the device, and the lines of its bus by \`${library.bus}\`.`
        : `- \`${library.name}\` ${library.version}, for ${library.devices.join(', ')}: comes with the board, which starts it.`));
    return rows.join('\n') || 'None.';
}

const dependencyOf = (library) => (library.registry ? `  ${library.name}: "^${library.version}"` : `  ${library.name}:\n    git: ${library.url}`);

// The lines of the skeleton's CMakeLists.txt that read the board and give each board its lock, for a program of its own.
async function cmakeSnippet() {
    const answer = await fetch('skeleton/CMakeLists.txt');
    if (!answer.ok) return null;
    const lines = (await answer.text()).split('\n');
    const first = lines.findIndex((line) => line.startsWith('# BOARD='));
    const lock = lines.findIndex((line) => line.includes('DEPENDENCIES_LOCK'));
    const last = lines.findIndex((line, at) => at > lock && line.trim() === 'endif()');
    return first >= 0 && lock > first && last > lock ? lines.slice(first, last + 1).join('\n') : null;
}

// The section of the README of a project for one of its kits: the board, what it takes, its wires and its libraries.
function kitSection(kit, board) {
    const parts = [`- ${kit.title}`, ...kit.modules.map((item) => `- ${item.count} x ${item.title}, on ${item.on.toUpperCase()}`)];
    const notes = kit.says.filter((line) => line.level === 'do').map((line) => `- ${line.text}`);
    return [`## ${kit.title}: \`${board}\``, '', '### What it takes', '', ...parts, ...notes, '', '### The wires', '', wiresText(kit), '', '### The libraries', '', librariesText(kit)].join('\n');
}

// The files of a new project for its kits, each [kit, board], board the name board_select.py takes: the templates of the
// page, and the smallest program of the component.
async function skeletonOf(chosen, current, name, version) {
    const fill = {
        '@NAME@': name,
        '@TITLE@': name,
        '@KITS@': chosen.map(([kit, board]) => kitSection(kit, board)).join('\n\n'),
        '@CURRENT@': current,
        // what the kits take that the program names itself, once
        '@DEPENDENCIES@': [...new Map(chosen.flatMap(([kit]) => kit.libraries.filter((library) => library.own)).map((library) => [library.name, dependencyOf(library)])).values()].join('\n'),
        '@COMPONENT_VERSION@': version,
    };
    const files = {};
    const list = await fetch(SKELETON);
    if (!list.ok) throw new Error(`${SKELETON}: ${list.status}`);
    for (const [from, to] of (await list.json()).files) {
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
        answers: { outputs: [], blocks: [], ...JSON.parse(localStorage.getItem(PREFERENCES.answers) ?? '{}') },
        language: localStorage.getItem(PREFERENCES.language) || (navigator.language.startsWith('ru') ? 'ru' : 'en'),
        currency: localStorage.getItem(PREFERENCES.currency) || 'EUR',
        projectName: 'my_project',
        plan: null, // what a project is about to get, shown before anything is written
        kits: [],
        solving: false,
        agent: null, // the token of tools/boards_mcp.py, when the page came from it
        talk: [], // what was said with the model
        applied: 0, // the last message of the model whose edits are on the canvas
        installed: null, // the versions of the platforms on the computer, from the server of the model
        description: '', // what the model wrote in the end: a project gets it
        chosen: [], // the kits of the project, in the order they were added: [{ headline, kit }]
        current: null, // the headline of the kit idf.py builds when no preset is named
        wanted: null, // selection.json of a folder opened, until the kits it names are counted
        project: null, // the folder tools/boards_mcp.py may write a project into: { path, name, mode, for_ever }
        modelless: false, // the server came with --serve: no model answers
    }),
    getters: {
        entry(state) {
            state.stamp;
            return state.key ? library.entries[state.key] : null;
        },
        // The roles by groups, with how many parts of the catalog each has.
        palette(state) {
            state.stamp;
            const parts = [...Object.values(library.catalog?.modules ?? {}), ...Object.values(library.catalog?.boards ?? {})];
            const classOf = (device) => [].concat(device.class ?? library.catalog?.devices[device.chip]?.class ?? []);
            const has = (role, device) => Boolean(device.provides?.[role.id]) || (role.needs?.class && classOf(device).includes(role.needs.class));
            const count = (role) => parts.filter((part) => Object.values(part.devices ?? {}).some((device) => has(role, device))).length;
            return (library.roles ?? []).map((group) => ({ ...group, roles: group.roles.map((role) => ({ ...role, count: count(role) })) }));
        },
        // The versions of a platform, the newest first, for the person to fix one.
        versionsOf() {
            return (platform) => Object.keys(library.catalog.platforms?.[platform]?.versions ?? {}).sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        },
        // What a block asks of the data of its part: the questions of its role, and of its variant.
        asksOf() {
            // the fields of its part, and the questions of its class asked of each block
            const classOf = (block) => library.roles.flatMap((group) => group.roles).find((role) => role.id === block.role)?.needs?.class;
            return (block) => library.questions.filter((question) => (question.limit?.field && question.limit.of === block.role && (!question.limit.variant || question.limit.variant === block.variant))
                || (question.asked === 'block' && [].concat(question.limit?.of ?? []).includes(classOf(block)) && (!question.limit.variant || !block.variant || [].concat(question.limit.variant).includes(block.variant))));
        },
        // The parts of the catalog a block can have, for the person to fix one.
        partsOf() {
            return (block) => library.solver?.partsOfBlock(block) ?? [];
        },
        // What a block asks besides its variant: the questions that limit parts of its class.
        settings(state) {
            return (role) => library.questions.filter((question) => question.asked !== 'block' && question.limit?.of && question.limit.of === role.needs?.class && library.solver.holds(question, { ...state.answers, nfc_readers: state.answers.blocks.filter((block) => block.role === role.id).length }));
        },
        readOnly() {
            return !this.entry || READ_ONLY_GROUPS.has(this.entry.group) || Boolean(this.entry.doc.origin); // what is imported is regenerated
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
            return library.questions.filter((question) => question.top && library.solver.holds(question, state.answers));
        },
        currencies(state) {
            state.stamp;
            return library.rates ? [library.rates.base, ...Object.keys(library.rates.rates)] : [];
        },
        saved() {
            return this.plain ? `${catalogJson(this.plain)}\n` : '';
        },
        edited() {
            return (entry) => !READ_ONLY_GROUPS.has(entry.group) && `${catalogJson(entry.doc)}\n` !== entry.text;
        },
    },
    actions: {
        // Beside tools/boards_mcp.py the page tells it what it has, and reads what the model says.
        connect() {
            const hash = new URLSearchParams(location.hash.slice(1));
            this.agent = hash.get('agent');
            if (!this.agent) return;
            // boards_mcp.py --serve: the server of the page and of the writes, with no model behind it
            this.modelless = hash.get('model') === 'none';
            if (!this.modelless) this.listen(0);
            this.agentCall('installed').then((versions) => (this.installed = versions)).catch(() => {});
            // the project of the server, when it has one with a selection.json: the page starts where it was left
            this.agentCall('project').then(async (project) => {
                this.project = project;
                // a new project keeps the name typed for its folder; a program has its own, and selection.json the one its boards took
                if (project.mode === 'create') this.projectName = localStorage.getItem(`${PREFERENCES.project}:${project.path}`) || nameOf(project.name);
                if (project.mode !== 'update') return;
                this.projectName = nameOf(project.name);
                const saved = await this.agentCall('project/file?path=selection.json').catch(() => null);
                if (saved?.text) this.takeSelection(saved.text);
            }).catch(() => {});
        },
        async agentCall(path, options = {}) {
            const answer = await fetch(`/agent/${path}`, { ...options, headers: { Authorization: `Bearer ${this.agent}` } });
            if (!answer.ok) throw new Error(`the server of the model: ${answer.status}`);
            return answer.json();
        },
        async listen(seen) {
            let next = seen;
            try {
                const messages = await this.agentCall(`messages?seen=${seen}`);
                this.talk.push(...messages);
                next = seen + messages.length;
                for (const item of messages) if (item.description) this.description = item.text;
                for (const item of messages) if (item.edits) this.applyEdits(item);
            } catch {
                this.agent = null; // the server is gone: the page works on without it
                return;
            }
            this.listen(next);
        },
        tellAgent() {
            if (!this.agent || this.modelless) return Promise.resolve();
            const kits = this.kits.filter((kit) => kit.fits).slice(0, AGENT_KITS).map((kit) => ({ headline: kit.headline, price: kit.price, imported: kit.imported, says: kit.says }));
            // why the boards that do not fit do not, the most common first: what keeps a selection empty
            const why = new Map();
            for (const kit of this.kits.filter((item) => !item.fits)) {
                const reason = kit.says.find((line) => line.level === 'no')?.text ?? 'no reason given';
                why.set(reason, (why.get(reason) ?? new Set()).add(kit.name));
            }
            const refusals = [...why].map(([reason, boards]) => ({ reason, boards: boards.size })).sort((a, b) => b.boards - a.boards).slice(0, AGENT_REFUSALS);
            return this.agentCall('state', { method: 'POST', body: JSON.stringify({ task: this.answers.task ?? '', blocks: this.answers.blocks, board: this.answers.board ?? null, fits: this.kits.filter((kit) => kit.fits).length, kits, refusals }) }).catch(() => {});
        },
        // what it says goes after what the page has, so the model reads the two in order
        async sayToAgent(text) {
            if (!text.trim()) return;
            await this.tellAgent();
            await this.agentCall('say', { method: 'POST', body: JSON.stringify({ text }) });
        },
        // What the model changes on the canvas, once per message: a block the person fixed stays as it is.
        applyEdits(message) {
            const stored = `boards.applied.${this.agent}`;
            this.applied = Math.max(this.applied, Number(localStorage.getItem(stored) ?? 0));
            if (message.id <= this.applied) return;
            const named = (name) => this.answers.blocks.find((block) => (block.name || block.role) === name && !block.fixed);
            for (const name of message.edits.remove ?? []) {
                const block = named(name);
                if (block) this.answers.blocks.splice(this.answers.blocks.indexOf(block), 1);
            }
            for (const change of message.edits.change ?? []) {
                const block = named(change.name);
                if (block) Object.assign(block, { variant: change.variant ?? block.variant, part: change.part ?? block.part, asks: change.asks ?? block.asks, by: 'model' });
            }
            for (const block of (message.edits.add ?? []).filter((item) => knownRole(item.role))) {
                if (!this.answers.blocks.some((other) => other.fixed && (other.name || other.role) === (block.name || block.role)))
                    this.answers.blocks.push({ role: block.role, variant: block.variant, name: block.name ?? '', part: block.part, asks: block.asks, by: 'model' });
            }
            this.applied = message.id;
            localStorage.setItem(stored, String(message.id));
        },
        addBlock(role) {
            if (knownRole(role)) this.answers.blocks.push({ role, variant: undefined, name: '', by: 'person' });
        },
        // The worker answers the last question only; a page it cannot start on answers by itself.
        startWorker() {
            try {
                library.worker = new Worker('solver_worker.js');
            } catch {
                return;
            }
            library.worker.onmessage = ({ data }) => {
                if (data.id !== library.asked) return;
                this.kits = data.kits;
                this.solving = false;
                this.restoreChosen();
                this.tellAgent();
            };
            library.worker.onerror = () => {
                library.worker = null;
                this.solving = false;
                this.askKits();
            };
        },
        askKits() {
            if (!this.loaded) return;
            // only what the page shows acts: an answer kept from the old questions would add a part nobody sees asked for
            const classes = new Set(this.answers.blocks.map((block) => library.roles.flatMap((group) => group.roles).find((role) => role.id === block.role)?.needs?.class).filter(Boolean));
            const shown = new Set(library.questions.filter((question) => question.top || classes.has(question.limit?.of)).map((question) => question.id));
            const kept = Object.entries(copied(this.answers)).filter(([key]) => SHOWN_ANSWERS.includes(key) || shown.has(key));
            const answers = { ...Object.fromEntries(kept), currency: this.currency, ...(this.installed ? { installed: copied(this.installed) } : {}) };
            if (!library.worker) {
                this.kits = library.solver.solve(answers);
                this.restoreChosen();
                return;
            }
            const message = { id: ++library.asked, answers, language: this.language };
            if (library.sent !== this.stamp) {
                message.documents = { catalog: library.catalog, schema: library.schema, rules: library.rules, questions: library.questions, roles: library.roles, libraries: library.candidates, rates: library.rates.rates, judgements: library.judgements };
                library.sent = this.stamp;
            }
            this.solving = true;
            try {
                library.worker.postMessage(message);
            } catch (error) {
                // what cannot be sent would leave the page counting for ever: it is said, and the page counts by itself
                console.error('postMessage to the solver:', error);
                this.solving = false;
                this.kits = library.solver.solve(answers);
                this.restoreChosen();
            }
        },
        // A kit added to the project, or taken out of it; the first one added is current until another is made so.
        chooseKit(kit) {
            const at = this.chosen.findIndex((item) => item.headline === kit.headline);
            if (at >= 0) this.chosen.splice(at, 1);
            else this.chosen.push({ headline: kit.headline, kit: copied(kit) });
            if (!this.chosen.some((item) => item.headline === this.current)) this.current = this.chosen[0]?.headline ?? null;
        },
        // The kits selection.json of a folder names, found among those counted for its answers: by the board and the modules
        // with their counts, so two kits that differ in the count of a module stay two.
        restoreChosen() {
            if (!this.wanted) return;
            const counted = new Map(this.kits.filter((kit) => kit.fits).map((kit) => [kitKey(kit.name, kit.modules), kit]));
            const found = this.wanted.boards.map((entry) => ({ entry, kit: counted.get(kitKey(entry.base ?? entry.board, entry.modules)) })).filter((item) => item.kit);
            this.chosen = found.map(({ kit }) => ({ headline: kit.headline, kit: copied(kit) }));
            this.current = found.find(({ entry }) => entry.board === this.wanted.current)?.kit.headline ?? this.chosen[0]?.headline ?? null;
            this.wanted = null;
        },
        async start() {
            this.startWorker();
            this.connect();
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
        // selection.json of a project: its answers, and its kits when they are counted again. It is checked by the schema
        // first, so it is taken when the catalog is read.
        takeSelection(selection) {
            if (!library.reader) {
                library.pendingSelection = selection;
                return;
            }
            let saved;
            try {
                saved = JSON.parse(selection);
            } catch (error) {
                this.error = `selection.json: ${error.message}`;
                return;
            }
            // a selection.json before format 3 had one kit at its top, and another form
            const wrong = saved?.format_version === SELECTION_VERSION ? library.reader.errors({ $ref: '#/$defs/selection' }, saved) : [];
            if (wrong.length) {
                this.error = `selection.json: ${wrong[0].path.join('.') || 'the file'}: ${wrong[0].message}: not taken`;
                return;
            }
            // board_project.py writes no blocks: no answers were given
            this.answers = { outputs: [], ...saved.answers, blocks: (saved.answers?.blocks ?? []).filter((block) => knownRole(block.role)) };
            if (saved.currency) this.currency = saved.currency;
            if (saved.name) this.projectName = saved.name;
            this.page = 'select';
            // a selection.json before format 3 had one kit at its top
            this.wanted = saved.boards ? { boards: saved.boards, current: saved.current } : { boards: [{ board: saved.board, modules: saved.modules ?? [] }], current: saved.board };
            this.askKits();
        },
        take({ local, files, selection }) {
            if (selection) this.takeSelection(selection);
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
            // blocks kept by the page from before may name a role the catalog no longer has
            this.answers.blocks = (this.answers.blocks ?? []).filter((block) => knownRole(block.role));
            this.loaded = true;
            this.key = null;
            this.doc = null;
            this.stamp++;
            const first = Object.values(library.entries).find((entry) => entry.group === 'boards');
            if (first) this.open(first.key);
            if (library.pendingSelection) {
                const selection = library.pendingSelection;
                library.pendingSelection = null;
                this.takeSelection(selection);
            }
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
        // What a project gets: the folder decides. Nothing is written here. The kits are one taken from its card, or those
        // added to the project; each gets the name board_select.py takes, a board of the catalog as it is, a kit with modules a
        // board of the program <project>_<board>, and a file of defaults whose first line is the command that makes it. A
        // program with a selection.json keeps its name and its boards: a kit from a card joins them and becomes current.
        async planProject(single) {
            await this.run(async () => {
                // through tools/boards_mcp.py into its folder, or into one picked here
                const bridge = this.project?.mode ? this.project : null;
                let folder = null;
                let mode = bridge?.mode;
                if (!bridge) {
                    const picked = await host.pickProject();
                    folder = picked.folder;
                    mode = picked.names.includes('CMakeLists.txt') ? 'update' : picked.names.every((item) => REPOSITORY_ONLY.test(item)) ? 'create' : null;
                    if (!mode) throw new Error(`${folder.name}: not empty and not a program: nothing is written there`);
                }
                const read = async (path) => (bridge ? (await this.agentCall(`project/file?path=${encodeURIComponent(path)}`).catch(() => null))?.text ?? null : host.readIn(folder, path));
                const saved = mode === 'update' ? JSON.parse((await read(SELECTION)) ?? 'null') : null;
                // a selection.json before format 3 had one kit at its top
                const savedBoards = saved?.boards ?? (saved?.board ? [{ board: saved.board, modules: saved.modules ?? [], libraries: saved.libraries ?? [], says: saved.says ?? [] }] : []);
                const name = saved?.name ?? this.projectName;
                if (!NAME.test(name)) throw new Error('a project name is a lowercase letter, then lowercase letters, digits and _');
                const joins = single && savedBoards.length && !this.chosen.some((item) => item.headline === single.headline);
                if (joins) this.chosen.push({ headline: single.headline, kit: copied(single) });
                if (single && savedBoards.length) this.current = single.headline;
                const kits = single && !savedBoards.length ? [single] : this.chosen.map((item) => item.kit);
                if (!kits.length) throw new Error('no kit in the project: add one from its card');
                // a kit the project has keeps the name of its board; a new one takes none the project has
                const taken = new Set(savedBoards.map((entry) => entry.board));
                const chosen = kits.map((kit) => {
                    const had = savedBoards.find((entry) => kitKey(entry.base ?? entry.board, entry.modules) === kitKey(kit.name, kit.modules));
                    if (had) return [kit, had.board];
                    const base = kit.project ? `${name}_${kit.name}` : kit.name;
                    let board = base;
                    for (let n = 2; taken.has(board); ++n) board = `${base}_${n}`;
                    taken.add(board);
                    if (kit.project && library.catalog.boards[board]) throw new Error(`the catalog has a board ${board}: give the project another name`);
                    return [kit, board];
                });
                const currentKit = (savedBoards.length ? null : single) ?? this.chosen.find((item) => item.headline === this.current)?.kit ?? kits[0];
                const current = chosen.find(([kit]) => kit === currentKit)?.[1] ?? chosen[0][1];
                const files = {};
                for (const [kit, board] of chosen) {
                    if (kit.project) files[LOCAL_BOARD(board)] = `${catalogJson({ ...kit.project, name: board, title: kit.modules.length ? `${kit.title} with ${kit.modules.map((item) => item.title).join(', ')}` : kit.title })}\n`;
                    files[`sdkconfig.defaults.${board}`] = `${STUB(board)}\n# The page wrote this line only: board_select.py --again . makes the defaults of the board.\n`;
                }
                if (mode === 'create') Object.assign(files, await skeletonOf(chosen, current, name, this.installed?.component ?? 'main'));
                if (this.description) files[DESCRIPTION] = `${this.description.trim()}\n`;
                const selection = library.solver.selectionOf(chosen.map(([kit, board]) => ({ kit, board })), current, this.kits, copied(this.answers), this.currency, name);
                // the boards the project had stay where they were, those planned now in their place, the new ones after them
                const fresh = new Map(selection.boards.map((entry) => [entry.board, entry]));
                selection.boards = [...savedBoards.map((entry) => fresh.get(entry.board) ?? entry), ...selection.boards.filter((entry) => !savedBoards.some((had) => had.board === entry.board))];
                files[SELECTION] = `${JSON.stringify(selection, null, 4)}\n`;
                const rows = [];
                if (bridge) {
                    // the server says what lies there and what board_select.py --again makes after these files
                    const planned = await this.agentCall('project/plan', { method: 'POST', body: JSON.stringify({ files }) });
                    if (planned.failed) throw new Error(`board_select.py --again: ${planned.failed}`);
                    for (const [path, state] of Object.entries({ ...planned.files, ...planned.made })) {
                        rows.push({ path, text: files[path] ?? null, old: state.state === 'changed' ? await read(path) : null, state: state.state, why: state.why, digest: state.digest, made: path in planned.made, replace: false });
                    }
                } else {
                    for (const [path, text] of Object.entries(files)) {
                        const old = await host.readIn(folder, path);
                        // a file of defaults made from its first line is that file
                        const made = path.startsWith('sdkconfig.defaults.') && old?.startsWith(`${text.split('\n')[0]}\n`);
                        const state = old === null ? 'new' : old === text || made ? 'same' : path === SELECTION || path === DESCRIPTION || path.startsWith('components/local-boards/') ? 'changes' : 'kept';
                        rows.push({ path, text, old, state, replace: false });
                    }
                }
                const manifest = mode === 'update' ? await read('main/idf_component.yml') : null;
                // a program of its own also needs the CMake that reads the boards and main naming the component: shown, not written
                const project = mode === 'update' ? await read('CMakeLists.txt') : null;
                const main = mode === 'update' ? await read('main/CMakeLists.txt') : null;
                const cmakeLines = mode === 'update' && !project?.includes('sdkconfig.defaults.${BOARD}') ? await cmakeSnippet() : null;
                const requiresLine = mode === 'update' && main && !main.includes('jef-sure__boards') ? 'PRIV_REQUIRES jef-sure__boards' : null;
                const own = [...new Map(kits.flatMap((kit) => kit.libraries.filter((item) => item.own)).map((item) => [item.name, item])).values()];
                this.plan = { folder: folder && Vue.markRaw(folder), bridge: Boolean(bridge), folderName: bridge ? bridge.path : folder.name, mode, rows, files, current, boards: chosen.map(([, board]) => board), written: null,
                    allow: bridge && !bridge.for_ever ? 'once' : null, cmakeLines, requiresLine,
                    manifestLines: mode === 'update' ? [...(manifest?.includes(COMPONENT_NAME) ? [] : [COMPONENT_LINES(this.installed?.component ?? 'main')]), ...own.filter((item) => !manifest?.includes(item.name)).map(dependencyOf)] : [] };
            });
        },
        // Writes what is new and what was ticked. Nothing else is touched and nothing is removed.
        async writeProject() {
            await this.run(async () => {
                const plan = this.plan;
                if (plan.bridge) {
                    // a tick names what the list showed: a file changed again since is refused by the server
                    const replace = Object.fromEntries(plan.rows.filter((row) => row.state === 'changed' && row.replace).map((row) => [row.path, row.digest]));
                    const done = await this.agentCall('project/write', { method: 'POST', body: JSON.stringify({ files: plan.files, replace, ...(plan.allow ? { allow: plan.allow } : {}) }) });
                    if (done.failed) throw new Error(`board_select.py --again: ${done.failed}`);
                    const refused = Object.keys(done.refused ?? {});
                    if (refused.length) throw new Error(`nothing is written: ${refused.join(', ')} changed after the list was made or may not be written; make the list again`);
                    if (plan.allow === 'for ever') this.project.for_ever = true;
                    plan.written = done.written;
                    return;
                }
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
