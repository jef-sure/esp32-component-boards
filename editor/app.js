// The page: the documents of the catalog, the tree of the one open, the card of a node, its pins.
// No build step: the templates are compiled by the Vue of vendor/.
'use strict';

const { createApp, computed, ref } = Vue;
const SHORT_LINE = 60; // an object this short stays on one line of the card
const PLACES_OPEN = 3; // nested fields open this deep
const MADE_BY_THE_LOADER = 'Made by the loader'; // how the schema marks a field no file writes

const oneLine = (value) => catalogLine(value);
const isShort = (value) => !isPlain(value) && !Array.isArray(value) ? true : oneLine(value).length <= SHORT_LINE && !Object.values(value).some((item) => isPlain(item) && Object.keys(item).length > 2);

// The line of a card: a value of a field, in the control its schema asks for.
const FieldValue = {
    props: ['path', 'schemas', 'locked'],
    setup(props) {
        const store = useEditor();
        const own = computed(() => valueAt(store.doc, props.path));
        const shown = computed(() => own.value ?? valueAt(store.shown, props.path));
        const shape = computed(() => library.reader.shape(props.schemas));
        // config.libraries.<library>.panel of a display: the panels that library names for the chip and the size, to try one
        const offered = computed(() => {
            const path = props.path;
            const n = path.length;
            if (n < 5 || path[n - 1] !== 'panel' || path[n - 3] !== 'libraries' || path[n - 4] !== 'config') return null;
            const device = valueAt(store.shown, path.slice(0, n - 4));
            const panel = device?.config?.panel;
            const rows = (library.catalog.libraries[path[n - 2]]?.chips?.[device?.chip]?.panels ?? []).filter(
                (row) => !panel || (row.width === panel.width && row.height === panel.height),
            );
            return rows.length ? rows : null;
        });
        const kind = computed(() => {
            const { values, types } = shape.value;
            if (offered.value) return 'offered';
            if (values) return 'choice';
            if (types.length === 1 && types[0] === 'boolean') return 'flag';
            if (types.length === 1 && (types[0] === 'integer' || types[0] === 'number')) return 'number';
            if (types.length === 1 && types[0] === 'string') return 'text';
            return 'json';
        });
        const failed = ref(false);
        const text = computed(() => (shown.value === undefined ? '' : typeof shown.value === 'string' && kind.value !== 'json' ? shown.value : oneLine(shown.value)));
        const set = (value) => store.setValue(props.path, value === '' ? undefined : value);
        function setJson(event) {
            const typed = event.target.value.trim();
            if (typed === '') return set(undefined);
            try {
                failed.value = false;
                set(JSON.parse(typed));
            } catch {
                failed.value = true;
            }
        }
        return { own, shown, shape, offered, kind, failed, text, set, setJson };
    },
    template: `
        <select v-if="kind === 'choice'" :value="shown" :disabled="locked" :class="{ inherited: own === undefined }" @change="set(JSON.parse($event.target.selectedOptions[0].dataset.value))">
            <option v-if="shown === undefined" :value="undefined"></option>
            <option v-for="choice in shape.values" :key="choice" :value="choice" :data-value="JSON.stringify(choice)">{{ choice }}</option>
        </select>
        <select v-else-if="kind === 'offered'" :value="shown ?? ''" :disabled="locked" :class="{ inherited: own === undefined }" @change="set($event.target.value)">
            <option value="">{{ offered[0].value }} (the first of the size)</option>
            <option v-for="row in offered" :key="row.value" :value="row.value" :title="row.notes">{{ row.notes ? row.value + ': ' + row.notes : row.value }}</option>
        </select>
        <input v-else-if="kind === 'flag'" type="checkbox" :checked="shown === true" :disabled="locked" @change="set($event.target.checked)">
        <input v-else-if="kind === 'number'" type="number" step="any" :value="shown" :disabled="locked" :class="{ inherited: own === undefined }"
            @change="set($event.target.value === '' ? '' : Number($event.target.value))">
        <input v-else-if="kind === 'text'" type="text" :value="shown" :disabled="locked" :class="{ inherited: own === undefined }" @change="set($event.target.value)">
        <input v-else type="text" class="json" :value="text" :disabled="locked" :class="{ inherited: own === undefined, wrong: failed }" @change="setJson">
    `,
};

// The fields of a place: those of the file, those it inherits, and what the schema still allows.
const FieldList = {
    name: 'FieldList',
    components: { FieldValue },
    props: ['path', 'depth', 'locked'],
    setup(props) {
        const store = useEditor();
        const value = computed(() => valueAt(store.shown, props.path));
        const own = computed(() => valueAt(store.doc, props.path));
        const schemas = computed(() => library.reader.at(store.shown, props.path));
        const known = computed(() => library.reader.fields(schemas.value));
        const isList = computed(() => Array.isArray(value.value));
        const keys = computed(() => (value.value === null || value.value === undefined ? [] : Object.keys(value.value).map((key) => (isList.value ? +key : key))));
        const hidden = (key) => LOADED.includes(key) || (!props.path.length && ['format', 'format_version'].includes(key));
        const rows = computed(() =>
            keys.value.filter((key) => !hidden(key)).map((key) => {
                const path = [...props.path, key];
                const item = value.value[key];
                const below = library.reader.inForce(library.reader.below(schemas.value, key), item);
                const open = (isPlain(item) || Array.isArray(item)) && !isShort(item);
                const inherited = valueAt(store.doc, path) === undefined;
                return { key, path, item, below, open, inherited, description: library.reader.shape(below).description, required: known.value[key]?.required };
            }).filter((row) => !row.description.startsWith(MADE_BY_THE_LOADER)).sort((a, b) => a.open - b.open)
        );
        const describes = (key) => library.reader.shape(library.reader.inForce(known.value[key].schemas)).description;
        const free = computed(() => Object.keys(known.value).filter((key) => !keys.value.includes(key) && !hidden(key) && !describes(key).startsWith(MADE_BY_THE_LOADER)).sort());
        const added = ref('');
        const addable = computed(() => schemas.value.some((schema) => isPlain(schema.additionalProperties)));
        const entryName = ref('');
        const removed = computed(() => (isPlain(own.value) ? Object.keys(own.value).filter((key) => own.value[key] === null) : []));
        const layered = computed(() => Boolean(store.doc.extends));
        const listOfObjects = computed(() => isList.value && value.value.every(isPlain));
        function addField() {
            const key = added.value;
            added.value = '';
            const shape = library.reader.shape(library.reader.inForce(known.value[key].schemas));
            const empty = shape.types.includes('object') ? {} : shape.types.includes('array') ? [] : shape.values ? shape.values[0] : shape.types.includes('boolean') ? false : shape.types.includes('string') ? '' : 0;
            store.setValue([...props.path, key], empty);
        }
        function addEntry() {
            if (entryName.value) store.setValue([...props.path, entryName.value], {});
            entryName.value = '';
        }
        return { store, own, rows, free, added, addField, addable, entryName, addEntry, removed, layered, listOfObjects };
    },
    template: `
        <div class="fields">
            <template v-for="row in rows" :key="row.key">
                <details v-if="row.open" class="nested" :open="depth < PLACES_OPEN">
                    <summary><span class="name" :title="row.description">{{ typeof row.key === 'number' ? '#' + row.key : row.key }}</span>
                        <span v-if="row.inherited" class="tag">inherited</span>
                        <button v-if="row.inherited && layered && !locked" class="drop" title="take it out here, the base keeps it" @click.prevent="store.removeInherited(row.path)">×</button>
                        <button v-if="!row.inherited && !locked" class="drop" title="take it out of this file" @click.prevent="store.setValue(row.path, undefined)">×</button></summary>
                    <field-list :path="row.path" :depth="depth + 1" :locked="locked"></field-list>
                </details>
                <div v-else class="field">
                    <label class="name" :title="row.description">{{ row.key }}<span v-if="row.required" class="required">*</span></label>
                    <div class="control">
                        <field-value :path="row.path" :schemas="row.below" :locked="locked"></field-value>
                        <button v-if="!row.inherited && !locked" class="drop" title="take it out of this file" @click="store.setValue(row.path, undefined)">×</button>
                        <span v-if="row.inherited" class="tag">inherited</span>
                        <button v-if="row.inherited && layered && !locked" class="drop" title="take it out here, the base keeps it" @click="store.removeInherited(row.path)">×</button>
                    </div>
                    <div v-if="row.description" class="hint">{{ row.description }}</div>
                </div>
            </template>
            <div v-for="key in removed" :key="key" class="field">
                <label class="name removed">{{ key }}</label>
                <div class="control"><span class="hint">taken out here</span>
                    <button v-if="!locked" class="drop" title="inherit it again" @click="store.inheritAgain([...path, key])">↺</button></div>
            </div>
            <div v-if="!locked && free.length" class="more">
                <select v-model="added" @change="addField"><option value="">add a field…</option><option v-for="key in free" :key="key">{{ key }}</option></select>
            </div>
            <div v-if="!locked && addable" class="more">
                <input type="text" v-model="entryName" placeholder="name of a new entry" @keyup.enter="addEntry"><button @click="addEntry">add</button>
            </div>
            <div v-if="!locked && listOfObjects" class="more">
                <button @click="store.setValue([...path, rows.length], {})">add an item</button>
            </div>
        </div>
    `,
};

