// From the answers to the questions of catalog/questions.json to kits: a board of the catalog and the modules it
// lacks, with the wires. The solver only proposes: a kit is a project, and the checks of the tools decide about it.
'use strict';

const KIT_FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const SELECTION_VERSION = 3; // selection.json with the kits of several boards and the current one
const OTHERS_KEPT = 20; // the kits that fit too, the best first, that selection.json names: the rest come again from its answers
const CHIP_HIGH_MV = 3300; // what a pin of an ESP32 gives as high
const MOST_MODULES = 6; // the parts tried for one need: more make the search longer and the list no clearer
const OWN_PART = 'own_part'; // the role of a part of the person's own, which the catalog has not
const CHAIN_QUESTION = 'chain_outputs'; // the outputs a block of chained parts asks, by which a kit counts its products
const JOINT_QUESTION = 'joint_outputs'; // the weight of a joint of two products of a chain, in outputs to spare
const MOST_CHOICES = 12; // of modules for one board, tried one by one: five needs on a hundred boards took a minute and a half
const ROUNDS_OF_CHANGES = 2; // past that, what one change of the best gives, and again from the new best
// What the solver wires by itself, in the order it tries them. select: a line of its own for each device; alone: a bus
// for each device; fixed: the pins belong to the chip, so a module takes a free bus of the board, on a ribbon.
const KIT_BUSES = {
    i2c: { host: 'i2c', lines: ['sda', 'scl'] },
    spi: { host: 'spi', lines: ['mosi', 'miso', 'sclk'], select: true, most: 6 }, // DEV_NUM_MAX of spi_master.c: on an S3 the seventh gave ESP_ERR_NO_MEM
    qspi: { host: 'spi', lines: ['sclk', 'd0', 'd1', 'd2', 'd3'], select: true },
    uart: { host: 'uart', lines: ['tx', 'rx'], alone: true },
    dsi: { lines: [], fixed: true },
    gpio: { lines: [] }, // no bus: the lines are those of a way of the device
};
const KIT_CURRENCY = 'EUR';
const LEAST_WORTH = 0.01; // the least a part of a board weighs, in KIT_CURRENCY: a part with no price is not counted as 0 (Anton, 2026-11-03)
const PRESCALES_TRIED = 8; // the smallest prescalers that fit: a larger one only loses resolution
const MM_IN_INCH = 25.4;
const cents = (value) => Math.round(value * 100) / 100;
// a range of a price as the page writes it: one number when both ends are the same
const spread = ([low, high]) => (cents(low) === cents(high) ? `${cents(low)}` : `${cents(low)}–${cents(high)}`);

const STATUSES_THAT_FIT = ['yes', 'partly'];
const HEALTH_SECTIONS = ['frames', 'waiting', 'code_health'];
const HEALTH_POINTS = { yes: 1, partly: 0.5 };

// What the order reads of an audit: its last entry, the same reading for every library.
function auditSummary(doc) {
    const last = doc.audits.at(-1);
    const items = Object.entries(last.items);
    const count = (severity) => last.defects.filter((defect) => defect.severity === severity).length;
    const healthItems = items.filter(([name]) => HEALTH_SECTIONS.includes(name.split('.')[0]));
    const health = healthItems.reduce((sum, [, item]) => sum + (HEALTH_POINTS[item.status] ?? 0), 0);
    return { statuses: Object.fromEntries(items.map(([name, item]) => [name, item.status])), high: count('high'), medium: count('medium'), health, health_of: healthItems.length, version: last.version, date: last.date };
}

// A library with what it requires, all the way down: it answers for those, and what nobody read stays named.
function withRequired({ all, audits }, id, seen = new Set([id])) {
    const own = audits[id];
    const total = { high: own?.high ?? 0, medium: own?.medium ?? 0, unread: own ? [] : [id] };
    for (const needed of all[id]?.requires ?? []) {
        if (seen.has(needed)) continue;
        seen.add(needed);
        const below = withRequired({ all, audits }, needed, seen);
        total.high += below.high;
        total.medium += below.medium;
        total.unread.push(...below.unread);
    }
    return total;
}

// The audited libraries of a chip that fit a project, best first: what fits comes from the audit, the order from what was found.
// Whether a version of a platform, as 5.5, meets a range of a manifest, as >=5.2.0 or ^5.3: some release of that line does.
// A form not read here leaves the version in.
function within(version, range) {
    const parts = (text) => text.split('.').map(Number);
    const compare = (a, b) => {
        for (let i = 0; i < Math.max(a.length, b.length); i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) - (b[i] ?? 0);
        return 0;
    };
    const RELEASE = 999; // the last release of a line, so >=5.5.2 holds for 5.5
    const meets = (candidate, term) => {
        const match = /^(>=|<=|!=|>|<|==|=|\^|~)?\s*(\d+(?:\.\d+)*)$/.exec(term.trim());
        if (!match) return true;
        const [, op = '==', text] = match;
        const bound = parts(text);
        const order = compare(candidate, bound);
        if (op === '>=') return order >= 0;
        if (op === '>') return order > 0;
        if (op === '<=') return order <= 0;
        if (op === '<') return order < 0;
        if (op === '^') return order >= 0 && candidate[0] === bound[0];
        if (op === '~') return order >= 0 && candidate[0] === bound[0] && candidate[1] === bound[1];
        if (op === '!=') return compare(candidate.slice(0, bound.length), bound) !== 0;
        return compare(candidate.slice(0, bound.length), bound) === 0;
    };
    const line = parts(version);
    const terms = range.split(/,|\s+(?=[<>=!^~])/).filter((term) => term.trim() && term.trim() !== '*');
    return [[...line, 0], [...line, RELEASE]].some((candidate) => terms.every((term) => meets(candidate, term)));
}

function auditedOrder(libraries, { chip, platform, bus, several, standard }) {
    const fits = (id) => {
        const asked = [`transports.${bus}`, ...(several ? ['several.several_readers'] : []), ...(several && bus === 'spi' ? ['several.shared_spi_bus'] : []), ...(standard ? [`cards.${standard}`] : [])];
        return libraries.all[id]?.platforms?.includes(platform) && asked.every((item) => STATUSES_THAT_FIT.includes(libraries.audits[id].statuses[item]));
    };
    return (libraries.byChip[chip] ?? []).filter((id) => libraries.audits[id] && fits(id)).map((id) => ({ ...libraries.audits[id], id, ...withRequired(libraries, id) }))
        .sort((a, b) => a.high - b.high || a.medium - b.medium || b.health - a.health || a.id.localeCompare(b.id));
}

