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
        const kind = computed(() => {
            const { values, types } = shape.value;
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
        return { own, shown, shape, kind, failed, text, set, setJson };
    },
    template: `
        <select v-if="kind === 'choice'" :value="shown" :disabled="locked" :class="{ inherited: own === undefined }" @change="set(JSON.parse($event.target.selectedOptions[0].dataset.value))">
            <option v-if="shown === undefined" :value="undefined"></option>
            <option v-for="choice in shape.values" :key="choice" :value="choice" :data-value="JSON.stringify(choice)">{{ choice }}</option>
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
const BOARDS_SHOWN = 10; // the cards shown at first: a hundred boards fit when little is asked

// Which question a board and its modules answer: the first screen.
const numberOf = (event, question) => {
    if (event.target.value === '') return undefined;
    const value = Number(event.target.value);
    return question?.type === 'count' ? Math.min(Math.max(Math.floor(value), 0), question.max ?? value) : value;
};

const SelectPage = {
    setup() {
        const store = useEditor();
        const fit = computed(() => store.kits.filter((kit) => kit.fits));
        const others = computed(() => store.kits.filter((kit) => !kit.fits));
        // One card a board: the kits come sorted, so its first is its best, and the rest wait behind it.
        const boards = computed(() => [...Map.groupBy(fit.value, (kit) => kit.name).values()].map(([first, ...rest]) => ({ first, rest })));
        const shownBoards = ref(BOARDS_SHOWN);
        const asked = computed(() => Object.values(store.answers).some((answer) => (Array.isArray(answer) ? answer.length : answer && answer !== 'none')));
        const addOutput = () => store.answers.outputs.push({ kind: 'tone', hz: undefined, ppm: undefined, jitter: 'any', bits: 8, pins: 1, live: false });
        Vue.watch(() => [store.loaded, store.stamp, store.language, store.currency, store.answers, store.installed], () => store.askKits(), { deep: true, immediate: true });
        // a plan belongs to the answers it was made for
        Vue.watch(() => store.answers, (answers) => {
            store.plan = null;
            localStorage.setItem(PREFERENCES.answers, JSON.stringify(answers));
        }, { deep: true });
        const money = (price) => (!price ? '' : !price.known ? translate(store.language, 'price not known') : `${price.low === price.high ? price.low : `${price.low}–${price.high}`} ${price.currency}${price.missing.length ? ' + ?' : ''}`);
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
            const asks = { ...(block.asks ?? {}) };
            if (event.target.value === '') delete asks[question.id];
            else asks[question.id] = Number(event.target.value);
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
        return { store, host, fit, boards, others, asked, addOutput, money, numberOf, priceLink, MARKS, filter, groups, roleOf, nameOf, outputsQuestion, firstOfRole, said, sendSaid, talking, stream, partsOf, boardTitle, servedBy, install, local, copied, copyInstall, setAsk, shownBoards, BOARDS_SHOWN };
    },
    template: `
        <div class="select" :class="{ talking }">
            <aside class="palette">
                <details v-if="!store.agent" class="agent-hint"><summary>{{ t('Talk with a model') }}</summary>
                    <p class="hint">{{ t(local ? 'Once, in the folder you started this page from:' : 'Once, in any folder:') }}</p>
                    <div class="command"><code>{{ install }}</code><button type="button" @click="copyInstall">{{ t(copied ? 'copied' : 'copy') }}</button></div>
                    <p class="hint">{{ t('Then ask your agent to help choose the hardware: it gives a link to this page, with a dialog.') }}</p>
                </details>
                <h2 v-if="!talking">{{ t('Roles') }}</h2>
                <input type="search" v-model="filter" :placeholder="t('find a role')">
                <div v-if="!talking || filter" class="roles">
                    <section v-for="group in groups" :key="group.id">
                        <h3>{{ t(group.text) }}</h3>
                        <button v-for="role in group.roles" :key="role.id" type="button" class="role" :class="{ empty: !role.count }" draggable="true"
                            @dragstart="$event.dataTransfer.setData('text/plain', role.id)" @click="store.addBlock(role.id)">{{ t(role.text) }} <span class="note">{{ role.count }}</span></button>
                    </section>
                </div>
                <section v-if="store.agent" class="talk">
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
                <label class="project">{{ t('Project name') }} <input type="text" v-model="store.projectName"></label>
                <textarea class="task" rows="3" v-model="store.answers.task" :placeholder="t('What the device does, who uses it and where it stands')"></textarea>
                <p v-if="!store.answers.blocks.length" class="hint">{{ t('Put here what the device needs: click a role or drag it.') }}</p>
                <div class="blocks">
                    <article v-for="(block, i) in store.answers.blocks" :key="i" class="block" :class="{ fixed: block.fixed }">
                        <header><b>{{ t(roleOf(block.role).text) }}</b>
                            <span><span v-if="block.by === 'model'" class="hint">{{ t('by the model') }}</span>
                                <button class="pin" :class="{ on: block.fixed }" :title="t(block.fixed ? 'Pinned: the model leaves it as it is. Click to free it.' : 'Pin it: the model will leave it as it is.')" @click.prevent="block.fixed = !block.fixed">{{ t(block.fixed ? 'pinned' : 'pin') }}</button>
                                <button class="drop" @click.prevent="store.answers.blocks.splice(i, 1)">×</button></span></header>
                        <label v-if="roleOf(block.role).variants">{{ t('Variant') }}
                            <select v-model="block.variant"><option :value="undefined">{{ t('any') }}</option>
                                <option v-for="variant in roleOf(block.role).variants" :key="variant.id" :value="variant.id">{{ t(variant.text) }}</option></select></label>
                        <label>{{ t('Name') }} <input type="text" :value="block.name" :placeholder="block.role" @change="block.name = nameOf($event)"></label>
                        <label v-if="store.partsOf(block).length">{{ t('Part') }}
                            <select v-model="block.part" @change="block.fixed = block.fixed || Boolean(block.part)"><option :value="undefined">{{ t('any') }}</option>
                                <option v-for="part in store.partsOf(block)" :key="part.name" :value="part.name">{{ part.title }}</option></select></label>
                        <template v-if="block.role === 'own_part'">
                            <label>{{ t('Its lines, a soldered one as line=GPIO') }} <input type="text" v-model="block.lines" placeholder="relay=14, beeper"></label>
                            <label>{{ t('Its bus') }} <select v-model="block.bus"><option value="">{{ t('none') }}</option><option value="i2c">I2C</option><option value="spi">SPI</option><option value="uart">UART</option></select></label>
                            <label v-if="block.bus === 'i2c'">{{ t('Its I2C address') }} <input type="text" v-model="block.address" placeholder="0x40"></label>
                        </template>
                        <label v-for="question in store.asksOf(block)" :key="question.id">{{ t(question.text) }}
                            <input type="number" step="any" :value="block.asks?.[question.id]" :placeholder="t('any')" @change="setAsk(block, question, $event)"></label>
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
            </form>
            <div class="kits">
                <section v-if="store.plan" class="plan">
                    <h3>{{ t(store.plan.mode === 'create' ? 'A new project in' : 'The project') }} {{ store.plan.folderName }}</h3>
                    <table>
                        <tr v-for="row in store.plan.rows" :key="row.path" :class="row.state">
                            <td><code>{{ row.path }}</code></td>
                            <td v-if="row.state === 'new'">{{ t('new') }}</td>
                            <td v-else-if="row.state === 'same'">{{ t('the same, left as it is') }}</td>
                            <td v-else-if="row.state === 'kept'">{{ t('it is there, left as it is') }}</td>
                            <td v-else><label><input type="checkbox" v-model="row.replace"> {{ t('it differs: replace it') }}</label></td>
                        </tr>
                    </table>
                    <details v-for="row in store.plan.rows.filter((item) => item.state === 'changes')" :key="row.path"><summary>{{ t('{0}: what lies there and what would', row.path) }}</summary>
                        <div class="both"><pre>{{ row.old }}</pre><pre>{{ row.text }}</pre></div>
                    </details>
                    <div v-if="store.plan.cmakeLines" class="locked">{{ t('Put these into CMakeLists.txt yourself, the include of project.cmake among them: they read the board.') }}
                        <pre>{{ store.plan.cmakeLines }}</pre></div>
                    <div v-if="store.plan.requiresLine" class="locked">{{ t('In main/CMakeLists.txt, in idf_component_register: {0}', store.plan.requiresLine) }}</div>
                    <div v-if="store.plan.manifestLines.length" class="locked">{{ t('Add these to main/idf_component.yml yourself: the file stays as it is.') }}
                        <pre>{{ store.plan.manifestLines.join('\\n') }}</pre></div>
                    <p v-if="!store.plan.written"><button @click="store.writeProject()">{{ t('write') }}</button> <button @click="store.plan = null">{{ t('cancel') }}</button></p>
                    <div v-else>
                        <p class="good">{{ t('{0} file(s) written, nothing else touched.', store.plan.written.length) }}</p>
                        <pre>idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py --reset {{ store.plan.board }} .
idf.py reconfigure build flash monitor</pre>
                    </div>
                </section>
                <p v-if="store.answers.board" class="fixed-board">{{ t('Board pinned: {0}', boardTitle(store.answers.board)) }}
                    <button class="drop" :title="t('free the board')" @click="store.answers.board = undefined">×</button></p>
                <p class="summary"><b>{{ t(fit.length === 1 ? '{0} set of parts fits' : '{0} sets of parts fit', fit.length) }}</b>
                    <span v-if="store.solving" class="hint">{{ t('counting…') }}</span>
                    <span class="hint">{{ t(asked ? 'The fewest unknowns first, then the least worth of what you did not ask for, the fewest modules and the fewest wires; the price counts last, or after the unknowns with a budget.' : 'Nothing is asked yet, so every board fits.') }}</span></p>
                <p class="hint">{{ t('An empty folder gets a whole project. A folder with a program gets only its board.') }}</p>
                <p v-if="boards.length > shownBoards" class="hint">{{ t('{0} boards fit. To narrow: a budget or a platform above, pin a part in a block, or pin a board.', boards.length) }}</p>
                <article v-for="{ first: kit, rest } in boards.slice(0, shownBoards)" :key="kit.name" class="kit">
                    <img v-if="kit.picture" class="picture" :src="host.pictureSrc(kit.picture)" :alt="kit.title">
                    <h3>{{ kit.title }}</h3>
                    <p v-if="kit.modules.length || kit.addons?.length" class="added">+ {{ partsOf(kit) }}</p>
                    <p class="note">{{ money(kit.price) }}<template v-if="kit.modules.length || kit.addons?.length"> · {{ t('Parts bought one by one: the solver put them together.') }}</template></p>
                    <div v-if="kit.modules.some((module) => module.picture)" class="parts">
                        <figure v-for="module in kit.modules.filter((item) => item.picture)" :key="module.name" :title="module.credit">
                            <img :src="host.pictureSrc(module.picture)" :alt="module.title"><figcaption>{{ module.title }}</figcaption></figure>
                        <p class="hint credit">{{ t('Pictures of parts: Fritzing, CC BY-SA 3.0. Hold the pointer on one for its author.') }}</p>
                    </div>
                    <ul><li v-for="line in kit.says" :key="line.text" :class="line.level" :title="line.judgement ? line.judgement + ' (catalog/judgements.json)' : null"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul>
                    <p v-if="kit.price.unpriced.length" class="hint">{{ t('Know a price?') }}
                        <a v-for="item in kit.price.unpriced" :key="item.item" target="_blank" rel="noopener" :href="priceLink(item.item)">{{ item.title }}</a></p>
                    <details v-if="kit.wiring.length"><summary>{{ t('the wires') }}</summary>
                        <div v-for="module in kit.wiring" :key="module.use" class="wiring"><b>{{ module.title }}</b>
                            <span v-for="wire in module.lines" :key="wire.line"><code>{{ wire.line }}</code> → {{ wire.to }}</span></div>
                    </details>
                    <button v-if="host.canOpenFolder && kit.writable" @click="store.planProject(kit)">{{ t('make a project…') }}</button>
                    <button v-if="store.answers.board !== kit.name" :title="t('Pin this board: the solver and the model try no other.')" @click="store.answers.board = kit.name">{{ t('pin this board') }}</button>
                    <span v-if="kit.imported" class="hint">{{ t('imported: no project until this board is in the catalog') }}</span>
                    <span v-else-if="!kit.writable" class="hint">{{ t('The page writes projects for ESP-IDF only for now.') }}</span>
                    <span v-else-if="!host.canOpenFolder" class="hint">{{ t('Writing a project into a folder takes Chromium.') }}</span>
                    <details v-if="rest.length" class="more"><summary>{{ t('{0} more on this board', rest.length) }}</summary>
                        <p v-for="other in rest" :key="other.headline">+ {{ partsOf(other) || t('nothing more') }} <span class="note">{{ money(other.price) }}</span>
                            <button v-if="host.canOpenFolder && other.writable" @click="store.planProject(other)">{{ t('make a project…') }}</button></p>
                    </details>
                </article>
                <button v-if="boards.length > shownBoards" @click="shownBoards += BOARDS_SHOWN">{{ t('{0} more boards', Math.min(BOARDS_SHOWN, boards.length - shownBoards)) }}</button>
                <p v-if="!fit.length">{{ t('Nothing fits these answers.') }}</p>
                <details v-if="others.length" class="others"><summary>{{ t('What does not fit, and why ({0})', others.length) }}</summary>
                    <article v-for="kit in others" :key="kit.name" class="kit">
                        <h3>{{ kit.title }}</h3>
                        <ul><li v-for="line in kit.says" :key="line.text" :class="line.level" :title="line.judgement ? line.judgement + ' (catalog/judgements.json)' : null"><span class="mark">{{ MARKS[line.level] }}</span> {{ line.text }}</li></ul>
                    </article>
                </details>
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
        const jsonOf = computed(() => (store.jsonResolved ? JSON.stringify(store.checks.resolved, null, 2) : store.saved));
        return { store, host, VIEWS, jsonOf, numberOf, LANGUAGES };
    },
    template: `
        <header>
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
        <p v-if="store.error" class="banner">{{ store.error }}</p>
        <p v-if="!store.loaded" class="start">The page is not served from the repository, so it has no catalog: open the folder of the repository.
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
app.use(Pinia.createPinia());
app.config.globalProperties.t = (text, ...values) => translate(useEditor().language, text, ...values);
app.mount('#app');