const TreeItem = {
    name: 'TreeItem',
    props: ['node'],
    setup(props) {
        const store = useEditor();
        const here = computed(() => store.selected.join('\u0000') === props.node.id);
        return { store, here };
    },
    template: `
        <li>
            <button class="node" :class="{ here, made: node.made }" :title="node.made ? 'from a module or the catalog: change it there' : ''" @click="store.select(node.path)">
                {{ node.label }} <span v-if="node.note" class="note">{{ node.note }}</span>
            </button>
            <ul v-if="node.children.length"><tree-item v-for="child in node.children" :key="child.id" :node="child"></tree-item></ul>
        </li>
    `,
};

const NodeCard = {
    components: { FieldList },
    setup() {
        const store = useEditor();
        const path = computed(() => store.selected);
        const made = computed(() => path.value.length > 0 && valueAt(store.checks.layers, path.value) === undefined);
        const locked = computed(() => store.readOnly || made.value);
        const title = computed(() => (path.value.length ? path.value.join(' / ') : store.plain?.title ?? store.entry?.name));
        const trust = computed(() => {
            const board = store.checks.resolved;
            if (!board || !path.value.length) return null;
            const [level, open] = library.loader.trust(board, path.value.join('.'), library.levels);
            return { level, open };
        });
        const notes = computed(() => [].concat(valueAt(store.shown, [...path.value, 'notes']) ?? []));
        return { store, path, made, locked, title, trust, notes };
    },
    template: `
        <section class="card">
            <h2>{{ title }}</h2>
            <p v-if="trust" class="trust"><span class="tag" :class="trust.level">{{ trust.level }}</span>
                <span v-for="line in trust.open" :key="line" class="tag open">{{ line }}</span></p>
            <p v-if="made" class="locked">This comes from a module or the catalog: change it there, or through <code>modules</code> of this file.</p>
            <p v-if="store.readOnly" class="locked">Written by a tool, read only here.</p>
            <ul v-if="notes.length" class="notes"><li v-for="line in notes" :key="line">{{ line }}</li></ul>
            <field-list :path="path" :depth="0" :locked="locked"></field-list>
        </section>
    `,
};

const PinMap = {
    setup() {
        const store = useEditor();
        const rows = computed(() =>
            Object.entries(store.pins || {})
                .map(([pin, entry]) => ({ pin, ...entry }))
                .filter((row) => !store.freeOnly || row.state === 'free')
        );
        const counts = computed(() => {
            const all = Object.values(store.pins || {});
            return { free: all.filter((row) => row.state === 'free').length, all: all.length };
        });
        // a pin's owner is devices.<name>.<line> or a bus: the tree has the first two places
        function goTo(owner) {
            const [first, second, third] = owner.split('.');
            const shown = store.shown;
            if (shown.devices?.[first]) store.select(['devices', first]);
            else if (shown.buses?.[first]?.[second]) store.select(['buses', first, second]);
            else if (first === 'power') store.select(['power']);
            return third;
        }
        return { store, rows, counts, goTo };
    },
    template: `
        <section class="card">
            <h2>Pins</h2>
            <p v-if="!store.pins">Nothing to show: the document has no chip.</p>
            <template v-else>
                <p><label><input type="checkbox" v-model="store.freeOnly"> only free</label> <span class="hint">{{ counts.free }} free of {{ counts.all }}</span></p>
                <table class="pins">
                    <thead><tr><th>GPIO</th><th>who has it</th><th>connector</th><th>can do</th><th>notes</th></tr></thead>
                    <tbody>
                        <tr v-for="row in rows" :key="row.pin" :class="row.state">
                            <td>{{ row.pin }}</td>
                            <td><button v-for="owner in row.owners" :key="owner" class="link" @click="goTo(owner)">{{ owner }}</button>
                                <span v-if="row.free_while" class="hint"> free while {{ row.free_while }}</span></td>
                            <td>{{ row.connectors.join(', ') }}</td>
                            <td>{{ (row.analog || []).join(', ') }}</td>
                            <td><span v-if="row.strapping" class="tag">strapping</span> <span v-if="row.input_only" class="tag">input only</span></td>
                        </tr>
                    </tbody>
                </table>
            </template>
        </section>
    `,
};