function kitSolver({ catalog, loader, questions, roles = [], libraries = { all: {}, byChip: {}, audits: {} }, rates, levels, checksOf, pinMap, judgements = [], t = (text, ...values) => text.replace(/\{(\d)\}/g, (_, i) => values[+i]) }) {
    // the judgements of catalog/judgements.json, by kind: each kind is a function here
    const judgementsOf = (kind) => judgements.filter((item) => item.kind === kind);
    const shortOfPins = (wanted, left) => t('it takes {0} more pins and {1} free ones come out of this board', wanted, left);
    const valueAt = (node, path) => path.split('.').reduce((at, key) => (at === undefined || at === null ? undefined : at[key]), node);
    // A part of a need: by its class, or by the role it names. A variant it does not name stays in: the kit can only say so.
    const isClass = (device, need) => {
        const byClass = need.role ? Boolean(device.provides?.[need.role]) : (device.classes || []).includes(need.class) && Object.entries(need.where || {}).every(([path, value]) => valueAt(device, path) === value);
        const found = byClass || Boolean(need.id && device.provides?.[need.id]); // an imported part has no class of its own, it names its roles
        const said = device.provides?.[need.id]?.variant;
        return found && (!need.variant || !said || said === need.variant);
    };
    const titleOf = (need) => need.title.toLowerCase();
    // a display by its class, or by the role it gives: an imported part has no class of its own
    const isDisplay = (device) => (device.classes || []).includes('display') || Boolean(device.provides?.display);

    function diagonalOf(device) {
        const panel = device.config?.panel;
        const [width, height] = panel?.mm_w ? [panel.mm_w, panel.mm_h] : panel?.window_mm ?? [];
        return width ? Math.hypot(width, height) / MM_IN_INCH : null;
    }

    // What a question can limit: where the figure lies, and what to say when a part falls short or has no figure.
    const reachOf = (device) => [].concat(device.provides?.nfc?.range_mm ?? null);
    const MEASURES = {
        diagonal_in: { of: diagonalOf, short: (asked) => t('the display is smaller than {0} inches', asked), unknown: 'the size of the display is not in the data' },
        range_mm: { of: (device) => reachOf(device)[0], short: (asked) => t('no reader that reaches {0} mm', asked), unknown: 'the reading distance is not in the data' },
        // The reach of a reader is a guide along its axis and two readers side by side are not measured: an unknown of the kit, not a refusal.
        gap_mm: { of: (device) => reachOf(device).at(-1), fits: (reach, gap) => reach < gap, soft: (title, reach, gap) => t('{0} reaches {1} mm and the readers are {2} mm apart: a card at one may be read by the other too, this is not measured', title, reach, gap), unknown: 'the longest reading distance is not in the data', unanswered: 'the distance between the readers is not given: a card at one may be read by the other too' },
    };

    // a panel is round only when its data says so: a GC9A01 drives square glass too
    MEASURES.shape = { of: (device) => (device.config?.panel ? (device.config.panel.round ? 'round' : 'rectangular') : null), fits: (shape, asked) => shape === asked, short: (asked) => t('no {0} display', t(asked)), unknown: 'the shape of the display is not in the data' };

    // the depths of color the driver of a display takes; a block taken from a board shows the depth its data starts it with
    MEASURES.depth_bits = { of: (device) => device.libraries?.[device.library]?.supports?.depth_bits ?? null, fits: (depths, asked) => depths.includes(Number(asked)),
        short: (asked) => t('no display whose driver takes {0} bits of color', asked), unknown: 'the depths of color its driver takes are not in the data',
        given: (device) => (device.config?.depth_bits ? String(device.config.depth_bits) : null) };

    // the swing a part of sound reaches by the best of its ways
    MEASURES.swing_v = { of: (device) => (device.ways?.some((way) => way.gives?.swing_v !== undefined) ? Math.max(...device.ways.map((way) => way.gives?.swing_v ?? 0)) : null),
        short: (asked) => t('no part of sound swings {0} V', asked), unknown: 'its swing is not in the data' };

    // a chain grows to the outputs asked, so a part that chains always fits; one that does not says nothing of its outputs
    MEASURES.chain = { of: (device) => (device.chain ? (device.config?.count ?? 1) * (device.chain.unit ?? device.chain.per) : null), fits: () => true, short: () => '', unknown: 'how many outputs a part drives without a chain is not in the data' };

    // not a limit but a weight the person sets for a chain: a joint of two products against outputs to spare, read by mixOf
    MEASURES.joint = { of: () => 0, fits: () => true, short: () => '', unknown: '' };

    MEASURES.standard = { of: (device) => device.provides?.nfc?.standards ?? null, fits: (standards, asked) => standards.includes(asked), short: (asked) => t('no reader of {0}', asked), unknown: 'the standards are not in the data' };

    // What a question can ask for: a board holding such a part that nobody asked for gives more than the kit needs.
    // the classes a person can ask for, by a question or by a role of the palette: a part of such a class on a board, not asked, is left unused
    const ASKABLE = new Set([...questions.flatMap((question) => [question.needs, ...(question.choices || []).map((choice) => choice.needs)]), ...roles.flatMap((group) => group.roles.map((role) => role.needs))].map((need) => need?.class));
    // what a board gives as a whole device, as Ethernet, and a person asks for by a role
    const ASKABLE_GIVEN = new Set(roles.flatMap((group) => group.roles).map((role) => role.needs?.provides).filter(Boolean));

    const roleOf = (id) => roles.flatMap((group) => group.roles).find((role) => role.id === id);

    // A part of the person's own: lines by name, those already soldered as name=GPIO, and a bus with an address if it has one.
    function ownWay(block) {
        const lines = [];
        const fixed = {};
        for (const token of String(block.lines ?? '').split(/[,;\s]+/).filter(Boolean)) {
            const [word, pin] = token.split('=');
            const line = word.toLowerCase().replace(/[^a-z0-9_]/g, '_') || `line_${lines.length + Object.keys(fixed).length + 1}`;
            if (/^\d+$/.test(pin ?? '')) fixed[line] = Number(pin);
            else lines.push(line);
        }
        const address = /^0x[0-9a-f]{2}$/i.test(block.address ?? '') ? block.address.toLowerCase() : undefined;
        return { lines, fixed, ...(KIT_BUSES[block.bus] ? { bus: block.bus } : {}), ...(address ? { address } : {}) };
    }

    // Blocks of one role and variant are one need: the same part for each, under the names of the blocks.
    function blocksInNeeds(blocks) {
        const same = new Map();
        for (const [at, block] of blocks.entries()) {
            // a part the person fixed makes a need of its own
            const key = block.role === OWN_PART ? `${OWN_PART}/${at}` : `${block.role}/${block.variant ?? ''}/${JSON.stringify(block.part ?? '')}/${JSON.stringify(block.asks ?? {})}`;
            same.set(key, [...(same.get(key) ?? []), block]);
        }
        return [...same.values()].map((group) => {
            const role = roleOf(group[0].role);
            if (role.id === OWN_PART) return { id: OWN_PART, own: true, count: 1, names: [group[0].name || undefined], title: group[0].name || t(role.text), way: ownWay(group[0]) };
            const variant = role.variants?.find((item) => item.id === group[0].variant);
            // a variant that asks the board for something else, as a gamepad by Bluetooth, is named by what the board must have
            const title = t(variant?.needs?.provides && variant.needs.provides !== role.needs?.provides ? variant.text : role.text);
            // a part fixed is a name, or what the person has of a chain: products and their counts in order from the board
            const listed = Array.isArray(group[0].part) ? group[0].part.map((item) => ({ part: item.part, count: item.count ?? 1 })) : undefined;
            return { ...(variant?.needs ?? role.needs ?? { role: role.id }), id: role.id, variant: group[0].variant, part: listed ? listed[0]?.part : group[0].part, ...(listed ? { members: listed } : {}), asks: group[0].asks, count: group.length, names: group.map((block) => block.name), title, way: variant?.way, wayTitle: variant && t(variant.text) };
        });
    }

    function holds(question, answers) {
        // on the canvas a block is what such a question waits for: the display block stands for the answer graphics
        const byBlock = question.limit?.of && (answers.blocks ?? []).some((block) => roleOf(block.role)?.needs?.class === question.limit.of);
        return Object.entries(question.when || {}).every(([id, value]) => (byBlock && answers[id] === undefined) || (value === true ? Boolean(answers[id]) : value.at_least ? answers[id] >= value.at_least : answers[id] === value));
    }

    const ppmOf = (setting) => Math.round((1e8 * (setting.hz - setting.wanted)) / setting.wanted) / 100;

    // What a source can make of an output, by its kind. key tells settings of one timer; whole: no jitter of a divider.
    const SETTINGS = {
        // The divider is A + B/256: with B = 0 it adds no jitter, otherwise periods alternate between A and A + 1 ticks
        // and only their average is the frequency.
        ledc(source, output, clock) {
            const unit = 2 ** source.fraction_bits;
            const widths = output.bits ? [output.bits] : Array.from({ length: source.counter_bits }, (_, i) => i + 1);
            return widths.filter((width) => width <= source.counter_bits).flatMap((bits) => {
                const exact = (clock * unit) / (output.hz * 2 ** bits);
                return [Math.round(exact), Math.floor(exact / unit) * unit, Math.ceil(exact / unit) * unit].filter((divider) => divider >= unit && divider < 2 ** source.divider_bits).map((divider) => ({
                    bits, key: `${bits}/${divider}`, hz: (clock * unit) / (divider * 2 ** bits), whole: divider % unit === 0, note: divider % unit === 0 ? 'a whole divider, no jitter of its own' : 'a fractional divider, periods differ',
                }));
            });
        },
        // A period in whole ticks after a whole prescaler, so no jitter of a divider, and it is not tied to a power of two.
        ticks(source, output) {
            const total = source.clock_hz / output.hz;
            const first = Math.max(1, Math.ceil(total / source.ticks_max));
            const prescales = Array.from({ length: PRESCALES_TRIED }, (_, i) => first + i).filter((prescale) => prescale <= source.prescale_max);
            return prescales.flatMap((prescale) => {
                const ticks = Math.round(total / prescale);
                const bits = Math.floor(Math.log2(ticks));
                if (ticks < 2 || ticks > source.ticks_max || (output.bits && output.bits > bits)) return [];
                return [{ bits, key: `${prescale}/${ticks}`, hz: source.clock_hz / prescale / ticks, whole: true, note: 'whole ticks, no jitter of their own' }];
            });
        },
        // xtal x (4 + sdm / 65536) / (2 x (o_div + 2)), then a whole divider of I2S; the multiplier stays in its range.
        apll(source, output) {
            if (output.bits) return [];
            const settings = [];
            for (let total = Math.ceil(source.min_hz / output.hz); total <= Math.floor(source.max_hz / output.hz) && total <= 1024; total++) {
                for (let div = 0; div < 32; div++) {
                    const multiplier = output.hz * total * 2 * (div + 2);
                    if (multiplier < source.multiplier_min_hz || multiplier > source.multiplier_max_hz) continue;
                    const sdm = Math.round((multiplier / source.xtal_hz - 4) * 65536);
                    const hz = (source.xtal_hz * (4 + sdm / 65536)) / (2 * (div + 2)) / total;
                    settings.push({ bits: 1, key: `${div}/${sdm}/${total}`, hz, whole: true, note: 'a whole divider after the audio PLL: low jitter by its purpose, no figure' });
                }
            }
            return settings;
        },
        // A crystal of the board on a pin: it gives its own frequency and nothing else.
        clock_out(source, output, _, board) {
            const crystals = source.signals.length ? Object.values(board.devices).map((device) => device.provides?.clock?.freq_mhz?.[0] * 1e6).filter(Boolean) : [];
            return crystals.filter((hz) => !output.bits && Math.abs(hz - output.hz) < 1).map((hz) => ({ bits: 1, key: `${hz}`, hz, whole: true, note: 'the crystal of the board' }));
        },
    };

    // The best setting: with a tolerance, no jitter first; with none, the nearest frequency.
    function settingOf(source, output, clock, board) {
        const allowed = (SETTINGS[source.kind]?.(source, output, clock, board) ?? []).map((setting) => ({ ...setting, wanted: output.hz }))
            .filter((setting) => (output.ppm === undefined || Math.abs(ppmOf(setting)) <= output.ppm) && (output.jitter !== 'none' || setting.whole));
        const near = (a, b) => Math.abs(ppmOf(a)) - Math.abs(ppmOf(b));
        return allowed.sort((a, b) => (output.ppm === undefined ? near(a, b) || b.whole - a.whole : b.whole - a.whole || near(a, b)) || a.bits - b.bits)[0];
    }

    // The sources for the outputs, first come: the clock of LEDC is one for all its timers, outputs of one setting share a timer,
    // and one that changes while it runs has a timer of its own, on a source that can do it.
    function outputsPlan(board, outputs) {
        const sources = board.mcu.facts.frequency_sources;
        if (!sources) return { problem: t('the sources of frequency of this chip are not in the data') };
        let problem;
        for (const clock of Object.values(sources.ledc.clocks_hz)) {
            const used = Object.fromEntries(Object.keys(sources).map((name) => [name, { timers: new Map(), lines: 0, pairs: false }]));
            const chosen = [];
            for (const [index, output] of outputs.entries()) {
                const lines = output.pins === 2 ? 2 : 1;
                const found = Object.entries(sources).map(([name, source]) => {
                    if (output.live && !source.can.includes('frequency')) return null;
                    if (lines === 2 && !source.pairs) return null;
                    const setting = settingOf(source, output, clock, board);
                    if (!setting) return null;
                    const key = output.live ? `live ${index}` : setting.key;
                    const room = used[name].timers.has(key) || used[name].timers.size < source.timers;
                    return room && used[name].lines + lines <= source.outputs ? { name, key, setting, lines } : null;
                }).find(Boolean);
                if (!found) break;
                if (!used[found.name].timers.has(found.key)) used[found.name].timers.set(found.key, found.setting);
                used[found.name].lines += lines;
                used[found.name].pairs ||= lines === 2;
                chosen.push({ ...found, timer: [...used[found.name].timers.keys()].indexOf(found.key) });
            }
            if (chosen.length === outputs.length) return { sources, used, chosen };
            problem = t('this chip does not give output {0}: {1} Hz', chosen.length + 1, outputs[chosen.length].hz);
        }
        return { problem };
    }

    // What the answers ask of a part of this kind: a class may have several questions.
    // How a value of the data of a part meets what a block asks, by the fits of its question.
    const FITS = {
        up_to: (range, asked) => [].concat(range).at(-1) >= asked,
        down_to: (range, asked) => [].concat(range)[0] <= asked,
        at_least: (value, asked) => value >= asked,
        at_most: (value, asked) => value <= asked,
        includes: (list, asked) => [].concat(list).includes(asked),
        is: (value, asked) => value === asked,
    };

    // a question of a measure limits this class, and this variant when it names some, or a need of no variant: of and variant
    // may each be a list
    const ofClass = (question, cls, variant) => [].concat(question.limit?.of ?? []).includes(cls) && (!question.limit.variant || !variant || [].concat(question.limit.variant).includes(variant));

    // an answer of a block that asks something: none for an empty field or "any"
    const blockAnswer = (value) => (value === undefined || value === null || value === '' || value === 'any' ? undefined : value);

    // the depth of color a block asks of its display, a number; undefined for any
    const DEPTH = questions.find((item) => item.limit?.measure === 'depth_bits')?.id;
    const depthAsked = (need) => (DEPTH && blockAnswer(need.asks?.[DEPTH]) !== undefined ? Number(need.asks[DEPTH]) : undefined);

    // the letter a block groups its part by: the blocks of one letter take one edge of the board, of other letters other edges
    const SIDE = questions.find((item) => item.asked === 'block' && !item.limit && item.id === 'side')?.id;
    const sideOf = (need) => (SIDE ? blockAnswer(need?.asks?.[SIDE]) : undefined);
    // the sides before the IO MUX of a host, or after it, as the ranks of their judgements order them
    const rankOf = (kind) => Math.min(...judgementsOf(kind).map((judgement) => judgement.rank ?? Infinity));
    const sidesFirst = () => rankOf('sides') <= rankOf('prefer_pins');
    const EDGES = ['top', 'right', 'bottom', 'left'];

    // Where the GPIOs and the supplies of a board come out: places, a GPIO to its connector, its contact from 1 and the
    // edge of its run as the picture of the board names it; names, each edge to the supplies and grounds on it; spots, a
    // supply on an edge to its connector and contact.
    function edgesOf(board) {
        const places = new Map();
        const names = new Map();
        const spots = new Map();
        for (const [name, connector] of Object.entries(board.connectors || {})) {
            const runs = (connector.edges || []).flatMap((run) => Array.from({ length: run.count }, (_, at) => ({ edge: run.edge, at })));
            (connector.pins || []).forEach((pin, i) => {
                const run = runs[i] ?? {};
                const gpio = typeof pin === 'object' ? pin?.gpio : typeof pin === 'number' ? pin : undefined;
                if (gpio !== undefined && !places.has(gpio)) places.set(gpio, { connector: name, contact: i + 1, ...run });
                if (typeof pin === 'string' && run.edge) names.set(run.edge, new Set([...(names.get(run.edge) ?? []), pin]));
                if (typeof pin === 'string' && run.edge && !spots.has(`${run.edge} ${pin}`)) spots.set(`${run.edge} ${pin}`, { connector: name, contact: i + 1, edge: run.edge });
            });
        }
        return { places, names, spots };
    }

    // The plans of the sides a kit tries, best first: each letter of the picks to an edge of its own, an edge where the
    // supplies of the letter come out too before one where they do not, then the edge with more free pins. No letter, or
    // a board whose data names no edges: one plan with no sides.
    function sidePlans(board, picks) {
        const letters = [...new Set(picks.map((pick) => sideOf(pick.need)).filter(Boolean))].sort();
        const { places, names } = edgesOf(board);
        const free = freePins(board);
        const room = (edge) => free.filter((pin) => places.get(pin)?.edge === edge).length;
        const edges = EDGES.filter((edge) => room(edge));
        if (!letters.length || !edges.length) return [new Map()];
        const supplies = (letter) => picks.filter((pick) => sideOf(pick.need) === letter && pick.module?.power)
            .flatMap((pick) => Object.values(supplyOf(board, pick.module) ?? {}));
        const order = (letter) => {
            const fed = (edge) => supplies(letter).every((name) => names.get(edge)?.has(name)) && (!supplies(letter).length || names.get(edge)?.has('GND'));
            return [...edges].sort((a, b) => fed(b) - fed(a) || room(b) - room(a));
        };
        const plans = [];
        const assign = (at, taken) => {
            if (plans.length >= 24) return;
            if (at === letters.length) return void plans.push(new Map(taken));
            for (const edge of order(letters[at]).filter((item) => ![...taken.values()].includes(item))) assign(at + 1, new Map([...taken, [letters[at], edge]]));
        };
        assign(0, new Map());
        return plans.length ? plans : [new Map()];
    }

    // the way a part with no bus is wired for a need: the first that gives the swing its block asks, else the first
    const SWING = questions.find((item) => item.limit?.measure === 'swing_v')?.id;
    const wayOf = (device, need) => {
        const swing = SWING && blockAnswer(need?.asks?.[SWING]) !== undefined ? Number(need.asks[SWING]) : undefined;
        return (swing !== undefined && device.ways.find((way) => (way.gives?.swing_v ?? 0) >= swing)) || device.ways[0];
    };

    function limitsOf(need, wanted) {
        // a question asked of each block takes the block's answer first, the one of the page after it (an older answer)
        const answerOf = (item) => (item.asked === 'block' && blockAnswer(need.asks?.[item.id]) !== undefined ? need.asks[item.id] : wanted.limits[item.limit.measure]);
        const measured = questions.filter((item) => item.limit?.measure && ofClass(item, need.class, need.variant) && answerOf(item) !== undefined)
            .map((item) => ({ asked: answerOf(item), fits: (value, asked) => value >= asked, ...MEASURES[item.limit.measure] }));
        // what a block asks of the data of its part: a value not in the data leaves the part in, as an unknown
        const asked = Object.entries(need.asks ?? {}).filter(([, value]) => blockAnswer(value) !== undefined).map(([id, value]) => {
            const question = questions.find((item) => item.id === id && item.limit?.field);
            // an answer kept from another variant of the block does not act: a CO2 range does not limit a VOC sensor
            if (!question || (question.limit.variant && question.limit.variant !== need.variant)) return null;
            const wantedValue = question.limit.fits === 'includes' ? question.limit.value : value;
            return { asked: wantedValue, of: (device) => valueAt(device, question.limit.field) ?? null, fits: FITS[question.limit.fits],
                short: () => t('{0} {1}: no part of the catalog', t(question.text), value), unknown: t('{0}: not in the data', t(question.text)) };
        });
        return [...measured, ...asked.filter(Boolean)];
    }

    const meets = (limit, device) => Boolean(limit.soft) || limit.of(device) === null || limit.fits(limit.of(device), limit.asked);

    // What the answers ask for: {class or provides, count, title}, and the numbers that limit them.
    function wantedBy(given) {
        const blocks = given.blocks ?? [];
        const answers = { ...given };
        const needs = blocksInNeeds(blocks);
        for (const question of questions) if (blocks.length && question.type === 'count') answers[question.id] = blocks.filter((block) => roleOf(block.role)?.needs?.class === question.needs?.class).length;
        const limits = {};
        for (const question of questions) {
            const answer = answers[question.id];
            if (!holds(question, answers) || answer === undefined || answer === null || answer === '' || answer === false || answer === 0) continue;
            const choice = (question.choices || []).find((item) => item.value === answer);
            if (question.limit) {
                if (answer !== 'any') limits[question.limit.measure] = answer;
                continue;
            }
            const need = choice ? choice.needs : question.needs;
            if (need && !blocks.length) needs.push({ ...need, count: question.type === 'count' ? Math.min(Math.floor(answer), question.max ?? answer) : 1, title: t(choice ? choice.text : question.text) });
        }
        const outputs = (answers.outputs || []).filter((output) => output.hz > 0).map((output) => ({ ...output, ppm: output.ppm === '' ? undefined : output.ppm, bits: output.kind === 'pwm' ? output.bits : undefined }));
        const unanswered = questions.filter((question) => MEASURES[question.limit?.measure]?.unanswered && holds(question, answers) && limits[question.limit.measure] === undefined);
        // what the person has already: a board or a module of the catalog by its name, with how many
        const have = new Map();
        for (const item of answers.have ?? []) if (item?.part) have.set(item.part, (have.get(item.part) ?? 0) + Math.max(1, Math.floor(item.count ?? 1)));
        return { needs, limits, unanswered, outputs, currency: answers.currency || KIT_CURRENCY, installed: answers.installed ?? null, have };
    }

    const rateOf = (currency) => (currency === KIT_CURRENCY ? 1 : rates[currency]);

    // An offer in a currency, null when one of the two has no rate. A low of 0 is a bound, "less than 3": it counts as that bound.
    function converted(offer, currency) {
        const rate = rateOf(currency) / rateOf(offer.currency);
        return rate ? [(offer.range[0] || offer.range[1]) * rate, offer.range[1] * rate] : null;
    }

    function median(values) {
        const sorted = [...values].sort((a, b) => a - b);
        const middle = Math.floor(sorted.length / 2);
        return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    }

    // What is sold by the pack is bought by the pack: at least the smallest quantity of the offers.
    const boughtOf = (price, count) => Math.max(count, Math.min(...Object.values(price).map((offer) => offer.qty ?? 1)));

    // The price of one piece when count are wanted, as board_bom.py counts it. Each shop gives its offers of the largest
    // quantity the pieces bought reach: reports of its sellers, kept all, a named seller by the newest report. The shop
    // counts their median, the low and the high apart (Anton, 2026-11-04); the cheapest shop gives the low, the dearest the
    // high. Counted once for a price, a currency and a count: nothing changes a price in place, a changed catalog brings
    // new objects.
    const ranged = new WeakMap();
    function rangeOf(price, currency, count = 1) {
        if (!price || !Object.keys(price).length) return null;
        if (!ranged.has(price)) ranged.set(price, new Map());
        const known = ranged.get(price);
        const key = `${currency}/${count}`;
        if (!known.has(key)) known.set(key, counted(price, currency, boughtOf(price, count)));
        return known.get(key);
    }

    function counted(price, currency, bought) {
        const tiers = new Map();
        for (const offer of Object.values(price)) {
            const qty = offer.qty ?? 1;
            const tier = tiers.get(offer.shop ?? '');
            if (qty > bought || !converted(offer, currency) || (tier && qty < tier.qty)) continue;
            if (!tier || qty > tier.qty) tiers.set(offer.shop ?? '', { qty, offers: [offer] });
            else tier.offers.push(offer);
        }
        const ranges = [...tiers.values()].map(({ offers }) => {
            const newest = new Map();
            for (const offer of offers.filter((item) => item.seller)) {
                if (!newest.has(offer.seller) || offer.date > newest.get(offer.seller).date) newest.set(offer.seller, offer);
            }
            const reports = [...offers.filter((item) => !item.seller), ...newest.values()].map((offer) => converted(offer, currency));
            return [median(reports.map((range) => range[0])), median(reports.map((range) => range[1]))];
        });
        return ranges.length ? [Math.min(...ranges.map((range) => range[0])), Math.max(...ranges.map((range) => range[1]))] : null;
    }

    // What one piece of a role costs at least: the cheapest chip of the catalog with a price that gives it, by role and variant.
    let pieces = null;
    function piecePrices() {
        const by = new Map();
        for (const chip of Object.values(catalog.devices)) {
            const range = rangeOf(chip.price, KIT_CURRENCY);
            if (!range || range[0] <= 0) continue;
            for (const [role, given] of Object.entries(chip.provides ?? {})) {
                for (const key of [...(given?.variant ? [`${role}/${given.variant}`] : []), role]) by.set(key, Math.min(by.get(key) ?? Infinity, range[0]));
            }
        }
        return by;
    }

    // What a part of a role costs at least by a module: the cheapest module priced for it, a pack counted by the piece. For a part
    // whose chip has no price and no chip of its role has one; a price of nothing is no price (Anton, 2026-11-03).
    let cheapest = null;
    function modulePrices() {
        const by = new Map();
        const add = (key, value) => by.set(key, Math.min(by.get(key) ?? Infinity, value));
        for (const module of Object.values(catalog.modules)) {
            const range = rangeOf(module.price, KIT_CURRENCY);
            if (!range || range[0] <= 0) continue;
            const each = range[0]; // the price of one piece, of a pack too
            const keys = new Set();
            for (const device of Object.values(module.devices ?? {})) {
                const type = catalog.devices[device.chip] ?? {};
                for (const [role, given] of Object.entries({ ...type.provides, ...device.provides })) {
                    keys.add(role);
                    if (given?.variant) keys.add(`${role}/${given.variant}`);
                }
                for (const item of [].concat(device.class ?? type.class ?? [])) keys.add(`class:${item}`);
            }
            for (const key of keys) add(key, each);
            add('', each);
        }
        return by;
    }
    // a part of a board nobody asked for, in money: its role and variant, its role, its class, or any part
    function worthOf(device) {
        // a part whose chip has a price by the piece is worth that many of it: a module of its role counts a ring for one LED;
        // in a chain the units of its driver are not chips, as the digits of a MAX7219, eight to a chip
        const many = device.chain ? Math.ceil(((device.config?.count ?? 1) * (device.chain.unit ?? device.chain.per)) / device.chain.per) : device.config?.count ?? device.count ?? 1;
        const own = rangeOf(device.price ?? catalog.devices[device.chip]?.price, KIT_CURRENCY);
        if (own && own[0] > 0) return Math.max(LEAST_WORTH, own[0] * many); // the lowest of its offers, as the cheapest of a role is
        const roleKeys = Object.entries(device.provides ?? {}).filter(([role]) => roleOf(role)).flatMap(([role, given]) => [...(given?.variant ? [`${role}/${given.variant}`] : []), role]);
        // a part with no chip of its own weighs the cheapest chip of the catalog that gives its role and variant, by the piece
        pieces ??= piecePrices();
        const piece = roleKeys.find((key) => pieces.has(key));
        if (piece) return Math.max(LEAST_WORTH, pieces.get(piece) * many);
        // then the cheapest module of its role, its class or of all, by the piece: a part with no price is still not free (Anton)
        cheapest ??= modulePrices();
        const keys = [...roleKeys, ...(device.classes ?? []).filter((item) => item !== 'other').map((item) => `class:${item}`), ''];
        return Math.max(LEAST_WORTH, (cheapest.get(keys.find((key) => cheapest.has(key))) ?? 0) * many);
    }

    // Resolving every module for every board is the slowest thing here. It holds for one solve: the catalog can change between them.
    const modulesOfNeed = new Map();
    function modulesWith(need) {
        const key = JSON.stringify([need.class, need.where, need.role, need.id, need.variant]);
        if (!modulesOfNeed.has(key)) modulesOfNeed.set(key, findModules(need));
        return modulesOfNeed.get(key);
    }

    function findModules(need) {
        const found = [];
        for (const name of Object.keys(catalog.modules).sort()) {
            let module;
            try {
                module = loader.resolve(catalog.modules[name]);
            } catch {
                continue;
            }
            for (const [part, device] of Object.entries(module.devices)) if (isClass(device, need)) found.push({ name, part, device, title: module.title ?? name, power: module.power || [] });
        }
        // what we checked first, then what has a price: a kit tries the first few
        const rank = ({ name }) => (catalog.modules[name].origin ? 2 : 0) + (catalog.modules[name].price ? 0 : 1);
        return found.sort((a, b) => rank(a) - rank(b));
    }

    // The pins left to wire to: free and with nothing to remember about them. A board with connectors in its data gives only what comes out.
    // The harm of a level on a strapping pin, read from what the datasheet gives: the voltage of the flash, or a level the start of the
    // program (the row spi_boot of the table of boot modes) names, is run; a level only another row names is download; a pin
    // whose level the footnote says decides nothing, or which no row names, is none. A pin the datasheet does not describe: unknown.
    function bootHarm(board, pin, entry) {
        if (!entry.boot) return 'unknown';
        if (entry.boot.selects.includes('flash voltage')) return 'run';
        if (entry.boot.decides === false) return null;
        const modes = board.mcu.facts.gpio.boot_modes ?? {};
        const named = (row) => row?.[pin] !== undefined && row[pin] !== 'any';
        if (named(modes.spi_boot)) return 'run';
        return Object.entries(modes).some(([mode, row]) => mode !== 'spi_boot' && named(row)) ? 'download' : null;
    }

    // keep_out of strapping pins: given only when a judgement lets its harm go; an unknown one never
    function strappingGiven(board, pin, entry) {
        const harm = bootHarm(board, pin, entry);
        return harm !== 'unknown' && judgementsOf('keep_out').some((judgement) => judgement.what === 'strapping' && !judgement.harm.includes(harm));
    }

    // The pins nobody has that a line can take: free, an output, out of the board, with no note that keeps them out.
    function openPins(board) {
        const map = pinMap(board);
        const hasOutside = Object.values(map).some((entry) => entry.connectors.length);
        // the note of a strapping pin is keep_out's to weigh, a note that is a cost note_cost's; any other keeps a pin out
        const costs = new Set(judgementsOf('note_cost').map((judgement) => judgement.note));
        const notes = (entry) => (entry.notes || []).filter((note) => !note.startsWith('Strapping pin') && !costs.has(note));
        return Object.entries(map).filter(([, entry]) => entry.state === 'free' && !entry.input_only && !notes(entry).length && (!hasOutside || entry.connectors.length));
    }

    function freePins(board) {
        return openPins(board).filter(([pin, entry]) => !entry.strapping || strappingGiven(board, pin, entry)).map(([pin]) => +pin);
    }

    // keep_out unless logic none: the strapping pins kept out that the lines of a part holding nothing may have all the same
    function quietPins(board) {
        if (!judgementsOf('keep_out').some((judgement) => judgement.what === 'strapping' && judgement.unless?.logic === 'none')) return [];
        return openPins(board).filter(([pin, entry]) => entry.strapping && !strappingGiven(board, pin, entry) && bootHarm(board, pin, entry) !== 'unknown').map(([pin]) => +pin);
    }

    // A board with connectors in its data: a line is of use only if it comes out.
    function reaches(board, kind, own) {
        const map = pinMap(board);
        if (!Object.values(map).some((entry) => entry.connectors.length)) return true;
        return KIT_BUSES[kind].lines.every((line) => map[board.buses[kind][own][line]?.gpio]?.connectors.length);
    }

    // prefer_pins: the pins a judgement names for a host, from a field of the chip (its IO MUX), when every line asked is free
    function ownPins(board, kind, own, lines, pins) {
        for (const judgement of judgementsOf('prefer_pins')) {
            const named = judgement.bus === kind && board.mcu.facts[judgement.pins]?.[kind]?.[own];
            if (named && lines.every((line) => pins.includes(named[line]))) return named;
        }
        return null;
    }

    // The cs of a device on a host: the one a judgement names for the host while it is free, else the next free pin.
    function selectOf(board, kind, own, pins) {
        const cs = ownPins(board, kind, own, [], pins)?.cs;
        return cs !== undefined && pins.includes(cs) ? pins.splice(pins.indexOf(cs), 1)[0] : pins.shift();
    }

    function hostNames(board, host) {
        const count = board.mcu.facts.hosts?.[host] ?? 0;
        // SPI1 belongs to the flash, UART0 to the console
        if (host === 'spi') return Array.from({ length: Math.max(count - 1, 0) }, (_, i) => `spi${i + 2}`);
        return Array.from({ length: count }, (_, i) => `${host}${i}`).slice(host === 'uart' ? 1 : 0);
    }

    function lineMv(board, name) {
        const step = (board.power || []).find((item) => item.name === name);
        if (!step) return null;
        return step.mv ?? (step.inputs?.length ? lineMv(board, step.inputs[0].name) : null);
    }

    const namesLines = (board) => (board.power || []).some((line) => line.name);

    // The line of the board for each step a module takes from it, the lowest that fits; null when a step has none.
    // A board whose data names no lines says nothing: the kit counts that as an unknown.
    function supplyOf(board, module) {
        const contacts = Object.values(board.connectors || {}).flatMap((connector) => connector.pins || []);
        const supply = {};
        for (const step of module.power.filter((item) => item.source === 'connector' && item.volts)) {
            const [low, high] = [].concat(step.volts, step.volts);
            const lines = (board.power || [])
                .filter((line) => line.name && (!contacts.length || contacts.includes(line.name)))
                .map((line) => [line.name, lineMv(board, line.name)])
                .filter(([, mv]) => mv !== null && mv >= low * 1000 && mv <= high * 1000)
                .sort((a, b) => a[1] - b[1]);
            if (!lines.length && !namesLines(board)) continue;
            if (!lines.length) return null;
            supply[step.name] = lines[0][0];
        }
        return supply;
    }

    // The bus of a kind to join: one the board has and a display does not hold, or a new one on a free host.
    function busOf(board, kind, pins, added, hz, alone, kept, silent, placed, spread, reach = {}) {
        const spec = KIT_BUSES[kind];
        const room = (own) => !spec.most || Object.values(board.devices).filter((device) => `${kind}.${own}` in (device.on || {})).length + (placed[own] ?? 0) < spec.most;
        const named = Object.keys(board.buses?.[kind] || {});
        const held = (own) => Object.values(board.devices).some((device) => `${kind}.${own}` in (device.on || {}) && (spec.fixed || isDisplay(device)));
        if (spec.fixed) return named.find((own) => !held(own)) ?? { problem: t('no free {0} bus on this board', kind.toUpperCase()) };
        const sharing = !spec.alone && !alone;
        // a host of its own: a free host of the chip, its lines from the free pins
        const fresh = () => {
            const kinds = Object.keys(KIT_BUSES).filter((other) => KIT_BUSES[other].host === spec.host);
            const taken = new Set(kinds.flatMap((other) => [...Object.keys(board.buses?.[other] || {}), ...Object.keys(added[other] || {})]));
            const own = hostNames(board, spec.host).find((name) => !taken.has(name));
            if (!own) return { problem: t('no free {0} host on this board: {1}', spec.host.toUpperCase(), [...taken].join(', ') || t('it has none')) };
            const lines = spec.lines.filter((line) => !(silent && line === 'miso')); // a device with no line back leaves it unwired
            if (pins.length < lines.length + (spec.select ? 1 : 0)) return { problem: shortOfPins(lines.length, pins.length) };
            const named = ownPins(board, kind, own, lines, reach.iomux ?? pins);
            // above the clock of the GPIO matrix of the chip only the IO MUX runs the host
            const matrix = board.mcu.facts.limits?.spi_matrix_mhz;
            if (kind === 'spi' && !named && hz && matrix && hz > matrix * 1e6 && board.mcu.facts.iomux?.spi?.[own]) {
                return { problem: t('{0} at {1} MHz needs the pins of its IO MUX: through the GPIO matrix the chip runs SPI up to {2} MHz', own.toUpperCase(), hz / 1e6, matrix) };
            }
            if (named) for (const line of lines) {
                const at = pins.indexOf(named[line]);
                if (at >= 0) pins.splice(at, 1);
                reach.taken?.(named[line]);
            }
            added[kind] = { ...added[kind], [own]: { ...Object.fromEntries(spec.lines.map((line) => [line, lines.includes(line) ? (named ? named[line] : pins.shift()) : 'nc'])), ...(hz ? { hz } : {}) } };
            if (alone) kept.add(own);
            return own;
        };
        // SPI parts each take a host of their own while the chip has one, so their tasks run apart (Anton: the terminal and
        // dotview-clock are built so); a host is shared when none is left or its pins are not there
        if (kind === 'spi' && sharing && spread) {
            const own = fresh();
            if (typeof own === 'string') return own;
        }
        const open = sharing && Object.keys(added[kind] || {}).find((own) => !kept.has(own) && room(own));
        if (open) return open;
        const shared = sharing && named.find((own) => !held(own) && reaches(board, kind, own) && room(own));
        if (shared) return shared;
        return fresh();
    }

    // How good the antenna of a radio of the board is by its design, 0 to 10, the best of the radios that give it; null when no data
    // says. Shown, not ranked: a device a metre from its access point does not care, and the model weighs it against the task.
    function antennaQuality(board, need) {
        const known = board.provides[need.provides].by.map((source) => (source === 'mcu' ? board.mcu.antenna : board.devices[source]?.antenna)?.quality).filter((value) => value !== undefined);
        return known.length ? Math.max(...known) : null;
    }

    // Whether an antenna outside the board can serve a radio of the board: the best of the radios that give it.
    function externalAntenna(board, need) {
        const ORDER = ['yes', 'do', 'unknown', 'no'];
        const ways = board.provides[need.provides].by.map((source) => {
            const antenna = source === 'mcu' ? board.mcu.antenna : board.devices[source]?.antenna;
            if (!antenna) return ['unknown', t('{0}: its antenna is not in the data', need.title)];
            if (antenna.kind !== 'on_board') return ['yes', t('{0}: its antenna is outside the board, on a {1}', need.title, antenna.connector ?? t(antenna.kind))];
            const { external } = antenna;
            if (!external) return ['no', t('{0}: only the antenna on the board', need.title)];
            if (external.by === 'resistor') return ['do', t('{0}: an antenna goes on its {1} once {2} is moved to it', need.title, external.connector, external.ref)];
            return ['do', t('{0}: an antenna goes on its {1}, and the program sets {2} to it', need.title, external.connector, external.ref)];
        });
        return ways.sort((a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]))[0];
    }

    // The addresses a part can have on I2C, the first as it comes.
    function addressesOf(device) {
        const on = { ...catalog.devices[device.chip]?.on?.i2c, ...device.on?.i2c };
        return on.address ? [on.address] : on.address_try ?? [];
    }

    // What the wiring of a part says of its address: the first of its list that is free on the bus. An imported list can be
    // short, so with none free the part keeps no address and the kit says so. A checked list is left to the rule that refuses.
    function addressFor(device, held) {
        const list = addressesOf(device);
        const free = list.find((value) => !held.has(value));
        if (free) held.add(free);
        if (free && free !== list[0]) return { address: free };
        if (!free && list.length && catalog.devices[device.chip]?.checked?.address?.level === 'extracted') return { address_try: [] };
        return {};
    }

    // A project of a board and the modules picked, or {problem} when the pins or the hosts run out.
    // The chips of the chain of a way: as many as the outputs asked take, one when nothing is asked.
    function chainCount(pick) {
        const chip = catalog.devices[pick.way.part];
        const asked = blockAnswer(pick.need.asks?.[CHAIN_QUESTION]);
        return chip?.chain && asked !== undefined ? Math.ceil(asked / chip.chain.per) : 1;
    }

    // The product of a use in a project: a module and its count, or a chain of several in order.
    const productOf = (pick) => (pick.members
        ? { chain: pick.members.map((member) => ({ module: member.module.name, ...(member.count > 1 ? { count: member.count } : {}) })) }
        : { module: pick.module.name, ...(pick.count > 1 ? { count: pick.count } : {}) });

    // Each product a pick buys, with its count: the members of a chain, or its module.
    const boughtBy = (pick) => pick.members ?? [{ module: pick.module, count: pick.count ?? 1 }];

    function projectOf(name, board, picks, unused, spread = true, sides = new Map()) {
        // the pins a part of the person's own is soldered to are out of what the kit hands out
        const soldered = picks.flatMap((pick) => Object.values(pick.way?.fixed ?? {}));
        const open = freePins(board);
        const lost = picks.find((pick) => Object.values(pick.way?.fixed ?? {}).some((pin) => !open.includes(pin)));
        if (lost) {
            const map = pinMap(board);
            // what holds the pin, in the words of the data
            const holder = (entry) => !entry ? t('not a GPIO of this chip') : entry.owners.length || entry.notes?.length ? [...entry.owners, ...(entry.notes ?? [])].join(', ') : entry.input_only ? t('input only') : entry.strapping ? t('a strapping pin') : t('does not come out');
            const pins = Object.values(lost.way.fixed).filter((pin) => !open.includes(pin)).map((pin) => `GPIO ${pin} (${holder(map[pin])})`);
            return { problem: t('{0} is soldered to {1}, which this board does not leave free', lost.module.title, pins.join(', ')) };
        }
        // the pins a judgement names for a host the board does not wire yet go last, so a new host can take them all
        const free = open.filter((pin) => !soldered.includes(pin));
        const quiet = quietPins(board).filter((pin) => !soldered.includes(pin));
        const theirs = new Set(judgementsOf('prefer_pins').flatMap((judgement) => hostNames(board, KIT_BUSES[judgement.bus].host)
            .filter((own) => !Object.values(board.buses ?? {}).some((named) => own in named))
            .flatMap((own) => [...KIT_BUSES[judgement.bus].lines, 'cs'].map((line) => board.mcu.facts[judgement.pins]?.[judgement.bus]?.[own]?.[line]))));
        const order = [...free.filter((pin) => !theirs.has(pin)), ...free.filter((pin) => theirs.has(pin))];
        // the sides: a pick of a letter takes the free pins of its edge, in their order along it; one of no letter leaves
        // the edges of the letters to them, last
        const { places } = edgesOf(board);
        const used = new Set();
        const sideEdges = new Set(sides.values());
        const along = (a, b) => (places.get(a).connector < places.get(b).connector ? -1 : places.get(a).connector > places.get(b).connector ? 1 : places.get(a).at - places.get(b).at);
        const poolOf = (pick, list) => {
            const left = list.filter((pin) => !used.has(pin));
            const edge = sides.get(sideOf(pick.need));
            if (edge) return left.filter((pin) => places.get(pin)?.edge === edge).sort(along);
            return [...left.filter((pin) => !sideEdges.has(places.get(pin)?.edge)), ...left.filter((pin) => sideEdges.has(places.get(pin)?.edge))];
        };
        const buses = {};
        const modules = { ...unused.modules };
        const devices = { ...unused.devices };
        const kept = new Set(); // the buses a display of its own holds
        const held = {}; // the addresses taken on each I2C bus
        const placed = {}; // the parts of this project on each host
        const shared = {}; // the lines the chains of a need have in common
        // one display is the primary: the board's, else the first of the blocks
        let primaryTaken = Object.values(board.devices).some((device) => device.config?.primary);
        // by the order of the blocks, whatever order the picks are wired in
        const seconds = new Set();
        for (const pick of picks.filter((item) => !item.way && item.module.device.config?.primary)) {
            if (primaryTaken) seconds.add(pick);
            primaryTaken = true;
        }
        // one pick on its pool: pins, the free pins it may take, spare the strapping pins a part holding nothing may have, reach
        // where the IO MUX of a new host may come from; returns a problem, or null
        const place = (pick, pins, spare, reach) => {
            if (pick.way) {
                // lines a chain shares with the others of its need, as the data and clock of shift registers
                const common = shared[pick.need.id]?.pins ?? {};
                const own = pick.way.lines.filter((line) => !(line in common));
                if (pins.length < own.length) return { problem: shortOfPins(own.length, pins.length) };
                // the first lines of a way are those read by ADC1
                const analog = board.mcu.facts.gpio.adc1 ?? [];
                const read = pins.filter((pin) => analog.includes(pin)).slice(0, pick.way.adc ?? 0);
                if (read.length < (pick.way.adc ?? 0)) return { problem: t('pins of ADC1: {0} needed, {1} free on this board', pick.way.adc, read.length) };
                for (const pin of read) pins.splice(pins.indexOf(pin), 1);
                // a way that names its chip writes the chips of its chain, so that the goods and the price count them
                const chip = !pick.need.output && !pick.module.own && pick.way.part && catalog.devices[pick.way.part] ? pick.way.part : null;
                // the part takes the class of its role, and a line its level that means on, so the glue starts it as such
                const placedPin = (line, pin) => (pick.way.active?.[line] ? { gpio: pin, active: pick.way.active[line] } : pin);
                devices[pick.use] = { ...(chip ? { chip, count: chainCount(pick) } : { class: roleOf(pick.need.id)?.class ?? 'other' }),
                    pins: { ...common, ...pick.way.fixed, ...Object.fromEntries(own.map((line, i) => [line, placedPin(line, i < read.length ? read[i] : pins.shift())])) } };
                if (devices[pick.use].count === 1) delete devices[pick.use].count;
                if (!Object.keys(devices[pick.use].pins).length) delete devices[pick.use].pins;
                if (pick.way.bus) {
                    const bus = busOf(board, pick.way.bus, pins, buses, undefined, false, kept, false, placed, spread, reach);
                    if (bus.problem) return bus;
                    placed[bus] = (placed[bus] ?? 0) + 1;
                    const wires = KIT_BUSES[pick.way.bus].select ? { cs: selectOf(board, pick.way.bus, bus, pins) } : {};
                    if (wires.cs === undefined && KIT_BUSES[pick.way.bus].select) return { problem: shortOfPins(1, 0) };
                    devices[pick.use].on = { [`${pick.way.bus}.${bus}`]: { ...wires, ...(pick.way.address ? { address: pick.way.address } : {}) } };
                }
                if (pick.way.shared) shared[pick.need.id] = { pins: Object.fromEntries(pick.way.shared.map((line) => [line, devices[pick.use].pins[line]])), uses: [...(shared[pick.need.id]?.uses ?? []), pick.use] };
                return null;
            }
            // a part with no bus takes the lines of its way
            if (pick.module.device.ways) {
                const { lines } = wayOf(pick.module.device, pick.need);
                // a part that holds nothing on its lines takes a strapping pin when the free ones run out
                const extra = pick.module.device.logic === 'none' ? spare : [];
                if (pins.length + extra.length < lines.length) return { problem: shortOfPins(lines.length, pins.length + extra.length) };
                modules[pick.use] = { ...productOf(pick), pins: Object.fromEntries(lines.map((line) => [line, pins.length ? pins.shift() : extra.shift()])) };
                return null;
            }
            const alone = isDisplay(pick.module.device) && KIT_BUSES[pick.transport].select;
            const own = busOf(board, pick.transport, pins, buses, pick.module.device.on?.[pick.transport]?.hz, alone, kept, alone && pick.module.device.logic === 'none', placed, spread, reach);
            if (own.problem) return own;
            placed[own] = (placed[own] ?? 0) + 1;
            const wires = {};
            if (KIT_BUSES[pick.transport].select) {
                if (!pins.length) return { problem: shortOfPins(1, 0) };
                wires.cs = selectOf(board, pick.transport, own, pins);
            }
            if (pick.transport === 'i2c') {
                held[own] ??= new Set(Object.values(board.devices).flatMap((device) => device.on?.[`i2c.${own}`]?.address ?? device.on?.[`i2c.${own}`]?.address_try?.[0] ?? []));
                Object.assign(wires, addressFor(pick.module.device, held[own]));
            }
            const lines = catalog.devices[pick.module.device.chip]?.on?.[pick.transport]?.lines || [];
            if (pins.length < lines.length) return { problem: shortOfPins(lines.length, pins.length) };
            const needed = Object.fromEntries(lines.map((line) => [line, pins.shift()]));
            const supply = supplyOf(board, pick.module);
            // the board keeps its own display as the primary one
            const second = seconds.has(pick);
            // a display of the module started at another depth than its data's
            const depth = depthAsked(pick.need);
            const config = { ...(second ? { primary: false } : {}), ...(depth !== undefined && pick.module.device.config?.depth_bits !== depth ? { depth_bits: depth } : {}) };
            modules[pick.use] = { ...productOf(pick), on: { [`${pick.transport}.${own}`]: wires }, ...(lines.length ? { pins: needed } : {}), ...(Object.keys(supply).length ? { supply } : {}), ...(Object.keys(config).length ? { config } : {}) };
            return null;
        };
        // the picks of a side first, so that one of no side does not take the pins of their edges
        for (const pick of [...picks.filter((item) => sides.has(sideOf(item.need))), ...picks.filter((item) => !sides.has(sideOf(item.need)))]) {
            const pins = poolOf(pick, order);
            const spare = poolOf(pick, quiet);
            const before = [...pins, ...spare];
            // the sides before the IO MUX: a host of a letter is on it only when its pins are on the edge; after it, from all free pins
            const reach = { iomux: sides.has(sideOf(pick.need)) && !sidesFirst() ? order.filter((pin) => !used.has(pin)) : pins, taken: (pin) => used.add(pin) };
            const problem = place(pick, pins, spare, reach);
            for (const pin of before) if (!pins.includes(pin) && !spare.includes(pin)) used.add(pin);
            if (problem) return problem;
        }
        const sharedPins = Object.fromEntries(Object.entries(shared).filter(([, chain]) => chain.uses.length > 1).flatMap(([id, chain]) => Object.entries(chain.pins).map(([line, pin]) => [`${id}_${line}`, { line: pin, devices: chain.uses }])));
        return { ...KIT_FORMAT, kind: 'project', name: 'kit', extends: name, title: `${board.title} with modules`, ...(Object.keys(buses).length ? { buses } : {}), ...(Object.keys(devices).length ? { devices } : {}), ...(Object.keys(sharedPins).length ? { shared_pins: sharedPins } : {}), modules };
    }

    function* product(lists) {
        if (!lists.length) {
            yield [];
            return;
        }
        const [first, ...rest] = lists;
        for (const item of first) for (const tail of product(rest)) yield [item, ...tail];
    }

    // The chip says what it can be wired by, a module may narrow it.
    const transportsOf = (device) => (device.ways ? ['gpio'] : Object.keys(KIT_BUSES)).filter((kind) => device.ways || kind in (Object.keys(device.on || {}).length ? device.on : catalog.devices[device.chip]?.on || {}));

    // The buses a chip was tried on with its libraries, by their records. None named says nothing of any bus.
    const tried = new Map();
    function triedBuses(chip) {
        if (!tried.has(chip)) {
            const entries = Object.values(catalog.libraries).filter((record) => record.chips?.[chip]).flatMap((record) => Object.values(record.checked ?? {}));
            tried.set(chip, entries.filter((entry) => entry.level === 'hardware').flatMap((entry) => entry.covers ?? []).filter((path) => path.startsWith('transports.')).map((path) => path.split('.')[1]));
        }
        return tried.get(chip);
    }

    // How many of a product one block takes on its wires: the outputs it asks over those of one product, when its part chains.
    function chainOf(need, module) {
        const asked = blockAnswer(need.asks?.[CHAIN_QUESTION]);
        const outputs = module.device && MEASURES.chain.of(module.device);
        return asked === undefined || !outputs ? 1 : Math.max(1, Math.ceil(asked / outputs));
    }

    // What the person has of a chain, in order, and what the outputs asked take more: of the first product of the list.
    // Null for a need with no list, or a list of one product: that is a module and its count.
    function membersOf(need) {
        if (!need.members) return null;
        const found = need.members.map(({ part, count }) => ({ module: modulesWith(need).find((item) => item.name === part), count }));
        if (found.some((member) => !member.module)) return null;
        const outputs = (member) => (MEASURES.chain.of(member.module.device) ?? 0) * member.count;
        const asked = blockAnswer(need.asks?.[CHAIN_QUESTION]);
        const have = found.reduce((sum, member) => sum + outputs(member), 0);
        const each = MEASURES.chain.of(found[0].module.device);
        const members = asked > have && each ? [...found, { module: found[0].module, count: Math.ceil((asked - have) / each) }] : found;
        return members.length > 1 ? members : null;
    }

    // With no list, the products of the catalog that chain the chip of the module chosen make the chain. Each joint of two
    // products is one more to solder and weighs as many outputs to spare as the block says (joint_outputs), by default the
    // outputs of the shortest product: the chain of the least joints times that weight and outputs over those asked
    // (Anton, 2026-11-04). The longest go first from the board. Null when no product chains that chip with another.
    function mixOf(need, module) {
        const asked = blockAnswer(need.asks?.[CHAIN_QUESTION]);
        const chip = module.device?.chip;
        if (asked === undefined || !chip || !catalog.devices[chip]?.chain) return null;
        const kinds = modulesWith(need).filter((item) => item.device?.chip === chip).map((item) => ({ module: item, outputs: MEASURES.chain.of(item.device) })).filter((kind) => kind.outputs > 0);
        if (new Set(kinds.map((kind) => kind.module.name)).size < 2) return null;
        // fewest[total]: the fewest pieces whose outputs make total exactly
        const limit = asked + Math.max(...kinds.map((kind) => kind.outputs));
        const fewest = [[]];
        for (let total = 1; total <= limit; ++total) {
            for (const kind of kinds) {
                const before = fewest[total - kind.outputs];
                if (before && (!fewest[total] || before.length + 1 < fewest[total].length)) fewest[total] = [...before, kind];
            }
        }
        const weight = blockAnswer(need.asks?.[JOINT_QUESTION]) ?? Math.min(...kinds.map((kind) => kind.outputs));
        const cost = (made) => (made.length - 1) * weight + made.reduce((sum, kind) => sum + kind.outputs, 0) - asked;
        const pieces = fewest.slice(asked).filter(Boolean).reduce((best, made) => (!best || cost(made) < cost(best) || (cost(made) === cost(best) && made.length < best.length) ? made : best), null);
        if (!pieces) return null;
        const counts = new Map();
        for (const kind of [...pieces].sort((a, b) => b.outputs - a.outputs)) counts.set(kind.module.name, { module: kind.module, count: (counts.get(kind.module.name)?.count ?? 0) + 1 });
        return [...counts.values()];
    }

    // The picks of a shortfall, a module for each thing lacking, the same kind of module for one need.
    function picksFor(shortfalls, choice, transports) {
        return shortfalls.flatMap((shortfall, i) => {
            const mixed = shortfall.need.members ? null : mixOf(shortfall.need, choice[i]);
            const members = membersOf(shortfall.need) ?? (mixed?.length > 1 ? mixed : null);
            // a chain one product makes is that product and its count, whichever of its chip was tried
            const module = mixed?.length === 1 ? mixed[0].module : choice[i];
            return Array.from({ length: shortfall.count }, (_, n) => ({
                count: members ? members[0].count : mixed?.length === 1 ? mixed[0].count : shortfall.need.members?.length === 1 ? Math.max(shortfall.need.members[0].count, chainOf(shortfall.need, module)) : chainOf(shortfall.need, module),
                ...(members ? { members } : {}),
                use: shortfall.need.use ?? (shortfall.need.names?.[n] || undefined) ?? (shortfall.count > 1 ? `${shortfall.need.id ?? shortfall.need.class}_${n + 1}` : shortfall.need.id ?? shortfall.need.class),
                module,
                transport: transports[i],
                need: shortfall.need,
                way: module.way,
            }));
        });
    }

    // Tries the ways to wire a choice of modules; the checks of the tools take the first that holds.
    // resource_limit of ledc: the channels the ways of the parts take (ledc of a way), beside those the outputs took
    function ledcShort(board, shortfalls, choice, taken) {
        const judgement = judgementsOf('resource_limit').find((item) => item.resource === 'ledc');
        const have = board.mcu.facts.frequency_sources?.ledc?.outputs;
        if (!judgement || have === undefined) return null;
        const asked = taken + choice.reduce((sum, module, i) => sum + shortfalls[i].count * (module.way?.ledc ?? (module.device?.ways ? wayOf(module.device, shortfalls[i].need).ledc : 0) ?? 0), 0);
        return asked > have ? { problem: t(judgement.says, asked, have), judgement: judgement.id } : null;
    }

    function wired(name, board, shortfalls, choice, unused, ledcTaken = 0) {
        const short = ledcShort(board, shortfalls, choice, ledcTaken);
        if (short) return short;
        const unfed = choice.find((module) => !supplyOf(board, module));
        if (unfed) return { problem: t('{0}: no line of this board gives the voltage it takes', unfed.title) };
        const ways = choice.map((module) => [...transportsOf(module.device)].sort((a, b) => triedBuses(module.device.chip).includes(b) - triedBuses(module.device.chip).includes(a)));
        if (ways.some((list) => !list.length)) return { problem: t('{0}: on no bus the solver wires', choice.find((module) => !transportsOf(module.device).length).title) };
        const problems = new Set();
        for (const transports of product(ways)) {
            const picks = picksFor(shortfalls, choice, transports);
            // the plans of the sides, best first; in each, SPI parts on hosts of their own first, and when the pins or the hosts
            // run out that way, the same parts sharing hosts
            let project = null;
            let sides = null;
            for (const plan of sidePlans(board, picks)) {
                const apart = projectOf(name, board, picks, unused, true, plan);
                const tried = apart.problem ? projectOf(name, board, picks, unused, false, plan) : apart;
                if (!project || !tried.problem) [project, sides] = [tried, plan];
                if (!tried.problem) break;
            }
            if (project.problem) {
                problems.add(sides.size ? t('the sides asked: {0}', project.problem) : project.problem);
                continue;
            }
            const checks = checksOf(project);
            if (!checks.problems.length) return { project, picks, resolved: checks.resolved, sides };
            const clash = checks.problems[0].text.match(/have address (\S+) on (\S+)/);
            problems.add(clash ? t('two devices would have one address, {0}, on {1}', clash[1], clash[2]) : checks.problems[0].text);
        }
        return { problem: [...problems].join('; ') };
    }

    function switchesOf(picks) {
        const notes = new Set();
        for (const pick of picks) {
            const control = pick.module.device.controls?.interface;
            const value = control?.values?.[pick.transport];
            if (control?.how === 'switch' && value) notes.add(t('{0}: set {1} for {2}', pick.module.title, control.lines.map((line, i) => t('{0} to {1}', line, value[i])).join(', '), pick.transport.toUpperCase()));
        }
        return [...notes];
    }

    // What a kit says of the I2C addresses of its modules.
    function addressLines(picks, project) {
        const lines = [];
        const unknown = new Map(); // bus and chip -> the picks with no address in the data
        for (const pick of picks.filter((item) => item.transport === 'i2c')) {
            const [bus, on] = Object.entries(project.modules[pick.use]?.on ?? {})[0] ?? [];
            if (on?.address) lines.push({ level: 'do', text: t('{0}: set its I2C address to {1}', pick.use, on.address) });
            if (on?.address_try) lines.push({ level: 'unknown', text: t('{0}: the data lists no free I2C address for it on {1}', pick.use, bus) });
            const part = `${bus} ${pick.module.device.chip ?? pick.module.name}`;
            if (bus && !addressesOf(pick.module.device).length) unknown.set(part, [...(unknown.get(part) ?? []), pick]);
        }
        for (const same of unknown.values()) if (same.length > 1) lines.push({ level: 'unknown', text: t('{0} of {1} on one bus: its I2C addresses are not in the data', same.length, same[0].module.device.chip ?? same[0].module.title) });
        return lines;
    }

    // The lines of a kit as a person wires them.
    function wiresOf(board, project, picks) {
        const rows = [];
        const buses = new Set(picks.flatMap((pick) => Object.keys(project.modules[pick.use]?.on || {})));
        for (const bus of buses) {
            const [kind, own] = bus.split('.');
            for (const line of KIT_BUSES[kind].lines) {
                const pin = project.buses?.[kind]?.[own]?.[line] ?? board.buses[kind][own][line].gpio;
                if (pin !== 'nc') rows.push({ what: `${kind.toUpperCase()} ${own}`, line, pin });
            }
        }
        for (const pick of picks) {
            const { on, pins } = project.modules[pick.use] ?? project.devices[pick.use];
            for (const wires of [...Object.values(on || {}), pins || {}]) for (const [line, pin] of Object.entries(wires)) rows.push({ what: pick.use, line, pin: pin?.gpio ?? pin });
        }
        return rows;
    }

    // The libraries of a kit: the board starts those with an adapter, the rest are for the program to start.
    function librariesOf(resolved) {
        const found = new Map();
        for (const [name, device] of Object.entries(resolved.devices)) {
            if (!device.library || device.used === false) continue;
            const record = catalog.libraries[device.library];
            const chip = device.libraries?.[device.library];
            if (!found.has(device.library)) found.set(device.library, { name: `${record.owner}/${record.name}`, version: device.library_at, own: !chip?.adapter, header: chip?.header, call: chip?.init?.[0]?.call, bus: Object.keys(device.on || {})[0], url: record.url, registry: record.install.some((way) => way.via === 'registry'), devices: [] });
            found.get(device.library).devices.push(name);
        }
        return [...found.values()];
    }

    // The audited libraries of the chips of a kit, in order. A kit shows the order: what was found stays in the catalog and with the model.
    function auditLines(resolved, platform, standard) {
        const lines = [];
        const used = Object.values(resolved.devices).filter((device) => device.chip && device.used !== false && (device.classes || []).some((item) => item !== 'other'));
        for (const chip of new Set(used.map((device) => device.chip))) {
            const devices = used.filter((device) => device.chip === chip);
            const bus = Object.keys(devices[0].on ?? {})[0]?.split('.')[0];
            if (triedBuses(chip).length && !triedBuses(chip).includes(bus)) lines.push({ level: 'unknown', text: t('{0} on {1} was not run on a board', chip, bus.toUpperCase()) });
            const order = auditedOrder(libraries, { chip, platform, bus, several: devices.length > 1, standard });
            const named = (id) => id.split('/').slice(1).join('/');
            // the basis of the order, for the page to show on demand: what each audit found, and where it lies
            const basis = order.map((item) => t('{0} {1}: {2} high and {3} medium defects with what it requires, {4} of {5} points of frames, waiting and code_health, read {6} (catalog/libraries/{7}/audit.json)', named(item.id), item.version, item.high, item.medium, item.health, item.health_of, item.date, item.id)).join('\n');
            if (order.length) lines.push({ level: 'yes', text: t('{0} on {1}, audited libraries in order: {2}', chip, bus.toUpperCase(), order.map((item) => named(item.id)).join(', ')), basis });
            for (const item of order) if (item.unread.length) lines.push({ level: 'unknown', text: t('{0} requires {1}, which nobody read', named(item.id), item.unread.map(named).join(', ')) });
            if (order.length || platform !== 'arduino_esp32') continue;
            // for Arduino a library nobody read is no proposal, so the kit only says how many name the chip
            const found = (libraries.byChip[chip] ?? []).filter((id) => libraries.all[id].platforms?.includes(platform));
            lines.push({ level: 'unknown', text: found.length ? t('{0}: no Arduino library is audited, {1} name it', chip, found.length) : t('{0}: no Arduino library names it', chip) });
        }
        return lines;
    }

    // The wires of each module, as a person with the module in hand connects them.
    function wiringOf(board, project, picks) {
        return picks.map((pick) => {
            const { on, pins, supply } = project.modules[pick.use] ?? project.devices[pick.use];
            const lines = [];
            if (pick.way && !pick.module.own) {
                // a line with the level that means on is an object, as the glue takes it
                const gpio = (line) => pins[line]?.gpio ?? pins[line];
                pick.way.lines.forEach((line, i) => lines.push(pick.need.output ? { line: t('channel {0}', pick.need.channel + i), to: `GPIO ${gpio(line)}${i ? `, ${t('half a period later')}` : ''}` } : { line, to: `GPIO ${gpio(line)}` }));
                return { use: pick.use, title: pick.module.title, lines: placed(board, lines) };
            }
            for (const [bus, wires] of Object.entries(on || {})) {
                const [kind, own] = bus.split('.');
                for (const line of KIT_BUSES[kind].lines) {
                    if (line === 'miso' && pick.module.device.logic === 'none') continue; // it sends nothing back
                    const pin = project.buses?.[kind]?.[own]?.[line] ?? board.buses[kind][own][line].gpio;
                    if (pin !== 'nc') lines.push({ line, to: `GPIO ${pin}` });
                }
                for (const [line, pin] of Object.entries(wires).filter(([, value]) => typeof value === 'number')) lines.push({ line, to: `GPIO ${pin}` }); // an address is no wire
            }
            for (const [line, pin] of Object.entries(pins || {})) lines.push({ line, to: `GPIO ${pin?.gpio ?? pin}` });
            for (const [line, from] of Object.entries(supply || {})) lines.push({ line, to: from });
            if (Object.keys(supply || {}).length) lines.push({ line: 'GND', to: 'GND' });
            const number = pick.use.match(/_(\d+)$/)?.[1];
            return { use: pick.use, title: number ? `${pick.module.title} ${number}` : pick.module.title, lines: placed(board, lines) };
        });
    }

    // The wires of a part with where each comes out: a GPIO at its contact and edge; a supply or a ground at a contact of it on
    // the edge of the GPIOs of the part, when the data has one there.
    function placed(board, lines) {
        const { places, spots } = edgesOf(board);
        const at = (spot) => (spot.edge ? t('{0}, contact {1}, {2}', spot.connector, spot.contact, t(`${spot.edge} edge`)) : t('{0}, contact {1}', spot.connector, spot.contact));
        const gpioOf = (wire) => Number(/^GPIO (\d+)/.exec(wire.to)?.[1] ?? NaN);
        const edge = lines.map((wire) => places.get(gpioOf(wire))?.edge).find(Boolean);
        return lines.map((wire) => {
            const spot = Number.isNaN(gpioOf(wire)) ? (edge && spots.get(`${edge} ${wire.to}`)) : places.get(gpioOf(wire));
            return spot ? { ...wire, where: at(spot) } : wire;
        });
    }

    // What a part of a board is, in a few words: its chip, its part when that says more, and the pixels of a panel.
    function partTitle(name, device) {
        const panel = device.config?.panel;
        // a part with no chip is named by its part number, as a photoresistor, and only then by its name on the board
        const chip = catalog.devices[device.chip]?.title ?? device.chip ?? device.part ?? name;
        // the part number says more than its chip when it holds the chip's name, as JD9365DA-H3 of the JD9365
        const named = device.part && device.part.toLowerCase().includes(chip.toLowerCase()) ? device.part : chip;
        const part = device.part && !named.toLowerCase().includes(device.part.toLowerCase()) ? device.part : null;
        return [named, part, panel?.width && `${panel.width} x ${panel.height}`].filter(Boolean).join(', ');
    }

    // The parts of a board that answer a role, for the person to put on the canvas as they are: the role, the variant the
    // part gives and the answers of its block from its data, so that another board is asked for the same. A measure of
    // how parts stand to each other, as the gap between readers, is no answer of one part.
    function boardParts(boardName) {
        const doc = catalog.boards[boardName];
        if (!doc) return [];
        const board = loader.resolve(doc);
        const parts = [];
        for (const [name, device] of Object.entries(board.devices ?? {})) {
            for (const role of roles.flatMap((group) => group.roles).filter((item) => item.id !== OWN_PART)) {
                if (!isClass(device, { ...(role.needs ?? { role: role.id }), id: role.id })) continue;
                const variant = role.variants?.some((item) => item.id === device.provides?.[role.id]?.variant) ? device.provides[role.id].variant : undefined;
                const cls = role.needs?.class;
                const asks = {};
                for (const question of questions.filter((item) => item.asked === 'block' && item.limit?.measure && ofClass(item, cls, variant))) {
                    const measure = MEASURES[question.limit.measure];
                    if (!measure || measure.soft || !measure.unknown) continue;
                    const value = measure.given ? measure.given(device) : measure.of(device);
                    if (typeof value === 'number') asks[question.id] = Math.floor(value * 10) / 10;
                    else if (typeof value === 'string') asks[question.id] = value;
                }
                for (const question of questions.filter((item) => item.limit?.field && item.limit.of === role.id && (!item.limit.variant || item.limit.variant === variant) && item.limit.fits !== 'includes')) {
                    const value = valueAt(device, question.limit.field);
                    if (typeof value === 'number') asks[question.id] = value;
                }
                // its buses and lines on the board, as the card of a kit shows them
                const { buses, lines } = heldOf(board, { title: role.text }, name, device);
                parts.push({ device: name, role: role.id, title: partTitle(name, device), variant, asks, buses, lines });
            }
        }
        return parts;
    }

    // A part of the board that answers a block, as the card shows it: what it is, its buses and its lines on the board, and
    // what a switch or a solder bridge on the board sets for it, as the board comes
    function heldOf(board, need, name, device) {
        const lines = [];
        for (const [bus, wires] of Object.entries(device.on || {})) {
            const [kind, own] = bus.split('.');
            for (const [line, value] of Object.entries(board.buses?.[kind]?.[own] ?? {})) if (value?.gpio !== undefined) lines.push({ line, to: `GPIO ${value.gpio}` });
            for (const [line, value] of Object.entries(wires || {})) if (value?.gpio !== undefined) lines.push({ line, to: `GPIO ${value.gpio}` });
        }
        for (const [line, value] of Object.entries(device.pins || {})) if (value?.gpio !== undefined) lines.push({ line, to: `GPIO ${value.gpio}` });
        const title = partTitle(name, device);
        const set = Object.entries(device.controls || {}).filter(([, control]) => ['switch', 'solder'].includes(control.how)).map(([control, { how, start }]) => ({ control, how, start: JSON.stringify(start) }));
        return { block: need.title, device: name, title, buses: Object.keys(device.on || {}).map((bus) => {
            // SPI2 or I2C0 by the host alone; a host of another kind of bus says the kind, as SPI2 (QSPI)
            const [kind, own] = bus.split('.');
            return (own.startsWith(kind) ? own : `${own} (${kind})`).toUpperCase();
        }), lines, set };
    }

    // What each module puts on the lines of the chip, against what its pins take.
    function levelsOf(resolved, picks, base, project) {
        const lines = [];
        const shifted = [];
        const wired = (pick) => wiringOf(base, project, [pick])[0].lines.filter((wire) => /^GPIO/.test(wire.to)).length;
        const limit = resolved.mcu.facts.gpio.high_mv_max;
        for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
            const low = pick.module.device.high_min_mv ?? (pick.module.device.ways ? wayOf(pick.module.device, pick.need).high_min_mv : undefined);
            // seen_level: a level a trial on hardware ran it with is a note, not a part
            const seen = judgementsOf('seen_level').find((judgement) => judgement.field === 'high_seen_mv');
            const seenLines = judgementsOf('seen_level').find((judgement) => judgement.field === 'logic_seen_mv');
            if (low > CHIP_HIGH_MV && seen && pick.module.device.high_seen_mv <= CHIP_HIGH_MV) {
                lines.push({ level: 'note', text: t(seen.says, pick.module.title, low / 1000, pick.module.device.high_seen_mv / 1000), judgement: seen.id });
                continue;
            }
            if (low > CHIP_HIGH_MV) {
                lines.push({ level: 'do', text: t('{0}: it takes {1} V as high and this chip gives {2} V: put a level shifter on its line', pick.module.title, low / 1000, CHIP_HIGH_MV / 1000) });
                shifted.push({ both: false, lines: wired(pick) });
                continue;
            }
            const logic = resolved.devices[`${pick.use}_${pick.module.part}`]?.logic;
            if (logic === 'none') continue;
            const mv = logic ? lineMv(resolved, logic) : null;
            if (mv === null || limit === undefined) lines.push({ level: 'unknown', text: t('{0}: the level of its lines against this chip is not in the data', pick.module.title) });
            else if (mv > limit && seenLines && pick.module.device.logic_seen_mv >= mv) {
                lines.push({ level: 'note', text: t(seenLines.says, pick.module.title, mv / 1000, limit / 1000), judgement: seenLines.id });
            } else if (mv > limit) {
                lines.push({ level: 'do', text: t('{0}: its lines go up to {1} V and the pins of this chip take {2} V: put a level shifter on them', pick.module.title, mv / 1000, limit / 1000) });
                shifted.push({ both: true, lines: wired(pick) });
            }
        }
        return { lines, shifted };
    }

    // An addon on a port that gives what a board lacks: the board has what it stands on, and a way in for the power it hands over.
    function addonFor(wanted, board) {
        const usable = Object.entries(catalog.addons ?? {}).filter(([, addon]) => addon.stands === 'port' && addon.gives?.provides?.includes(wanted) && (addon.needs ?? []).every((item) => board.provides?.[item]));
        for (const [name, addon] of usable) {
            if (!addon.gives.plug) return { name, addon, plug: t('port') };
            const entry = (board.power ?? []).find((step) => step.plug === addon.gives.plug && step.mv === addon.gives.mv);
            if (entry) return { name, addon, plug: catalog.connectors[addon.gives.plug].title };
        }
        const open = usable.find(([, addon]) => !(board.power ?? []).some((step) => step.plug));
        return open ? { name: open[0], addon: open[1], plug: null } : null;
    }

    // The addons for the lines that need one: those both ways apart from those one way, by the channels of one.
    function addonsFor(shifted) {
        return [true, false].flatMap((both) => {
            const lines = shifted.filter((item) => item.both === both).reduce((sum, item) => sum + item.lines, 0);
            const name = Object.keys(catalog.addons ?? {}).find((item) => catalog.addons[item].stands === 'lines' && Boolean(catalog.addons[item].both_ways) === both);
            return lines && name ? [{ name, title: catalog.addons[name].title, count: Math.ceil(lines / catalog.addons[name].channels) }] : [];
        });
    }

    // What is bought: what the person has already costs nothing, the board and as many of a module as they have.
    function priceOf(doc, picks, currency, addons = [], have = new Map()) {
        const had = have.get(doc.name) > 0;
        let owned = had; // something the person has took off the price: the price without it goes beside
        const own = had ? [0, 0] : rangeOf(doc.price, currency);
        const missing = own ? [] : [doc.title ?? doc.name];
        const unpriced = own ? [] : [{ title: doc.title ?? doc.name, item: `boards/${doc.name}` }];
        let low = own ? own[0] : 0;
        let high = own ? own[1] : 0;
        let known = Boolean(own);
        const packs = [];
        // what of the price is the parts beside the board: the modules, the small parts and the chips of chains
        const parts = { low: 0, high: 0, known: false, missing: [], bought: 0 };
        const counted = new Map();
        for (const { module, count } of picks.filter((item) => !item.way).flatMap(boughtBy)) counted.set(module.name, { title: module.title, count: (counted.get(module.name)?.count ?? 0) + count });
        for (const item of addons) counted.set(item.name, item);
        // the chips of the chains of ways, by the price of their chip
        for (const pick of picks.filter((item) => item.way?.part && !item.need.output && !item.module.own && catalog.devices[item.way.part])) {
            const key = `device ${pick.way.part}`;
            counted.set(key, { title: catalog.devices[pick.way.part].title, count: (counted.get(key)?.count ?? 0) + chainCount(pick) });
        }
        const addPart = (price, title, count, item) => {
            const range = rangeOf(price, currency, count);
            parts.bought += count;
            if (!range) {
                missing.push(title);
                unpriced.push({ title, item });
                parts.missing.push(title);
                return;
            }
            const bought = boughtOf(price, count);
            low += range[0] * bought;
            high += range[1] * bought;
            parts.low += range[0] * bought;
            parts.high += range[1] * bought;
            if (bought > count) packs.push({ title, bought, cost: cents(range[0] * bought) });
            known = true;
            parts.known = true;
        };
        for (const [name, { title, count: wanted }] of counted) {
            const count = wanted - Math.min(wanted, have.get(name) ?? 0);
            owned ||= count < wanted;
            if (!count) continue;
            if (name.startsWith('device ')) {
                const chip = name.slice('device '.length);
                addPart(catalog.devices[chip].price, title, count, `devices/${chip}`);
                continue;
            }
            const kind = name in (catalog.addons ?? {}) ? 'addons' : 'modules';
            addPart(catalog[kind][name].price, title, count, `${kind}/${name}`);
        }
        const price = {
            low: cents(low), high: cents(high), currency, missing, unpriced, known, packs,
            board: { low: cents(own ? own[0] : 0), high: cents(own ? own[1] : 0), known: Boolean(own), missing: own ? [] : [doc.title ?? doc.name] },
            // a part the person has is not bought: parts all had cost nothing
            ...(counted.size ? { parts: { low: cents(parts.low), high: cents(parts.high), known: parts.known || !parts.bought, missing: parts.missing } } : {}),
        };
        // the price in full, everything bought: the cost of the thing, as for making it again
        const full = owned ? priceOf(doc, picks, currency, addons) : price;
        return { ...price, full: { low: full.low, high: full.high, known: full.known, missing: full.missing } };
    }

    function kitsOfBoard(name, wanted) {
        const doc = catalog.boards[name];
        const board = loader.resolve(doc);
        const says = [];
        const held = []; // the parts of the board that answer a block, for the card
        const say = (level, text) => says.push({ level, text });
        const rejected = () => [{ name, title: doc.title ?? name, fits: false, says, modules: [], wires: [], unasked: 0, unaskedWorth: 0, price: null, project: null }];
        const asked = (device) => wanted.needs.some((need) => isClass(device, need));
        const beneath = new Set(Object.values(board.devices).filter(asked).map((device) => device.config?.over)); // a touch asked for needs its display
        const givenAsked = new Set(wanted.needs.map((need) => need.provides).filter(Boolean));
        const askable = (device) => (device.classes || []).some((item) => ASKABLE.has(item)) || Object.keys(device.provides ?? {}).some((key) => ASKABLE_GIVEN.has(key));
        const askedFor = (device) => asked(device) || Object.keys(device.provides ?? {}).some((key) => givenAsked.has(key));
        // the button of a strapping pin is there to flash the chip: every board has one, and nobody chooses it
        const strapping = new Set(board.mcu.facts.gpio.strapping ?? []);
        const forFlashing = (device) => (device.classes || []).includes('button') && Object.values(device.pins ?? {}).some((pin) => strapping.has(typeof pin === 'object' ? pin?.gpio : pin));
        const unasked = Object.entries(board.devices).filter(([part, device]) => askable(device) && !askedFor(device) && !beneath.has(part) && !forFlashing(device));
        // a part a module of the board brings is left unused through that module: its devices of the project would be put back by it
        const modules = doc.modules ?? {};
        const broughtBy = (part) => Object.entries(modules).find(([use, entry]) => part.startsWith(`${use}_`) && part.slice(use.length + 1) in (catalog.modules[entry.module]?.devices ?? {}));
        const unused = { devices: {}, modules: {} };
        // a layer over a part of the board in the board of the program: through its module when a module of the board brings it
        const layer = (part, value) => {
            const brought = broughtBy(part);
            if (!brought) unused.devices[part] = { ...unused.devices[part], ...value };
            else unused.modules[brought[0]] = { module: brought[1].module, devices: { ...unused.modules[brought[0]]?.devices, [part.slice(brought[0].length + 1)]: value } };
        };
        for (const [part] of unasked) layer(part, { used: false });
        let layered = false; // a part of the board asked with something other than its data, as another depth of color
        const shortfalls = [];
        const extra = []; // the addons that give what the board has not
        // The versions of the platforms that take the chip: of the platform asked, or of every one when none is. A version asked is
        // the only one tried; the libraries of a kit narrow the others further on. An older answer names both, as esp_idf:6.1.
        const [platformName, older] = (wanted.limits.platform ?? '').split(':');
        const platform = catalog.platforms?.[platformName];
        const pinned = platform?.versions[wanted.limits.platform_version ?? older] ? wanted.limits.platform_version ?? older : undefined;
        const takes = {};
        for (const [id, item] of Object.entries(catalog.platforms ?? {})) {
            if (platform && id !== platformName) continue;
            const versions = Object.entries(item.versions).filter(([version]) => !pinned || version === pinned);
            takes[id] = { full: versions.filter(([, entry]) => entry.targets.includes(board.mcu.target)).map(([version]) => version),
                          preview: versions.filter(([, entry]) => entry.preview?.includes(board.mcu.target)).map(([version]) => version) };
        }
        if (platform) {
            const { full, preview } = takes[platformName];
            if (!full.length && preview.length) say('unknown', t('{0} {1} takes {2} as a preview', platform.title, preview.join(', '), board.mcu.target));
            else if (!full.length) {
                say('no', pinned ? t('{0} {1} does not take {2}', platform.title, pinned, board.mcu.target) : t('no version of {0} takes {1}', platform.title, board.mcu.target));
                return rejected();
            }
        }
        const plan = wanted.outputs.length ? outputsPlan(board, wanted.outputs) : null;
        if (plan?.problem) {
            say('no', plan.problem);
            return rejected();
        }
        const channels = {};
        wanted.outputs.forEach((item, index) => {
            const lines = item.pins === 2 ? ['a', 'b'] : ['a'];
            const { name } = plan.chosen[index];
            const channel = channels[name] ?? 0;
            channels[name] = channel + lines.length;
            shortfalls.push({ need: { output: name, use: `output_${index + 1}`, index, channel, way: { lines } }, count: 1 });
        });
        for (const need of wanted.needs) {
            if (need.provides) {
                const standing = board.provides?.[need.provides] ? null : addonFor(need.provides, board);
                if (standing) {
                    extra.push({ name: standing.name, title: standing.addon.title, count: 1 });
                    say(standing.plug ? 'do' : 'unknown', standing.plug ? t('{0}: on the {1} of the board', standing.addon.title, standing.plug) : t('{0}: what the board takes for power is not in the data', standing.addon.title));
                    continue;
                }
                if (!board.provides?.[need.provides]) {
                    // an import lists what its source describes: a chip that can do this leaves the question open
                    if (doc.origin && board.mcu.facts.provides?.[need.chip]) {
                        say('unknown', t('{0}: the chip can, the imported data does not say if this board does', titleOf(need)));
                        continue;
                    }
                    say('no', t('no {0} on this board', titleOf(need)));
                    return rejected();
                }
                if (need.antenna) {
                    const [level, text] = externalAntenna(board, need);
                    say(level, text);
                    if (level === 'no') return rejected();
                }
                say('yes', t('{0} is on the board', need.title));
                const quality = antennaQuality(board, need);
                if (quality !== null) say('do', t('{0}: antenna quality {1} of 10', need.title, quality));
                continue;
            }
            for (const question of wanted.unanswered) if (question.limit.of === need.class && blockAnswer(need.asks?.[question.id]) === undefined) say('unknown', t(MEASURES[question.limit.measure].unanswered));
            const limits = limitsOf(need, wanted);
            // a part the person fixed is wanted as it is: what the board has of that role does not replace it
            const on = need.part ? [] : Object.values(board.devices).filter((device) => isClass(device, need));
            const large = on.filter((device) => limits.every((limit) => meets(limit, device)));
            if (on.length > large.length) {
                const short = limits.find((limit) => on.some((device) => !meets(limit, device)));
                say('no', short.short(short.asked));
                return rejected();
            }
            for (const limit of limits) if (large.some((device) => limit.of(device) === null)) say('unknown', t(limit.unknown));
            // unnamed_variant: a part of no named variant answers nothing where a module of the catalog names the one asked
            const unnamed = need.variant ? large.filter((device) => !device.provides?.[need.id]?.variant) : [];
            const named = judgementsOf('unnamed_variant')[0];
            const answering = unnamed.length && named && modulesWith(need).some((module) => module.device.provides?.[need.id]?.variant === need.variant) ? large.filter((device) => !unnamed.includes(device)) : large;
            if (answering.length < large.length) says.push({ level: 'note', text: t(named.says, need.title), judgement: named.id });
            if (need.variant && answering.some((device) => !device.provides?.[need.id]?.variant)) say('unknown', t('{0} is on the board, and the data does not say of which variant', need.title));
            else if (answering.length) say('yes', t('{0} is on the board', need.title));
            const names = new Map(Object.entries(board.devices).map(([key, device]) => [device, key]));
            for (const device of answering.slice(0, need.count)) held.push(heldOf(board, need, names.get(device), device));
            // a display of the board started at another depth than its data's
            const depth = depthAsked(need);
            for (const device of answering.slice(0, need.count).filter((item) => depth !== undefined && item.config?.depth_bits !== depth)) {
                layer(names.get(device), { config: { depth_bits: depth } });
                layered = true;
            }
            if (answering.length < need.count) shortfalls.push({ need, count: need.count - answering.length });
        }
        if (!shortfalls.length && !unasked.length && !layered) return [kit(name, doc, board, says, null, [])];
        const reaching = (need, module) => limitsOf(need, wanted).every((limit) => meets(limit, module.device));
        const output = (need) => ({ name: need.use, title: t('output {0}: {1} timer {2}, {3} Hz', need.index + 1, plan.sources[plan.chosen[need.index].name].title, plan.chosen[need.index].timer, wanted.outputs[need.index].hz), device: { ways: [need.way] }, power: [] });
        // a variant with its own way needs no part of the catalog: the kit gives it the lines
        const byItsLines = (need) => ({ name: need.id, title: need.wayTitle, way: need.way, power: [], device: { ways: [need.way] } });
        const partsOf = (need) => {
            if (need.part) return modulesWith(need).filter((module) => module.name === need.part && reaching(need, module));
            // a part that does not say so is no answer to a variant with a way of its own, and those that say go first
            const says = (module) => Boolean(module.device.provides?.[need.id]?.variant);
            const reached = modulesWith(need).filter((module) => reaching(need, module) && (!need.way || says(module)));
            const parts = [...reached.filter(says), ...reached.filter((module) => !says(module))].slice(0, MOST_MODULES);
            if (reached.length > MOST_MODULES) say('note', t('{0}: {1} more parts were not tried; pin a part in the block to choose one', need.title, reached.length - MOST_MODULES));
            return parts.length || !need.way ? parts : [byItsLines(need)];
        };
        const ownPart = (need) => ({ name: need.names[0] ?? OWN_PART, title: need.title, own: true, way: need.way, power: [], device: { ways: [need.way] } });
        const found = shortfalls.map(({ need }) => (need.output ? [{ ...output(need), way: need.way }] : need.own ? [ownPart(need)] : partsOf(need)));
        const lacking = shortfalls.find((_, i) => !found[i].length);
        if (lacking) {
            const short = limitsOf(lacking.need, wanted).find((limit) => modulesWith(lacking.need).some((module) => !meets(limit, module.device)));
            if (lacking.need.part) say('no', t('{0}: the part you fixed, {1}, does not serve it', lacking.need.title, catalog.modules[lacking.need.part]?.title ?? lacking.need.part));
            else say('no', short ? short.short(short.asked) : t('the catalog has no module for: {0}', titleOf(lacking.need)));
            return rejected();
        }
        const kits = [];
        // a part chosen for one block takes the place of another whose role it gives: an SCD4x measures temperature and humidity beside CO2
        const coverOf = (choice) => {
            const gone = new Map();
            shortfalls.forEach((shortfall, i) => {
                // a part that already serves another block stays: a chain would leave both without it
                if (shortfall.need.output || choice[i].way || [...gone.values()].includes(i)) return;
                // a need with a fixed part is covered only by that same part: one SCD41 fixed for CO2 and for humidity is one part;
                // two blocks of one role are two things, whatever they ask: one reader is no answer to two
                const at = choice.findIndex((module, other) => other !== i && !gone.has(other) && !module.way && !shortfalls[other].need.output
                    && shortfalls[other].need.id !== shortfall.need.id
                    && (!shortfall.need.part || module.name === shortfall.need.part) && shortfalls[other].count >= shortfall.count && isClass(module.device, shortfall.need) && reaching(shortfall.need, module));
                if (at >= 0) gone.set(i, at);
            });
            return gone;
        };
        const triedKits = new Map();
        const tryChoice = (choice) => {
            const gone = coverOf(choice);
            const kept = shortfalls.map((_, i) => i).filter((i) => !gone.has(i));
            const key = kept.map((i) => choice[i].name).join();
            if (triedKits.has(key)) return triedKits.get(key);
            const result = wired(name, board, kept.map((i) => shortfalls[i]), kept.map((i) => choice[i]), unused, plan?.used?.ledc?.lines ?? 0);
            // the blocks one part serves, in the order the person put them
            const serving = new Map([...gone].map(([, at]) => [at, [at]]));
            for (const [i, at] of gone) serving.get(at).push(i);
            const also = [...serving].map(([at, served]) => ({ level: 'yes', text: t('{0} serves: {1}', choice[at].title, served.sort((a, b) => a - b).map((i) => shortfalls[i].need.title).join(', ')) }));
            const item = result.project ? kit(name, doc, result.resolved, [...says, ...also], result.project, result.picks, board, result.sides) : { name, title: doc.title ?? name, fits: false, says: [...says, { level: 'no', text: result.problem, ...(result.judgement ? { judgement: result.judgement } : {}) }], modules: [], wires: [], price: null, project: null };
            // which part each block gets, for the canvas to show the blocks one part serves together
            // unit: the part as bought, so two SCD41 for two rooms are not one
            if (item.fits) item.served = shortfalls.map((shortfall, i) => ({ role: shortfall.need.id, names: shortfall.need.names ?? [], unit: gone.get(i) ?? i, title: choice[gone.get(i) ?? i].title })).filter((entry) => entry.role);
            kits.push(item);
            triedKits.set(key, item);
            return item;
        };
        if (found.reduce((all, list) => all * list.length, 1) <= MOST_CHOICES) for (const choice of product(found)) tryChoice(choice);
        else {
            // what weighs against a kit, in the order of the ranking
            const weight = (item) => [item.fits ? 0 : 1, item.says.filter((line) => line.level === 'unknown').length, item.modules.length, item.wires.length];
            const lighter = (a, b) => { const [x, y] = [weight(a), weight(b)]; return (x.find((value, i) => value !== y[i]) ?? 0) < (y.find((value, i) => value !== x[i]) ?? 0); };
            const tried = new Set();
            let best = { choice: found.map((list) => list[0]), kit: null };
            for (let round = 0; round < ROUNDS_OF_CHANGES; round += 1) {
                const around = best.choice;
                for (const [i, list] of found.entries()) {
                    for (const module of list) {
                        const choice = around.map((item, at) => (at === i ? module : item));
                        const key = choice.map((item) => item.name).join();
                        if (tried.has(key)) continue;
                        tried.add(key);
                        const item = tryChoice(choice);
                        if (!best.kit || lighter(item, best.kit)) best = { choice, kit: item };
                    }
                }
            }
        }
        const good = kits.filter((item) => item.fits);
        if (good.length) return good;
        // no choice of modules can be wired: the reasons of all of them
        const reasons = [...new Set(kits.flatMap((item) => item.says.filter((line) => line.level === 'no').map((line) => line.text)))];
        return [{ ...kits[0], says: [...says, ...reasons.map((text) => ({ level: 'no', text }))] }];

        function kit(boardName, source, resolved, reasons, project, picks, base, sides = new Map()) {
            const counted = new Map();
            for (const pick of picks.filter((item) => !item.way)) {
                // a member after the first of a chain is on the wires of the one before it, not on a bus of the board
                boughtBy(pick).forEach(({ module, count }, at) => counted.set(module.name, { ...pick, module, count: (counted.get(module.name)?.count ?? 0) + count, wired: counted.get(module.name)?.wired || !at }));
            }
            const pictureOf = (name) => Object.values(catalog.modules[name]?.images ?? {})[0];
            const modules = [...counted.values()].map((pick) => ({ name: pick.module.name, title: pick.module.title, count: pick.count, on: pick.transport, ...(pick.wired === false ? { after: true } : {}),
                ...(pictureOf(pick.module.name) ? { picture: `modules/${pick.module.name}/${pictureOf(pick.module.name).file}`, credit: pictureOf(pick.module.name).source } : {}) }));
            const named = (item) => `${item.count > 1 ? `${item.count} x ` : ''}${item.title}`;
            const lines = [...reasons];
            const arduino = platform?.ecosystem === 'arduino';
            for (const item of modules.filter((entry) => !entry.after)) lines.push({ level: 'yes', text: t('{0} on {1}', named(item), item.on.toUpperCase()) });
            // the sides: the edge of each letter, the supplies of its parts that come out elsewhere, a host off its IO MUX for it,
            // and a board whose data names no edges
            const sideJudgement = judgementsOf('sides')[0];
            if (sideJudgement && picks.some((pick) => sideOf(pick.need)) && !sides.size) lines.push({ level: 'unknown', text: t('the data of this board does not say on which edge its contacts are: the sides are not kept'), judgement: sideJudgement.id });
            const { names } = edgesOf(base ?? resolved);
            for (const [letter, edge] of sides) {
                lines.push({ level: 'yes', text: t(sideJudgement.says, letter, t(`${edge} edge`)), judgement: sideJudgement.id });
                const ofLetter = picks.filter((pick) => sideOf(pick.need) === letter);
                const supplies = [...new Set(ofLetter.flatMap((pick) => Object.values(project.modules[pick.use]?.supply ?? {})))];
                for (const supply of [...supplies, ...(supplies.length ? ['GND'] : [])].filter((name) => !names.get(edge)?.has(name))) {
                    const there = [...names].filter(([, set]) => set.has(supply)).map(([other]) => t(`${other} edge`));
                    lines.push({ level: 'do', text: there.length ? t('side {0}: {1} is not on its edge, take it from: {2}', letter, supply, there.join(', ')) : t('side {0}: {1} is not on its edge', letter, supply), judgement: sideJudgement.id });
                }
                const matrix = (base ?? resolved).mcu.facts.limits?.spi_matrix_mhz;
                const hosts = new Set(ofLetter.flatMap((pick) => Object.keys((project.modules[pick.use] ?? project.devices[pick.use])?.on ?? {})).filter((bus) => bus.startsWith('spi.')).map((bus) => bus.slice(4)));
                for (const own of hosts) {
                    const named = (base ?? resolved).mcu.facts.iomux?.spi?.[own];
                    const wired = project.buses?.spi?.[own];
                    if (!named || !wired) continue;
                    const off = KIT_BUSES.spi.lines.some((line) => wired[line] !== 'nc' && wired[line] !== named[line]);
                    const free = freePins(base ?? resolved);
                    if (off && KIT_BUSES.spi.lines.every((line) => wired[line] === 'nc' || free.includes(named[line]))) {
                        lines.push({ level: 'note', text: matrix ? t('{0} is not on the pins of its IO MUX, to keep side {1}: through the GPIO matrix up to {2} MHz', own.toUpperCase(), letter, matrix) : t('{0} is not on the pins of its IO MUX, to keep side {1}', own.toUpperCase(), letter), judgement: sideJudgement.id });
                    }
                }
            }
            // a display started at another depth of color than its data's was not tried so on this board
            for (const [part, device] of Object.entries(project && base ? resolved.devices : {})) {
                const data = (base.devices[part] ?? picks.find((pick) => part === `${pick.use}_${pick.module.part}`)?.module.device)?.config?.depth_bits;
                const depth = device.config?.depth_bits;
                if (data && depth && depth !== data) lines.push({ level: 'unknown', text: t('{0}: {1} bits of color were not tried on this board; its data starts it with {2}', catalog.devices[device.chip]?.title ?? part, depth, data) });
            }
            for (const pick of picks.filter((item) => item.count > 1 && !item.members)) lines.push({ level: 'do', text: t('{0}: {1} in one chain on the wires of one, the output of each into the input of the next', pick.module.title, pick.count) });
            for (const pick of picks.filter((item) => item.members)) lines.push({ level: 'do', text: t('{0}: {1} in one chain on the wires of the first, the output of each into the input of the next', pick.need.title, pick.members.map((member) => named({ title: member.module.title, count: member.count })).join(t(', then '))) });
            for (const [name, use] of Object.entries(plan?.used ?? {})) {
                const source = plan.sources[name];
                if (!use.timers.size) continue;
                const tried = Object.values(resolved.mcu.facts.checked ?? {}).some((entry) => entry.level === 'hardware' && entry.covers?.includes(`frequency_sources.${name}.pairs`));
                if (use.pairs && !tried) lines.push({ level: 'unknown', text: t('{0}: two pins in antiphase were not tried on this chip', source.title) });
                lines.push({ level: 'yes', text: t('{0}: {1} of {2} outputs, {3} of {4} timers', source.title, use.lines, source.outputs, use.timers.size, source.timers) });
                [...use.timers.values()].forEach((timer, index) => {
                    const error = Math.abs(ppmOf(timer)) < 0.01 ? t('exact') : `${ppmOf(timer) > 0 ? '+' : ''}${Math.round(ppmOf(timer) * 10) / 10} ppm`;
                    lines.push({ level: 'yes', text: t('{0} timer {1}: {2} Hz, {3}, {4}', source.title, index, cents(timer.hz), error, t(timer.note)) });
                });
            }
            for (const text of switchesOf(picks)) lines.push({ level: 'do', text });
            for (const pick of picks.filter((item) => item.module.own)) lines.push({ level: 'do', text: t('{0}: your own part, not in the catalog: {1}', pick.module.title, [...Object.entries(project.devices[pick.use].pins ?? {}).map(([line, pin]) => `${line} GPIO ${pin?.gpio ?? pin}`), ...Object.keys(project.devices[pick.use].on ?? {}).map((bus) => bus.toUpperCase())].join(', ') || t('no lines')) });
            for (const pick of new Map(picks.filter((item) => item.way && !item.need.output && !item.module.own).map((item) => [item.need.id, item])).values()) {
                // a way that names its chip counts the chips of one chain by the outputs asked
                const chip = pick.way.part && catalog.devices[pick.way.part];
                const asked = blockAnswer(pick.need.asks?.[CHAIN_QUESTION]);
                if (!chip?.chain) lines.push({ level: 'do', text: t('{0}: no part of the catalog, the kit only gives it pins: {1}', pick.module.title, pick.way.lines.join(', ')) });
                else if (asked === undefined) lines.push({ level: 'do', text: t('{0}: {1} in one chain, {2} outputs each, on the lines: {3}', pick.module.title, chip.title, chip.chain.per, pick.way.lines.join(', ')) });
                else lines.push({ level: 'do', text: t('{0}: {1} x {2} in one chain for {3} outputs, on the lines: {4}', pick.module.title, Math.ceil(asked / chip.chain.per), chip.title, asked, pick.way.lines.join(', ')) });
            }
            for (const pick of new Map(picks.filter((item) => item.need.variant && !item.way).map((item) => [item.module.name, item])).values()) {
                if (!pick.module.device.provides?.[pick.need.id]?.variant) lines.push({ level: 'unknown', text: t('{0}: the data does not say of which variant it is', pick.module.title) });
            }
            if (project) lines.push(...addressLines(picks, project));
            if (doc.origin) lines.push({ level: 'do', text: t('imported from {0} {1}, not checked by us', doc.origin.from, doc.origin.ref) });
            // a pack lists the parts its drivers start: what else the board has, and nobody asked for, is not known
            if (doc.origin) lines.push({ level: 'unknown', text: t('its data lists only the parts its pack starts') });
            if (picks.some((item) => !item.way) && !namesLines(base ?? board)) lines.push({ level: 'unknown', text: t('its supply lines are not in the data: check what feeds the modules') });
            if (picks.length && !Object.keys((base ?? board).connectors || {}).length) lines.push({ level: 'unknown', text: t('its connectors are not in the data: check that the wired pins come out') });
            const onLines = project ? levelsOf(resolved, picks, base, project) : { lines: [], shifted: [] };
            lines.push(...onLines.lines);
            const addons = [...addonsFor(onLines.shifted), ...extra];
            for (const item of addons) lines.push({ level: 'do', text: t('{0} between the chip and these lines', named(item)) });
            for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
                for (const limit of limitsOf(pick.need, wanted)) {
                    const value = limit.of(pick.module.device);
                    if (value === null) lines.push({ level: 'unknown', text: `${pick.module.title}: ${t(limit.unknown)}` });
                    else if (limit.soft && !limit.fits(value, limit.asked)) lines.push({ level: 'unknown', text: limit.soft(pick.module.title, value, limit.asked) });
                }
                for (const text of catalog.modules[pick.module.name].do ?? []) lines.push({ level: 'do', text: `${pick.module.title}: ${t(text)}` });
                // how the way taken is wired, as two pins in antiphase
                const way = pick.module.device.ways && !pick.module.own ? wayOf(pick.module.device, pick.need) : null;
                if (way?.do) lines.push({ level: 'do', text: `${pick.module.title}: ${t(way.do)}` });
                // the wires list no supply that the data does not name
                const steps = pick.module.power.filter((step) => step.source === 'connector');
                if (!steps.length) lines.push({ level: 'unknown', text: t('{0}: what feeds it is not in the data', pick.module.title) });
                for (const step of steps.filter((item) => !item.volts)) lines.push({ level: 'unknown', text: t('{0}: the voltage of {1} is not in the data', pick.module.title, step.name) });
                if (!KIT_BUSES[pick.transport].fixed) continue;
                lines.push({ level: 'do', text: t('{0}: a ribbon to the {1} connector', pick.module.title, pick.transport.toUpperCase()) });
                lines.push({ level: 'unknown', text: t('{0}: its timings are measured on a board, and not on this one', pick.module.title) });
            }
            const price = priceOf({ ...source, price: board.price }, picks, wanted.currency, addons, wanted.have);
            // a board the person has: its price and the worth of what nobody asked for on it are spent already
            const had = wanted.have.get(boardName) > 0;
            const usual = rangeOf(board.price, wanted.currency);
            if (had) lines.push({ level: 'yes', text: t('{0}: you have it, so its price ({1}) and what nobody asked for on it count nothing', source.title ?? boardName,
                usual ? `${spread(usual)} ${wanted.currency}` : t('price not known')) });
            for (const item of modules.filter((module) => wanted.have.get(module.name) > 0)) {
                lines.push({ level: 'yes', text: t('{0}: you have {1} of the {2} it takes', item.title, Math.min(wanted.have.get(item.name), item.count ?? 1), item.count ?? 1) });
            }
            for (const pack of price.packs) lines.push({ level: 'do', text: t('{0}: sold by {1}, {2} {3} the pack', pack.title, pack.bought, pack.cost, price.currency) });
            if (project && loader.trust(resolved, 'connectors', levels)[0].endsWith('unchecked')) lines.push({ level: 'do', text: t('{0}: its connectors are from memory: check them against the board before wiring', source.title ?? boardName) });
            for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
                if (!arduino && !resolved.devices[`${pick.use}_${pick.module.part}`]?.library) lines.push({ level: 'unknown', text: t('{0}: the catalog has no library for its chip', pick.module.title) });
            }
            for (const item of modules) {
                const entries = Object.values(catalog.modules[item.name].checked ?? {});
                if (entries.some((entry) => entry.level === 'unchecked' && entry.covers?.includes('power'))) lines.push({ level: 'do', text: t('{0}: its supply and levels are not measured', item.title) });
            }
            // the SPI parts on hosts of their own run apart; those on one host wait for each other
            const onSpi = Object.entries(project?.modules ?? {}).flatMap(([use, item]) => Object.keys(item.on ?? {}).filter((bus) => bus.startsWith('spi.')).map((bus) => ({ use, bus })));
            if (onSpi.length > 1) {
                const sharing = [...Map.groupBy(onSpi, (item) => item.bus)].filter(([, items]) => items.length > 1);
                for (const [bus, items] of sharing) lines.push({ level: 'note', text: t('{0} share {1}: no free SPI host, or no pins for one, is left for them', items.map((item) => item.use).join(', '), bus.split('.')[1].toUpperCase()) });
                if (!sharing.length) lines.push({ level: 'note', text: t('{0}: each on an SPI host of its own, so their tasks run apart', onSpi.map((item) => item.use).join(', ')) });
            }
            // a host of the kit on the pins a judgement names, with the id of that judgement
            const chip = (resolved ?? base)?.mcu?.facts;
            // a strapping pin the kit takes, with the judgement that lets it and what the pin selects
            if (project) {
                const before = pinMap(base);
                const after = pinMap(resolved);
                for (const judgement of judgementsOf('keep_out').filter((item) => item.what === 'strapping')) {
                    for (const [pin, entry] of Object.entries(after)) {
                        if (!entry.strapping || !entry.boot || !entry.owners.length || before[pin]?.owners.length) continue;
                        const selects = entry.boot.footnote ?? t('it selects {0}', entry.boot.selects.join(', '));
                        // a pin kept out that a part holding nothing has all the same: said with the part
                        const owner = resolved.devices[entry.owners[0].split('.')[0]];
                        const quietOne = judgement.unless?.logic === 'none' && owner?.logic === 'none' && !strappingGiven(base, pin, before[pin] ?? entry);
                        const part = quietOne && (Object.entries(resolved.modules ?? {}).find(([use]) => entry.owners[0].startsWith(`${use}_`))?.[1].title ?? entry.owners[0]);
                        lines.push({ level: 'note', text: quietOne ? t(judgement.says_unless, `GPIO ${pin}`, selects, part) : t(judgement.says, `GPIO ${pin}`, selects), judgement: judgement.id, pin: +pin });
                    }
                }
                // a pin the kit takes whose note is a cost, with the judgement that weighs it
                for (const judgement of judgementsOf('note_cost')) {
                    for (const [pin, entry] of Object.entries(after)) {
                        if ((entry.notes || []).includes(judgement.note) && entry.owners.length && !before[pin]?.owners.length) lines.push({ level: 'note', text: t(judgement.says, `GPIO ${pin}`), judgement: judgement.id, pin: +pin });
                    }
                }
            }
            // strapping pins the docs name and no datasheet describes: kept out, and said
            const undescribed = (chip?.gpio?.strapping ?? []).filter((pin) => !chip.gpio.pins?.[pin]?.boot);
            if (project && undescribed.length) lines.push({ level: 'note', text: t('GPIO {0}: strapping pins by the docs of ESP-IDF, with no description of their boot in the data: the kit leaves them', undescribed.join(', ')), judgement: 'strapping_by_harm' });
            if (chip && project && !chip.gpio?.strapping) lines.push({ level: 'unknown', text: t('{0}: its strapping pins are not in the data: a pin of this kit may be one', chip.title ?? chip.name) });
            for (const judgement of judgementsOf('prefer_pins')) {
                for (const [own, bus] of Object.entries(project?.buses?.[judgement.bus] ?? {})) {
                    const named = chip?.[judgement.pins]?.[judgement.bus]?.[own];
                    if (named && KIT_BUSES[judgement.bus].lines.every((line) => bus[line] === 'nc' || bus[line] === named[line])) lines.push({ level: 'note', text: t(judgement.says, own.toUpperCase()), judgement: judgement.id });
                }
            }
            const libraries = librariesOf(resolved);
            // the versions that take the chip, narrowed by what the libraries of the kit are built against
            const ranges = (id) => [...new Set(Object.values(resolved.devices).filter((device) => device.library && device.used !== false)
                .map((device) => catalog.libraries[device.library]?.versions?.[device.library_at]?.platforms?.[id]).filter(Boolean))];
            const builds = Object.entries(takes).map(([id, { full }]) => [id, full.filter((version) => ranges(id).every((range) => within(version, range)))]);
            for (const [id, versions] of builds) {
                if (!versions.length) continue;
                // what of these the computer has, when the server of the model told the page
                const here = wanted.installed?.[id]?.filter((full) => versions.some((version) => full === version || full.startsWith(`${version}.`)));
                lines.push({ level: 'yes', text: here ? t('builds with {0} {1}; on this computer: {2}', catalog.platforms[id].title, versions.join(', '), here.join(', ') || t('none of them')) : t('builds with {0} {1}', catalog.platforms[id].title, versions.join(', ')) });
            }
            const none = builds.find(([id, versions]) => id === platformName && !versions.length && takes[id].full.length);
            if (none) lines.push({ level: 'no', text: t('{0}: no version of the catalog takes what its libraries ask, {1}', platform.title, ranges(platformName).join(', ')) });
            lines.push(...auditLines(resolved, platformName || 'esp_idf', wanted.limits.standard));
            for (const item of arduino ? [] : libraries.filter((library) => library.own)) lines.push({ level: 'do', text: t('{0} {1}: the project gets it, the program starts {2} with {3}()', item.name, item.version, item.devices.join(', '), item.call) });
            const started = arduino ? [] : libraries.filter((library) => !library.own);
            if (started.length) lines.push({ level: 'yes', text: t('the board starts: {0}', started.map((item) => `${item.name} ${item.version}`).join(', ')) });
            if (unasked.length) lines.push({ level: 'note', text: t('on the board and not asked: {0}. The project leaves them unused and their pins stay taken', unasked.map(([name, device]) => device.chip ?? name).join(', ')) });
            if (unasked.length && !had) lines.push({ level: 'note', text: t('what nobody asked for is worth about {0} {1}: a part by the price of its chip, or by the cheapest of its role', cents(unasked.reduce((sum, [, device]) => sum + worthOf(device), 0)), KIT_CURRENCY) });
            for (const title of price.missing) lines.push({ level: 'unknown', text: t('no price for {0}', title) });
            const fits = !none && (wanted.limits.price === undefined || !price.known || price.low <= wanted.limits.price);
            if (!fits) lines.push({ level: 'no', text: t('it costs at least {0} {1}', price.low, price.currency) });
            const title = source.title ?? boardName;
            const headline = [title, ...modules.map(named), ...addons.map(named)].join(' + ');
            const pictures = Object.values(board.images || {});
            const picture = pictures.find((item) => item.shows === 'front') ?? pictures[0];
            return { name: boardName, title, headline, libraries, addons, cost: { ...price.full, currency: price.currency }, unasked: unasked.length, unaskedWorth: had ? 0 : cents(unasked.reduce((sum, [, device]) => sum + worthOf(device), 0)), imported: Boolean(doc.origin), writable: !doc.origin && platform?.writes_projects !== false, picture: picture ? `boards/${boardName}/${picture.file}` : null, fits, says: lines, held, modules, wires: project ? wiresOf(base, project, picks) : [], wiring: project ? wiringOf(base, project, picks) : [], price, project, free: freePins(resolved).length };
        }
    }

    // Every board with a verdict: the kits that fit first, then the fewest unknowns, the least worth of what nobody asked for, the fewest
    // modules, the fewest wires. What a board has and nobody needs weighs before the modules, in money (Anton): a camera puts a kit
    // below one without it, an LED hardly.
    // The unknowns come first: an imported board lists few of its parts, and the least nobody asked for would reward what the data lacks.
    // The price counts last, unless a budget makes it a criterion: then it comes right after the unknowns, and a missing price is one of them.
    function solve(answers) {
        modulesOfNeed.clear();
        const wanted = wantedBy(answers);
        const budget = wanted.limits.price !== undefined;
        // a board the person fixed is the only one tried
        const boards = Object.keys(catalog.boards).filter((name) => catalog.boards[name].kind === 'board' && (!answers.board || name === answers.board)).sort();
        const unknowns = (kit) => kit.says.filter((line) => line.level === 'unknown').length - (budget ? 0 : kit.price?.missing.length ?? 0);
        // a sum without the price of a part is no price: it would make a board with none look the cheapest
        const spent = (kit) => (kit.price?.known && !kit.price.missing.length ? kit.price.low : Infinity);
        return boards.flatMap((name) => kitsOfBoard(name, wanted)).sort(
            (a, b) => b.fits - a.fits || unknowns(a) - unknowns(b) || (budget && spent(a) - spent(b)) || (a.unaskedWorth ?? 0) - (b.unaskedWorth ?? 0) || a.modules.length + (a.addons?.length ?? 0) - b.modules.length - (b.addons?.length ?? 0) || a.wires.length - b.wires.length || (!budget && spent(a) - spent(b)) || a.name.localeCompare(b.name)
        );
    }

    // What a project keeps of how it was chosen, so that the choice can be read and made again.
    // selection.json of a project: the kits chosen, each by the name board_select.py takes, in the order they were added,
    // and the current one apart, so the order stays as it is when another becomes current.
    function selectionOf(chosen, current, kits, answers, currency, name) {
        // the page keeps copies of the kits it chose: they are the same kits by their headline
        const kitsChosen = new Set(chosen.map((item) => item.kit.headline));
        const others = kits.filter((item) => !kitsChosen.has(item.headline));
        return {
            format: KIT_FORMAT.format,
            format_version: SELECTION_VERSION,
            ...(name ? { name } : {}),
            currency,
            answers,
            boards: chosen.map(({ kit, board }) => ({
                board,
                ...(board !== kit.name ? { base: kit.name } : {}),
                modules: kit.modules.map(({ name, count, on }) => ({ name, count, on })),
                libraries: kit.libraries.map(({ name, version }) => ({ name, version })),
                says: kit.says.map(({ level, text, judgement }) => ({ level, text, ...(judgement ? { judgement } : {}) })),
                // to buy now, what the person has at nothing, and in full, everything bought
                ...(kit.price?.known ? { price: [kit.price.low, kit.price.high] } : {}),
                ...(kit.cost?.known ? { cost: [kit.cost.low, kit.cost.high] } : {}),
            })),
            current,
            others: others.filter((item) => item.fits).slice(0, OTHERS_KEPT).map((item) => item.headline),
            rejected: others.filter((item) => !item.fits).map((item) => ({ board: item.name, why: item.says.filter((line) => line.level === 'no').map((line) => line.text) })),
        };
    }

    // The parts of the catalog a block can have, for the person to fix one: none for a block the board itself gives.
    function partsOfBlock(block) {
        const [need] = blocksInNeeds([{ ...block, part: undefined }]);
        if (!need || need.own || need.provides || need.output) return [];
        return [...new Map(modulesWith(need).map((module) => [module.name, { name: module.name, title: module.title }])).values()];
    }

    return { solve, holds, selectionOf, partsOfBlock, boardParts };
}

if (typeof module !== 'undefined') module.exports = { kitSolver, auditSummary, auditedOrder, within };