const NewDocument = {
    setup() {
        const store = useEditor();
        const kind = ref('board');
        const name = ref('');
        const title = ref('');
        const base = ref('');
        const boards = computed(() => {
            store.stamp;
            return Object.values(library.entries).filter((entry) => entry.group === 'boards').map((entry) => entry.name);
        });
        function make() {
            store.create(kind.value === 'module' ? 'modules' : 'boards', kind.value, name.value, title.value || name.value, kind.value === 'project' ? base.value : '');
            name.value = title.value = '';
        }
        const ready = computed(() => /^[a-z0-9_]+$/.test(name.value) && (kind.value !== 'project' || base.value));
        return { store, kind, name, title, base, boards, make, ready };
    },
    template: `
        <details class="new"><summary>new…</summary>
            <p class="hint">{{ store.hasLocal ? 'It goes into local-boards.' : 'It goes into the catalog. A board of your own goes into a program: open its folder.' }}</p>
            <select v-model="kind"><option v-if="store.hasLocal">project</option><option>board</option><option>module</option></select>
            <input type="text" v-model="name" placeholder="name, as cyd_s028r">
            <input type="text" v-model="title" placeholder="title">
            <select v-if="kind === 'project'" v-model="base"><option value="">on the board…</option><option v-for="board in boards" :key="board">{{ board }}</option></select>
            <button :disabled="!ready" @click="make">create</button>
        </details>
    `,
};

const MARKS = { yes: '✓', no: '✗', unknown: '?', do: '→', note: '·' };
const FROM_BOARD = '@board'; // the value of Part for the part of the board a block came from
const BOARD_PART = '@board:'; // the value of Part for a part of the selected board, before its device
const BOARDS_SHOWN = 10; // the cards shown at first: a hundred boards fit when little is asked

// Which question a board and its modules answer: the first screen.
const numberOf = (event, question) => {
    if (event.target.value === '') return undefined;
    const value = Number(event.target.value);
    return question?.type === 'count' ? Math.min(Math.max(Math.floor(value), 0), question.max ?? value) : value;
};

// A card of a board: the kit the solver put first for it, and the others of the board behind it
const KitCard = {
    props: ['kit', 'rest', 'helpers'],
    setup(props) {
        return { ...props.helpers };
    },
    template: `
        <article class="kit">
            <p v-if="inProject.has(kit.name)" class="hint">{{ t('a board of the project: counted as one you have') }}</p>
            <img v-if="kit.picture" class="picture" :src="host.pictureSrc(kit.picture)" :alt="kit.title">
            <h3>{{ kit.title }}</h3>
            <p v-if="kit.modules.length || kit.addons?.length" class="added">+ {{ partsOf(kit) }}</p>
            <p class="note">{{ money(kit.price, kit.cost) }}<template v-if="kit.modules.length || kit.addons?.length"> · {{ t('Parts bought one by one: the solver put them together.') }}</template></p>
            <div v-if="kit.modules.some((module) => module.picture)" class="parts">
                <figure v-for="module in kit.modules.filter((item) => item.picture)" :key="module.name" :title="module.credit">
                    <img :src="host.pictureSrc(module.picture)" :alt="module.title"><figcaption>{{ module.title }}</figcaption></figure>
                <p class="hint credit">{{ t('Pictures of parts: hold the pointer on one for its source.') }}</p>
            </div>
            <ul><li v-for="line in firstSays(kit)" :key="line.text" :class="line.level" :title="line.basis ?? (line.judgement ? line.judgement + ' (catalog/judgements.json)' : null)"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul>
            <details v-if="laterSays(kit).length" class="later"><summary>{{ t('steps and notes ({0})', laterSays(kit).length) }}</summary>
                <ul><li v-for="line in laterSays(kit)" :key="line.text" :class="line.level" :title="line.basis ?? (line.judgement ? line.judgement + ' (catalog/judgements.json)' : null)"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul>
            </details>
            <p v-if="kit.price.unpriced.length" class="hint">{{ t('Know a price?') }}
                <a v-for="item in kit.price.unpriced" :key="item.item" target="_blank" rel="noopener" :href="priceLink(item.item)">{{ item.title }}</a></p>
            <details v-if="kit.held?.length" open><summary>{{ t('on the board') }}</summary>
                <div v-for="part in kit.held" :key="part.device" class="wiring"><b>{{ part.block }}: {{ part.title }}</b> {{ part.buses.join(', ') }}
                    <span v-for="wire in part.lines" :key="wire.line"><code>{{ wire.line }}</code> → {{ wire.to }}</span>
                    <span v-for="item in part.set" :key="item.control">{{ t('{0} = {1}, set by a {2} on the board', item.control, item.start, item.how) }}</span></div>
                <p class="hint">{{ t('Wired on the board: nothing to wire, and these pins are taken.') }}</p>
            </details>
            <details v-if="kit.wiring.length"><summary>{{ t('the wires') }}</summary>
                <div v-for="module in kit.wiring" :key="module.use" class="wiring"><b>{{ module.title }}</b>
                    <span v-for="wire in module.lines" :key="wire.line"><code>{{ wire.line }}</code> → {{ wire.to }}&nbsp;<span v-if="wire.where" class="hint">· {{ wire.where }}</span></span></div>
            </details>
            <button v-if="kit.writable" :class="{ on: chosenHas(kit) }" :title="t('A board the program is built for: a project may have several.')" @click="store.chooseKit(kit)">{{ t(chosenHas(kit) ? 'in the project' : 'add to the project') }}</button>
            <button v-if="canWrite && kit.writable && !store.chosen.length" @click="store.planProject(kit)">{{ t('make a project…') }}</button>
            <label v-if="canWrite && kit.writable && !store.chosen.length && store.hasDisplay(kit)" class="hint" :title="t('The computer shows the display of the board in a window: Linux with SDL2.')">
                <input type="checkbox" :checked="store.withComputer" @change="store.setComputer($event.target.checked)"> {{ t('add the build on the computer') }}</label>
            <button v-if="store.answers.board !== kit.name" :title="t('Pin this board: the solver and the model try no other.')" @click="store.answers.board = kit.name">{{ t('pin this board') }}</button>
            <span v-if="kit.imported" class="hint">{{ t('imported: no project until this board is in the catalog') }}</span>
            <span v-else-if="!kit.writable" class="hint">{{ t('The page writes projects for ESP-IDF only for now.') }}</span>
            <span v-else-if="!canWrite" class="hint">{{ t('Writing a project into a folder takes Chromium, or the page opened from tools/boards_mcp.py.') }}</span>
            <details v-if="rest.length" class="more"><summary>{{ t('{0} more on this board', rest.length) }}</summary>
                <p v-for="other in rest" :key="other.headline">+ {{ partsOf(other) || t('nothing more') }} <span class="note">{{ money(other.price, other.cost) }}</span>
                    <button v-if="other.writable" :class="{ on: chosenHas(other) }" @click="store.chooseKit(other)">{{ t(chosenHas(other) ? 'in the project' : 'add to the project') }}</button>
                    <button v-if="canWrite && other.writable && !store.chosen.length" @click="store.planProject(other)">{{ t('make a project…') }}</button></p>
            </details>
        </article>
    `,
};

const SelectPage = {
    components: { KitCard },
    setup() {
        const store = useEditor();
        const fit = computed(() => store.kits.filter((kit) => kit.fits));
        const others = computed(() => store.kits.filter((kit) => !kit.fits));
        // One card a board: the kits come sorted, so its first is its best, and the rest wait behind it.
        const inProject = computed(() => new Set(store.projectBoards()));
        const boards = computed(() => [...Map.groupBy(fit.value, (kit) => kit.name).values()].map(([first, ...rest]) => ({ first, rest })));
        // the card of the current board of the project, in its section: as it fits the answers, or why it does not
        const currentCard = computed(() => boards.value.find((card) => card.first.name === store.currentBoard) ?? null);
        const currentMiss = computed(() => (currentCard.value ? null : others.value.find((kit) => kit.name === store.currentBoard) ?? null));
        // the list below holds the others: the current board has its card above
        const listed = computed(() => boards.value.filter((card) => card.first.name !== store.currentBoard));
        const shownBoards = ref(BOARDS_SHOWN);
        const asked = computed(() => Object.values(store.answers).some((answer) => (Array.isArray(answer) ? answer.length : answer && answer !== 'none')));
        const addOutput = () => store.answers.outputs.push({ kind: 'tone', hz: undefined, ppm: undefined, jitter: 'any', bits: 8, pins: 1, live: false });
        // what the person has already, boards and modules of the catalog: it costs nothing in a kit
        const ownable = computed(() => {
            store.stamp;
            const listed = (group) => Object.entries(library.catalog?.[group] ?? {}).filter(([, doc]) => !doc.origin && doc.kind !== 'project').map(([name, doc]) => ({ name, title: doc.title ?? name }))
                .sort((a, b) => a.title.localeCompare(b.title));
            return { boards: listed('boards'), modules: listed('modules') };
        });
        const addOwned = () => (store.answers.have ??= []).push({ part: ownable.value.boards[0]?.name, count: 1 });
        Vue.watch(() => [store.loaded, store.stamp, store.language, store.currency, store.answers, store.installed], () => store.askKits(), { deep: true, immediate: true });
        // a board taken into the project or out of it counts as had or not; by its names only, as every count makes the kits
        // of the project again
        Vue.watch(() => store.projectBoards().join(' '), () => store.askKits());
        Vue.watch(() => store.selectedBoard, () => store.followBoard());
        // a plan belongs to the answers it was made for
        Vue.watch(() => store.answers, (answers) => {
            store.plan = null;
            localStorage.setItem(PREFERENCES.answers, JSON.stringify(answers));
        }, { deep: true });
        const money = (price, cost) => priceText(price, cost, (text, ...values) => translate(store.language, text, ...values));
        const priceLink = (item) => reportLink({ template: 'price.yml', item, currency: store.currency });
        const filter = Vue.ref('');
        const said = Vue.ref('');
        const sendSaid = () => {
            store.sayToAgent(said.value);
            said.value = '';
        };
        const groups = computed(() => store.palette.map((group) => ({ ...group, roles: group.roles.filter((role) => translate(store.language, role.text).toLowerCase().includes(filter.value.toLowerCase())) })).filter((group) => group.roles.length));
        const roleOf = (id) => store.palette.flatMap((group) => group.roles).find((role) => role.id === id);
        const boardTitle = (name) => store.kits.find((kit) => kit.name === name)?.title ?? name;
        // An answer of a block to a question about the data of its part; an empty field takes it back.
        const setAsk = (block, question, event) => {
            store.chosenByPerson(block);
            const asks = { ...(block.asks ?? {}) };
            if (event.target.value === '' || event.target.value === 'any') delete asks[question.id];
            else asks[question.id] = question.type === 'choice' ? event.target.value : Number(event.target.value);
            block.asks = Object.keys(asks).length ? asks : undefined;
        };
        // How a person gets the dialog with a model: one command. A page served from a copy of the repository finds the server beside
        // it, and the command runs in the folder the page was started from; any other page gives one that runs in any folder.
        const CLONE = '~/esp32-component-boards';
        const local = ref(false);
        fetch('../tools/boards_mcp.py', { method: 'HEAD' }).then((answer) => (local.value = answer.ok)).catch(() => {});
        const install = computed(() => (local.value ? 'python3 tools/boards_mcp.py --install'
            : `git clone --depth 1 https://github.com/jef-sure/esp32-component-boards ${CLONE} && python3 ${CLONE}/tools/boards_mcp.py --install`));
        const copied = ref(false);
        const copyInstall = () => navigator.clipboard?.writeText(install.value).then(() => (copied.value = true));
        // The part the best kit gives a block, and the other blocks the same part serves.
        const servedBy = (block) => {
            const served = fit.value[0]?.served ?? [];
            const entry = served.find((item) => item.role === block.role && item.names.includes(block.name));
            if (!entry) return null;
            const label = (item) => item.names.map((name) => name || translate(store.language, roleOf(item.role)?.text ?? item.role));
            return { title: entry.title, with: served.filter((item) => item !== entry && item.unit === entry.unit).flatMap(label) };
        };
        const nameOf = (event) => event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^[^a-z]+/, '').replace(/_+$/, '');
        // what limits a part of a role holds for all its blocks: it is asked on the first
        const firstOfRole = (at) => store.answers.blocks.findIndex((block) => block.role === store.answers.blocks[at].role) === at;
        const outputsQuestion = computed(() => store.questions.find((question) => question.type === 'outputs'));
        // the dialog and the palette are where blocks come from: once the dialog starts it takes the column, and the search stays
        const talking = computed(() => store.agent && store.talk.length > 0);
        const stream = ref(null);
        Vue.watch(() => store.talk.length, () => Vue.nextTick(() => {
            if (stream.value) stream.value.scrollTop = stream.value.scrollHeight;
        }));
        // what a kit adds to its board, the board being the title of the card
        const partsOf = (kit) => [...kit.modules, ...(kit.addons ?? [])].map((item) => `${item.count > 1 ? `${item.count} x ` : ''}${item.title}`).join(' + ');
        // a project is written into a folder picked in Chromium, or through tools/boards_mcp.py into its own
        const canWrite = computed(() => host.canOpenFolder || Boolean(store.project?.mode));
        const chosenHas = (kit) => store.chosen.some((item) => item.headline === kit.headline);
        // the cards wait for what the device needs: with nothing asked every board fits, and a hundred cards say nothing
        const showAll = ref(false);
        const showKits = computed(() => asked.value || store.chosen.length > 0 || Boolean(store.answers.board) || showAll.value);
        // a card says first what fits and what is not known; the steps and the notes wait behind it
        const FIRST_LEVELS = ['yes', 'no', 'unknown'];
        const firstSays = (kit) => kit.says.filter((line) => FIRST_LEVELS.includes(line.level));
        const laterSays = (kit) => kit.says.filter((line) => !FIRST_LEVELS.includes(line.level));
        // what the person has of a chain, its products and their counts in order from the board: the part of the block as a list
        const chainBlock = (block) => store.asksOf(block).some((question) => question.limit?.measure === 'chain');
        // where a part of the board is: its buses, or the GPIOs of a part on lines of its own, as an LED
        const partWhere = (part) => part.buses.join(', ') || (part.lines.length ? `GPIO ${part.lines.map((wire) => wire.to.replace('GPIO ', '')).join(', ')}` : '');
        // the Part of a block: the part of the board it came from, any, or a module the person fixes
        const boardPartsOf = (block) => store.boardParts.filter((part) => part.role === block.role);
        const partValue = (block) => block.part ?? (block.from?.board === store.selectedBoard && store.partFrom(block) ? BOARD_PART + block.from.device : store.partFrom(block) ? FROM_BOARD : '');
        const setPart = (block, value) => {
            store.chosenByPerson(block);
            const part = value.startsWith(BOARD_PART) ? boardPartsOf(block).find((item) => item.device === value.slice(BOARD_PART.length)) : null;
            // a part of the selected board brings what its data gives, as from its place in the palette
            if (part) Object.assign(block, { part: undefined, variant: part.variant, asks: { ...part.asks }, from: { board: store.selectedBoard, device: part.device } });
            else if (value === FROM_BOARD) block.part = undefined;
            else if (!value) Object.assign(block, { part: undefined, from: undefined });
            else Object.assign(block, { part: value, fixed: true });
        };
        const haveOf = (block) => (Array.isArray(block.part) ? block.part : []);
        const addHave = (block) => {
            if (!Array.isArray(block.part)) block.part = block.part ? [{ part: block.part, count: 1 }] : [];
            block.part.push({ part: store.partsOf(block)[0].name, count: 1 });
            block.fixed = true;
        };
        const dropHave = (block, at) => {
            block.part.splice(at, 1);
            if (!block.part.length) block.part = undefined;
        };
        const cardHelpers = { store, host, inProject, money, partsOf, firstSays, laterSays, MARKS, priceLink, canWrite, chosenHas };
        return { store, host, fit, boards, inProject, setPart, FROM_BOARD, BOARD_PART, boardPartsOf, partValue, cardHelpers, currentCard, currentMiss, listed, partWhere, others, asked, showAll, showKits, firstSays, laterSays, addOutput, ownable, addOwned, money, numberOf, priceLink, MARKS, filter, groups, roleOf, nameOf, outputsQuestion, firstOfRole, said, sendSaid, talking, stream, partsOf, boardTitle, servedBy, install, local, copied, copyInstall, setAsk, shownBoards, BOARDS_SHOWN, canWrite, chosenHas, chainBlock, haveOf, addHave, dropHave };
    },
    template: `
        <div class="select" :class="{ talking, waiting: !showKits }">
            <aside class="palette">
                <details v-if="!store.agent || store.modelless" class="agent-hint"><summary>{{ t('Talk with a model') }}</summary>
                    <p class="hint">{{ t(local ? 'Once, in the folder you started this page from:' : 'Once, in any folder:') }}</p>
                    <div class="command"><code>{{ install }}</code><button type="button" @click="copyInstall">{{ t(copied ? 'copied' : 'copy') }}</button></div>
                    <p class="hint">{{ t('Then ask your agent to help choose the hardware: it gives a link to this page, with a dialog.') }}</p>
                </details>
                <section v-if="store.boardParts.length && !talking" class="board-parts"><h3>{{ t('On the board') }}</h3>
                    <p class="board-name">{{ boardTitle(store.selectedBoard) }}</p>
                    <button v-for="part in store.boardParts" :key="part.device + '/' + part.role" type="button" class="role" :title="t('on the canvas as it is on the board')"
                        @click="store.addBoardPart(part)">{{ t(roleOf(part.role).text) }} <span class="note">{{ part.title }}<template v-if="partWhere(part)"> · {{ partWhere(part) }}</template></span></button></section>
                <h2 v-if="!talking">{{ t('Roles') }}</h2>
                <input type="search" v-model="filter" :placeholder="t('find a role')">
                <div v-if="!talking || filter" class="roles">
                    <section v-for="group in groups" :key="group.id">
                        <h3>{{ t(group.text) }}</h3>
                        <button v-for="role in group.roles" :key="role.id" type="button" class="role" :class="{ empty: !role.count }" draggable="true"
                            @dragstart="$event.dataTransfer.setData('text/plain', role.id)" @click="store.addBlock(role.id)">{{ t(role.text) }} <span class="note">{{ role.count }}</span></button>
                    </section>
                </div>
                <section v-if="store.agent && !store.modelless" class="talk">
                    <div ref="stream" class="stream">
                        <div v-for="item in store.talk" :key="item.id" class="said" :class="item.from">
                            <pre v-if="item.description">{{ item.text }}</pre><template v-else>{{ item.text }}</template>
                            <div v-if="item.edits" class="offer">
                                <span v-for="block in item.edits.add ?? []" :key="'+' + (block.name || block.role)" class="tag">+ {{ block.name || block.role }}</span>
                                <span v-for="block in item.edits.change ?? []" :key="'~' + block.name" class="tag">~ {{ block.name }}</span>
                                <span v-for="name in item.edits.remove ?? []" :key="'-' + name" class="tag">− {{ name }}</span>
                            </div>
                        </div>
                    </div>
                    <input type="text" v-model="said" :placeholder="t('Write to the model')" @keydown.enter.prevent="sendSaid">
                </section>
            </aside>
            <form class="canvas" @submit.prevent @dragover.prevent @drop.prevent="store.addBlock($event.dataTransfer.getData('text/plain'))">
                <h2>{{ t("Let's build something great!") }}</h2>
                <label class="project">{{ t('Project name') }} <input type="text" v-model="store.projectName" :readonly="store.project?.mode === 'update'"
                    :title="store.project?.mode === 'update' ? t('The name of the program: its boards are named after it.') : ''"></label>
                <textarea class="task" rows="3" v-model="store.answers.task" :placeholder="t('What the device does, who uses it and where it stands')"></textarea>
                <p v-if="!store.answers.blocks.length" class="hint">{{ t('Put here what the device needs: click a role or drag it.') }}</p>
                <div class="blocks">
                    <article v-for="(block, i) in store.answers.blocks" :key="i" class="block" :class="{ fixed: block.fixed }">
                        <header><b>{{ t(roleOf(block.role).text) }}</b>
                            <span><span v-if="block.by === 'model'" class="hint">{{ t('by the model') }}</span><span v-if="block.by === 'board'" class="hint">{{ t('from the board') }}</span>
                                <button class="pin" :class="{ on: block.fixed }" :title="t(block.fixed ? 'Pinned: the model leaves it as it is. Click to free it.' : 'Pin it: the model will leave it as it is.')" @click.prevent="block.fixed = !block.fixed">{{ t(block.fixed ? 'pinned' : 'pin') }}</button>
                                <button class="drop" @click.prevent="store.answers.blocks.splice(i, 1)">×</button></span></header>
                        <label v-if="roleOf(block.role).variants">{{ t('Variant') }}
                            <select v-model="block.variant" @change="store.chosenByPerson(block)"><option :value="undefined">{{ t('any') }}</option>
                                <option v-for="variant in roleOf(block.role).variants" :key="variant.id" :value="variant.id">{{ t(variant.text) }}</option></select></label>
                        <label>{{ t('Name') }} <input type="text" :value="block.name" :placeholder="block.role" @change="block.name = nameOf($event)"></label>
                        <div v-if="chainBlock(block) && store.partsOf(block).length" class="have">{{ t('What you have of it, in order from the board') }}
                            <p v-for="(item, at) in haveOf(block)" :key="at">
                                <select v-model="item.part"><option v-for="part in store.partsOf(block)" :key="part.name" :value="part.name">{{ part.title }}</option></select>
                                <input type="number" min="1" step="1" v-model.number="item.count">
                                <button class="drop" :title="t('take it out')" @click.prevent="dropHave(block, at)">×</button></p>
                            <button @click.prevent="addHave(block)">{{ t('add what you have') }}</button></div>
                        <label v-else-if="block.from || store.partsOf(block).length || boardPartsOf(block).length">{{ t('Part') }}
                            <select :value="partValue(block)" @change="setPart(block, $event.target.value)">
                                <option v-for="part in boardPartsOf(block)" :key="part.device" :value="BOARD_PART + part.device">{{ t('on the board {0}: {1}', boardTitle(store.selectedBoard), part.title) }}</option>
                                <option v-if="store.partFrom(block) && block.from.board !== store.selectedBoard" :value="FROM_BOARD">{{ t('on the board {0}: {1}', boardTitle(block.from.board), store.partFrom(block).title) }}</option>
                                <option value="">{{ t('any') }}</option>
                                <option v-for="part in store.partsOf(block)" :key="part.name" :value="part.name">{{ part.title }}</option></select></label>
                        <template v-if="block.role === 'own_part'">
                            <label>{{ t('Its lines, a soldered one as line=GPIO') }} <input type="text" v-model="block.lines" placeholder="relay=14, beeper"></label>
                            <label>{{ t('Its bus') }} <select v-model="block.bus"><option value="">{{ t('none') }}</option><option value="i2c">I2C</option><option value="spi">SPI</option><option value="uart">UART</option></select></label>
                            <label v-if="block.bus === 'i2c'">{{ t('Its I2C address') }} <input type="text" v-model="block.address" placeholder="0x40"></label>
                        </template>
                        <label v-for="question in store.asksOf(block)" :key="question.id">{{ t(question.text) }}
                            <select v-if="question.type === 'choice'" :value="block.asks?.[question.id] ?? 'any'" @change="setAsk(block, question, $event)">
                                <option v-for="choice in question.choices" :key="choice.value" :value="choice.value">{{ t(choice.text) }}</option></select>
                            <input v-else type="number" step="any" :value="block.asks?.[question.id]" :placeholder="t('any')" @change="setAsk(block, question, $event)"></label>
                        <p v-if="servedBy(block)" class="served">→ {{ servedBy(block).title }}<template v-if="servedBy(block).with.length"> · {{ t('the same part: {0}', servedBy(block).with.join(', ')) }}</template></p>
                        <label v-for="question in firstOfRole(i) ? store.settings(roleOf(block.role)) : []" :key="question.id">{{ t(question.text) }}
                            <select v-if="question.type === 'choice'" :value="store.answers[question.id] ?? question.choices[0].value" @change="store.answers[question.id] = $event.target.value">
                                <option v-for="choice in question.choices" :key="choice.value" :value="choice.value">{{ t(choice.text) }}</option></select>
                            <input v-else type="number" min="0" step="any" :value="store.answers[question.id]" @change="store.answers[question.id] = numberOf($event, question)"></label>
                    </article>
                </div>
                <div class="question">
                    <template v-if="outputsQuestion">
                        <label>{{ t(outputsQuestion.text) }}</label>
                        <div v-for="(output, i) in store.answers.outputs" :key="i" class="output">
                            <select v-model="output.kind"><option value="tone">{{ t('tone') }}</option><option value="pwm">PWM</option></select>
                            <label><input type="number" min="0" step="any" v-model.number="output.hz"> {{ t('Hz') }}</label>
                            <template v-if="output.kind === 'tone'">
                                <label>± <input type="number" min="0" step="any" v-model.number="output.ppm" :placeholder="t('any')"> ppm</label>
                                <select v-model="output.jitter"><option value="any">{{ t('any jitter') }}</option><option value="none">{{ t('no jitter of the divider') }}</option></select>
                            </template>
                            <label v-else><input type="number" min="1" step="1" v-model.number="output.bits"> {{ t('bits of duty') }}</label>
                            <label><input type="checkbox" v-model="output.live"> {{ t('changes while running') }}</label>
                            <select v-model.number="output.pins"><option :value="1">{{ t('one pin') }}</option><option :value="2">{{ t('two pins in antiphase') }}</option></select>
                            <button class="drop" @click.prevent="store.answers.outputs.splice(i, 1)">×</button>
                        </div>
                        <button @click.prevent="addOutput">{{ t('add an output') }}</button>
                        <div v-if="store.answers.outputs.length" class="hint">{{ t('Frequencies are calculated, not measured.') }}</div>
                    </template>
                </div>
                <div class="question">
                    <label>{{ t('What you have already: in a kit it costs nothing') }}</label>
                    <div v-for="(item, i) in store.answers.have ?? []" :key="i" class="output">
                        <select v-model="item.part">
                            <optgroup :label="t('Boards')"><option v-for="part in ownable.boards" :key="part.name" :value="part.name">{{ part.title }}</option></optgroup>
                            <optgroup :label="t('Modules')"><option v-for="part in ownable.modules" :key="part.name" :value="part.name">{{ part.title }}</option></optgroup>
                        </select>
                        <input type="number" min="1" step="1" v-model.number="item.count">
                        <button class="drop" :title="t('take it out')" @click.prevent="store.answers.have.splice(i, 1)">×</button>
                    </div>
                    <button @click.prevent="addOwned">{{ t('add what you have') }}</button>
                </div>
            </form>
            <div class="kits">
                <section v-if="store.plan" class="plan">
                    <h3>{{ t(store.plan.mode === 'create' ? 'A new project in' : 'The project') }} {{ store.plan.folderName }}</h3>
                    <table>
                        <tr v-for="row in store.plan.rows" :key="row.path" :class="row.state">
                            <td><code>{{ row.path }}</code><span v-if="row.made" class="hint">&nbsp;· {{ t('made by board_select.py --again') }}</span></td>
                            <td v-if="row.state === 'new'">{{ t('new') }}</td>
                            <td v-else-if="row.state === 'same'">{{ t('the same, left as it is') }}</td>
                            <td v-else-if="row.state === 'kept'">{{ t('it is there, left as it is') }}</td>
                            <td v-else-if="row.state === 'ours'">{{ t('made by the page or by board_select.py and not changed since: replaced') }}</td>
                            <td v-else-if="row.state === 'refused'" class="no">{{ t('not written: {0}', row.why) }}</td>
                            <td v-else-if="row.state === 'changed'"><label><input type="checkbox" v-model="row.replace"> {{ t('yours, or changed by you: replace it') }}</label></td>
                            <td v-else><label><input type="checkbox" v-model="row.replace"> {{ t('it differs: replace it') }}</label></td>
                        </tr>
                    </table>
                    <details v-for="row in store.plan.rows.filter((item) => (item.state === 'changes' || item.state === 'changed') && item.old !== null)" :key="row.path"><summary>{{ t('{0}: what lies there and what would', row.path) }}</summary>
                        <div class="both"><pre>{{ row.old }}</pre><pre>{{ row.text ?? t('what board_select.py --again makes') }}</pre></div>
                    </details>
                    <fieldset v-if="store.plan.allow && !store.plan.written" class="allow">
                        <legend>{{ t('The server of the model writes into {0}', store.plan.folderName) }}</legend>
                        <label><input type="radio" value="once" v-model="store.plan.allow"> {{ t('this time; ask me again next time') }}</label>
                        <label><input type="radio" value="for ever" v-model="store.plan.allow"> {{ t('for this project from now on') }}</label>
                    </fieldset>
                    <div v-if="store.plan.cmakeLines" class="locked">{{ t('Put these into CMakeLists.txt yourself, the include of project.cmake among them: they read the board.') }}
                        <pre>{{ store.plan.cmakeLines }}</pre></div>
                    <p class="hint">{{ store.plan.source?.git ? t('The component comes from git at the commit {0}.', store.plan.source.git.slice(0, 7))
                        : store.plan.source?.registry ? t('The component comes from the registry, {0}: it resolves once that version is published.', '>=' + store.plan.source.registry)
                        : t('The component comes from git at main: pin a commit in main/idf_component.yml for a build that stays the same.') }}</p>
                    <div v-if="store.plan.manifestLines.length" class="locked">{{ t('Add these to main/idf_component.yml yourself: the file stays as it is.') }}
                        <pre>{{ store.plan.manifestLines.join('\\n') }}</pre></div>
                    <p v-if="!store.plan.written"><button @click="store.writeProject()">{{ t('write') }}</button> <button @click="store.plan = null">{{ t('cancel') }}</button></p>
                    <div v-else>
                        <p class="good">{{ t('{0} file(s) written, nothing else touched.', store.plan.written.length) }}</p>
                        <pre v-if="store.plan.bridge">idf.py build flash monitor</pre>
                        <pre v-else>idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py --again .
idf.py build flash monitor</pre>
                        <p class="hint">{{ t('idf.py builds {0}; idf.py --preset <board> builds another, and in VS Code ESP-IDF: Select Project Configuration chooses it.', store.plan.current) }}</p>
                        <p v-if="store.plan.before !== store.plan.current" class="locked">{{ t('The current board is {0} now: in VS Code reload the window, Developer: Reload Window, so that the ESP-IDF extension and CMake Tools take it, and open a new terminal of ESP-IDF.', store.plan.current) }}</p>
                    </div>
                </section>
                <section v-if="store.chosen.length || store.withoutKit().length" class="chosen">
                    <h3>{{ t('The boards of the project') }}</h3>
                    <p v-for="item in store.withoutKit().filter((item) => !store.isCompanion(item))" :key="item.board">
                        <template v-if="store.isComputer(item.board)"><template v-if="item.title">{{ item.title }} </template><code>{{ item.board }}</code>
                            <span class="hint">{{ t('a computer that shows a board the project does not have; it stays in the project') }}</span></template>
                        <template v-else><label :title="t('the current board: idf.py builds it when no preset is named')"><input type="radio" :value="item.board" v-model="store.current"> <template v-if="item.title">{{ item.title }} </template><code>{{ item.board }}</code></label>
                            <span class="hint">{{ t(item.kept ? 'its kit does not fit the answers now; it stays in the project' : 'no kit of the page: a command made it; it stays in the project') }}</span></template>
                        <span v-if="store.companionOf(item.board)" class="hint">{{ t('its computer: {0}', store.companionOf(item.board)) }}</span></p>
                    <p v-for="item in store.chosen" :key="item.headline">
                        <label :title="t('the current board: idf.py builds it when no preset is named')"><input type="radio" :value="item.headline" v-model="store.current"> {{ item.kit.headline }}</label>
                        <span v-if="item.gone" class="hint">{{ t('does not fit the answers now') }}</span>
                        <span v-if="store.companionOf(store.boardOf(item))" class="hint">{{ t('its computer: {0}', store.companionOf(store.boardOf(item))) }}</span>
                        <button class="drop" :title="t('take it out of the project')" @click="store.chooseKit(item.kit)">×</button></p>
                    <button v-if="canWrite" @click="store.planProject()">{{ t('make the project of these boards…') }}</button>
                    <label v-if="canWrite && store.chosen.some((item) => store.hasDisplay(item.kit))" class="hint" :title="t('The computer shows the display of the board in a window: Linux with SDL2.')">
                        <input type="checkbox" :checked="store.withComputer" @change="store.setComputer($event.target.checked)"> {{ t('add the build on the computer') }}</label>
                    <kit-card v-if="currentCard" class="current" :kit="currentCard.first" :rest="currentCard.rest" :helpers="cardHelpers"></kit-card>
                    <article v-else-if="currentMiss" class="kit current"><h3>{{ currentMiss.title }}</h3>
                        <ul><li v-for="line in currentMiss.says" :key="line.text" :class="line.level"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul></article>
                </section>
                <p v-if="store.answers.board" class="fixed-board">{{ t('Board pinned: {0}', boardTitle(store.answers.board)) }}
                    <button class="drop" :title="t('free the board')" @click="store.answers.board = undefined">×</button></p>
                <div v-if="!showKits" class="first">
                    <p>{{ t('Put on the canvas what the device needs: click a role on the left, or drag it. The boards that fit it come here.') }}</p>
                    <button @click="showAll = true">{{ t('show every board anyway') }}</button>
                </div>
                <template v-else>
                <p class="summary"><b>{{ t(boards.length === 1 ? '{0} board fits' : '{0} boards fit', boards.length) }}</b>
                    <span v-if="store.solving" class="hint">{{ t('counting…') }}</span>
                    <span class="hint">{{ t('{0} sets of parts in all: the others of a board are in its card.', fit.length) }}</span>
                    <span class="hint">{{ t(asked ? 'The fewest unknowns first, then the least worth of what you did not ask for, the fewest modules and the fewest wires; the price counts last, or after the unknowns with a budget.' : 'Nothing is asked yet, so every board fits.') }}</span></p>
                <p v-if="store.project?.mode" class="hint">{{ t(store.project.mode === 'create' ? 'The project: {0}, a new one.' : 'The project: {0}, a program: it gets only its boards.', store.project.path) }}</p>
                <p v-else class="hint">{{ t('An empty folder gets a whole project. A folder with a program gets only its board.') }}</p>
                <p v-if="listed.length > shownBoards" class="hint">{{ t('To narrow: a budget or a platform above, pin a part in a block, or pin a board.') }}</p>
                <kit-card v-for="{ first: kit, rest } in listed.slice(0, shownBoards)" :key="kit.name" :kit="kit" :rest="rest" :helpers="cardHelpers"></kit-card>
                <button v-if="listed.length > shownBoards" @click="shownBoards += BOARDS_SHOWN">{{ t('{0} more boards', Math.min(BOARDS_SHOWN, listed.length - shownBoards)) }}</button>
                <p v-if="!fit.length">{{ t('Nothing fits these answers.') }}</p>
                <details v-if="others.length" class="others"><summary>{{ t('What does not fit, and why ({0})', others.length) }}</summary>
                    <article v-for="kit in others" :key="kit.name" class="kit">
                        <h3>{{ kit.title }}</h3>
                        <ul><li v-for="line in kit.says" :key="line.text" :class="line.level" :title="line.basis ?? (line.judgement ? line.judgement + ' (catalog/judgements.json)' : null)"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul>
                    </article>
                </details>
                </template>
            </div>
        </div>
    `,
};

const app = createApp({
    components: { TreeItem, NodeCard, PinMap, NewDocument, SelectPage },
    setup() {
        const store = useEditor();
        Vue.onMounted(() => store.start());
        const VIEWS = ['card', 'pins', 'json'];
        Vue.watch(() => store.language, (language) => {
            localStorage.setItem(PREFERENCES.language, language);
            document.documentElement.lang = language;
        }, { immediate: true });
        Vue.watch(() => store.currency, (currency) => localStorage.setItem(PREFERENCES.currency, currency));
        // the name typed for a new project, by its folder: a reload of the page keeps it
        Vue.watch(() => store.projectName, (name) => store.project?.mode === 'create' && localStorage.setItem(`${PREFERENCES.project}:${store.project.path}`, name));
        const jsonOf = computed(() => (store.jsonResolved ? JSON.stringify(store.checks.resolved, null, 2) : store.saved));
        return { store, host, VIEWS, jsonOf, numberOf, LANGUAGES };
    },
    template: `
        <header class="bar">
            <h1>boards</h1>
            <span class="views">
                <button :class="{ here: store.page === 'select' }" @click="store.page = 'select'">{{ t('select') }}</button>
                <button :class="{ here: store.page === 'edit' }" @click="store.page = 'edit'">{{ t('edit') }}</button>
            </span>
            <button v-if="host.canOpenFolder" :title="t('a program or its local-boards; the repository, to save into the catalog')" @click="store.openFolder()">{{ t('open a folder') }}</button>
            <label v-else class="button">{{ t('open a folder') }}<input type="file" webkitdirectory hidden @change="store.openPicked($event.target.files)"></label>
            <template v-if="store.entry && store.page === 'edit'">
                <span class="path">{{ store.entry.path }}</span>
                <span v-if="store.edited(store.entry)" class="tag open">edited</span>
                <button :disabled="store.readOnly || !store.edited(store.entry)" @click="store.save()">save</button>
            </template>
            <span class="say">{{ store.note }}</span>
            <span class="top">
                <template v-if="store.page === 'select'">
                    <label v-for="question in store.topQuestions" :key="question.id">{{ t(question.text) }}
                        <select v-if="question.type === 'choice'" v-model="store.answers[question.id]"><option v-for="choice in question.choices" :key="choice.value" :value="choice.value === 'any' ? undefined : choice.value">{{ t(choice.text) }}</option></select>
                        <select v-else-if="question.type === 'version'" v-model="store.answers[question.id]"><option :value="undefined">{{ t('by the kit') }}</option>
                            <option v-for="version in store.versionsOf(store.answers.platform)" :key="version" :value="version">{{ version }}</option></select>
                        <input v-else type="number" min="0" step="any" :value="store.answers[question.id]" @input="store.answers[question.id] = numberOf($event)"></label>
                </template>
                <label>{{ t('Prices in') }}
                    <select v-model="store.currency"><option v-for="currency in store.currencies" :key="currency">{{ currency }}</option></select></label>
                <select v-model="store.language" :aria-label="store.language"><option v-for="(language, code) in LANGUAGES" :key="code" :value="code">{{ language.title }}</option></select>
            </span>
        </header>
        <p v-if="store.error && !(FROM_FILE && !store.loaded)" class="banner">{{ store.error }}</p>
        <p v-if="!store.loaded && FROM_FILE" class="start">{{ t('Opened as a file, the page reads nothing: the browser lets a file fetch no other file. Start its server in the folder of the project and open the link it prints:') }}
            <code>python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve</code>. {{ t('In a clone of the repository:') }} <code>python3 tools/boards_mcp.py --serve</code>.</p>
        <p v-else-if="!store.loaded" class="start">The page is not served from the repository, so it has no catalog: open the folder of the repository.
            A program or its <code>local-boards</code> comes after it.</p>
        <select-page v-else-if="store.page === 'select'"></select-page>
        <main v-else>
            <nav class="documents">
                <input type="search" v-model="store.filter" placeholder="filter">
                <new-document></new-document>
                <details v-for="group in store.groups" :key="group.title" :open="group.title === 'Boards' || group.title === 'Local boards' || !!store.filter">
                    <summary>{{ group.title }} <span class="note">{{ group.entries.length }}</span></summary>
                    <button v-for="entry in group.entries" :key="entry.key" class="node" :class="{ here: entry.key === store.key }" @click="store.open(entry.key)">
                        {{ entry.name }}<span v-if="store.edited(entry)" class="note"> edited</span>
                    </button>
                </details>
            </nav>
            <nav class="tree" v-if="store.doc">
                <button class="node" :class="{ here: !store.selected.length }" @click="store.select([])">{{ store.doc.name ?? store.entry.name }}</button>
                <ul><tree-item v-for="node in store.tree" :key="node.id" :node="node"></tree-item></ul>
            </nav>
            <div class="work" v-if="store.doc">
                <div class="views">
                    <button v-for="view in VIEWS" :key="view" :class="{ here: store.view === view }" @click="store.view = view">{{ view }}</button>
                    <span v-if="store.checks.problems.length" class="count wrong">{{ store.checks.problems.length }} problem(s)</span>
                    <span v-else class="count good">no problems</span>
                </div>
                <ul v-if="store.checks.problems.length" class="problems">
                    <li v-for="(problem, i) in store.checks.problems" :key="i"><span class="tag">{{ problem.stage }}</span> {{ problem.text }}</li>
                </ul>
                <node-card v-if="store.view === 'card'"></node-card>
                <pin-map v-else-if="store.view === 'pins'"></pin-map>
                <section v-else class="card">
                    <p><label><input type="checkbox" v-model="store.jsonResolved"> resolved, as the tools read it</label></p>
                    <pre>{{ jsonOf }}</pre>
                </section>
            </div>
        </main>
    `,
});

app.config.globalProperties.PLACES_OPEN = PLACES_OPEN;
// a page opened as a file fetches nothing: it says how to serve it instead of what failed
app.config.globalProperties.FROM_FILE = location.protocol === 'file:';
app.use(Pinia.createPinia());
app.config.globalProperties.t = (text, ...values) => translate(useEditor().language, text, ...values);
app.mount('#app');
