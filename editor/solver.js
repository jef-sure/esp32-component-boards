// From the answers to the questions of catalog/questions.json to kits: a board of the catalog and the modules it
// lacks, with the wires. The solver only proposes: a kit is a project, and the checks of the tools decide about it.
'use strict';

const KIT_FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const CHIP_HIGH_MV = 3300; // what a pin of an ESP32 gives as high
const MOST_MODULES = 6; // the parts tried for one need: more make the search longer and the list no clearer
const OWN_PART = 'own_part'; // the role of a part of the person's own, which the catalog has not
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
            const key = block.role === OWN_PART ? `${OWN_PART}/${at}` : `${block.role}/${block.variant ?? ''}/${block.part ?? ''}/${JSON.stringify(block.asks ?? {})}`;
            same.set(key, [...(same.get(key) ?? []), block]);
        }
        return [...same.values()].map((group) => {
            const role = roleOf(group[0].role);
            if (role.id === OWN_PART) return { id: OWN_PART, own: true, count: 1, names: [group[0].name || undefined], title: group[0].name || t(role.text), way: ownWay(group[0]) };
            const variant = role.variants?.find((item) => item.id === group[0].variant);
            // a variant that asks the board for something else, as a gamepad by Bluetooth, is named by what the board must have
            const title = t(variant?.needs?.provides && variant.needs.provides !== role.needs?.provides ? variant.text : role.text);
            return { ...(variant?.needs ?? role.needs ?? { role: role.id }), id: role.id, variant: group[0].variant, part: group[0].part, asks: group[0].asks, count: group.length, names: group.map((block) => block.name), title, way: variant?.way, wayTitle: variant && t(variant.text) };
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

    // an answer of a block that asks something: none for an empty field or "any"
    const blockAnswer = (value) => (value === undefined || value === null || value === '' || value === 'any' ? undefined : value);

    function limitsOf(need, wanted) {
        // a question asked of each block takes the block's answer first, the one of the page after it (an older answer)
        const answerOf = (item) => (item.asked === 'block' && blockAnswer(need.asks?.[item.id]) !== undefined ? need.asks[item.id] : wanted.limits[item.limit.measure]);
        const measured = questions.filter((item) => item.limit?.measure && item.limit.of && item.limit.of === need.class && answerOf(item) !== undefined)
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
        return { needs, limits, unanswered, outputs, currency: answers.currency || KIT_CURRENCY, installed: answers.installed ?? null };
    }

    const rateOf = (currency) => (currency === KIT_CURRENCY ? 1 : rates[currency]);

    // An offer in a currency, null when one of the two has no rate. A low of 0 is a bound, "less than 3": it counts as that bound.
    function converted(offer, currency) {
        const rate = rateOf(currency) / rateOf(offer.currency);
        return rate ? [(offer.range[0] || offer.range[1]) * rate, offer.range[1] * rate] : null;
    }

    function rangeOf(price, currency) {
        const ranges = Object.values(price || {}).map((offer) => converted(offer, currency)).filter(Boolean);
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
            const each = range[0] / Math.max(1, Math.min(...Object.values(module.price).map((offer) => offer.qty ?? 1)));
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
        // a part whose chip has a price by the piece is worth that many of it: a module of its role counts a ring for one LED
        const many = device.config?.count ?? device.count ?? 1;
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

    function freePins(board) {
        const map = pinMap(board);
        const hasOutside = Object.values(map).some((entry) => entry.connectors.length);
        // the note of a strapping pin is keep_out's to weigh, a note that is a cost note_cost's; any other keeps a pin out
        const costs = new Set(judgementsOf('note_cost').map((judgement) => judgement.note));
        const notes = (entry) => (entry.notes || []).filter((note) => !note.startsWith('Strapping pin') && !costs.has(note));
        return Object.entries(map)
            .filter(([pin, entry]) => entry.state === 'free' && (!entry.strapping || strappingGiven(board, pin, entry)) && !entry.input_only && !notes(entry).length && (!hasOutside || entry.connectors.length))
            .map(([pin]) => +pin);
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
    function busOf(board, kind, pins, added, hz, alone, kept, silent, placed, spread) {
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
            const named = ownPins(board, kind, own, lines, pins);
            if (named) for (const line of lines) pins.splice(pins.indexOf(named[line]), 1);
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
    function projectOf(name, board, picks, unused, spread = true) {
        // the pins a part of the person's own is soldered to are out of what the kit hands out
        const soldered = picks.flatMap((pick) => Object.values(pick.way?.fixed ?? {}));
        const open = freePins(board);
        const lost = picks.find((pick) => Object.values(pick.way?.fixed ?? {}).some((pin) => !open.includes(pin)));
        if (lost) {
            const map = pinMap(board);
            // what holds the pin, in the words of the data
            const holder = (entry) => !entry ? t('not a GPIO of this chip') : entry.owners.length ? entry.owners.join(', ') : entry.input_only ? t('input only') : entry.notes?.length ? entry.notes.join(', ') : entry.strapping ? t('a strapping pin') : t('does not come out');
            const pins = Object.values(lost.way.fixed).filter((pin) => !open.includes(pin)).map((pin) => `GPIO ${pin} (${holder(map[pin])})`);
            return { problem: t('{0} is soldered to {1}, which this board does not leave free', lost.module.title, pins.join(', ')) };
        }
        // the pins a judgement names for a host the board does not wire yet go last, so a new host can take them all
        const free = open.filter((pin) => !soldered.includes(pin));
        const theirs = new Set(judgementsOf('prefer_pins').flatMap((judgement) => hostNames(board, KIT_BUSES[judgement.bus].host)
            .filter((own) => !Object.values(board.buses ?? {}).some((named) => own in named))
            .flatMap((own) => [...KIT_BUSES[judgement.bus].lines, 'cs'].map((line) => board.mcu.facts[judgement.pins]?.[judgement.bus]?.[own]?.[line]))));
        const pins = [...free.filter((pin) => !theirs.has(pin)), ...free.filter((pin) => theirs.has(pin))];
        const buses = {};
        const modules = { ...unused.modules };
        const devices = { ...unused.devices };
        const kept = new Set(); // the buses a display of its own holds
        const held = {}; // the addresses taken on each I2C bus
        const placed = {}; // the parts of this project on each host
        const shared = {}; // the lines the chains of a need have in common
        for (const pick of picks) {
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
                devices[pick.use] = { class: 'other', pins: { ...common, ...pick.way.fixed, ...Object.fromEntries(own.map((line, i) => [line, i < read.length ? read[i] : pins.shift()])) } };
                if (!Object.keys(devices[pick.use].pins).length) delete devices[pick.use].pins;
                if (pick.way.bus) {
                    const bus = busOf(board, pick.way.bus, pins, buses, undefined, false, kept, false, placed, spread);
                    if (bus.problem) return bus;
                    placed[bus] = (placed[bus] ?? 0) + 1;
                    const wires = KIT_BUSES[pick.way.bus].select ? { cs: selectOf(board, pick.way.bus, bus, pins) } : {};
                    if (wires.cs === undefined && KIT_BUSES[pick.way.bus].select) return { problem: shortOfPins(1, 0) };
                    devices[pick.use].on = { [`${pick.way.bus}.${bus}`]: { ...wires, ...(pick.way.address ? { address: pick.way.address } : {}) } };
                }
                if (pick.way.shared) shared[pick.need.id] = { pins: Object.fromEntries(pick.way.shared.map((line) => [line, devices[pick.use].pins[line]])), uses: [...(shared[pick.need.id]?.uses ?? []), pick.use] };
                continue;
            }
            // a part with no bus takes the lines of its first way
            if (pick.module.device.ways) {
                const { lines } = pick.module.device.ways[0];
                if (pins.length < lines.length) return { problem: shortOfPins(lines.length, pins.length) };
                modules[pick.use] = { module: pick.module.name, pins: Object.fromEntries(lines.map((line) => [line, pins.shift()])) };
                continue;
            }
            const alone = isDisplay(pick.module.device) && KIT_BUSES[pick.transport].select;
            const own = busOf(board, pick.transport, pins, buses, pick.module.device.on?.[pick.transport]?.hz, alone, kept, alone && pick.module.device.logic === 'none', placed, spread);
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
            const second = pick.module.device.config?.primary && Object.values(board.devices).some((device) => device.config?.primary);
            modules[pick.use] = { module: pick.module.name, on: { [`${pick.transport}.${own}`]: wires }, ...(lines.length ? { pins: needed } : {}), ...(Object.keys(supply).length ? { supply } : {}), ...(second ? { config: { primary: false } } : {}) };
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

    // The picks of a shortfall, a module for each thing lacking, the same kind of module for one need.
    function picksFor(shortfalls, choice, transports) {
        return shortfalls.flatMap((shortfall, i) => {
            return Array.from({ length: shortfall.count }, (_, n) => ({
                use: shortfall.need.use ?? (shortfall.need.names?.[n] || undefined) ?? (shortfall.count > 1 ? `${shortfall.need.id ?? shortfall.need.class}_${n + 1}` : shortfall.need.id ?? shortfall.need.class),
                module: choice[i],
                transport: transports[i],
                need: shortfall.need,
                way: choice[i].way,
            }));
        });
    }

    // Tries the ways to wire a choice of modules; the checks of the tools take the first that holds.
    // resource_limit of ledc: the channels the ways of the parts take (ledc of a way), beside those the outputs took
    function ledcShort(board, shortfalls, choice, taken) {
        const judgement = judgementsOf('resource_limit').find((item) => item.resource === 'ledc');
        const have = board.mcu.facts.frequency_sources?.ledc?.outputs;
        if (!judgement || have === undefined) return null;
        const asked = taken + choice.reduce((sum, module, i) => sum + shortfalls[i].count * (module.way?.ledc ?? module.device?.ways?.[0]?.ledc ?? 0), 0);
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
            // SPI parts on hosts of their own first; when the pins or the hosts run out that way, the same parts sharing hosts
            const apart = projectOf(name, board, picks, unused);
            const project = apart.problem ? projectOf(name, board, picks, unused, false) : apart;
            if (project.problem) {
                problems.add(project.problem);
                continue;
            }
            const checks = checksOf(project);
            if (!checks.problems.length) return { project, picks, resolved: checks.resolved };
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
            for (const wires of [...Object.values(on || {}), pins || {}]) for (const [line, pin] of Object.entries(wires)) rows.push({ what: pick.use, line, pin });
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
                pick.way.lines.forEach((line, i) => lines.push(pick.need.output ? { line: t('channel {0}', pick.need.channel + i), to: `GPIO ${pins[line]}${i ? `, ${t('half a period later')}` : ''}` } : { line, to: `GPIO ${pins[line]}` }));
                return { use: pick.use, title: pick.module.title, lines };
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
            for (const [line, pin] of Object.entries(pins || {})) lines.push({ line, to: `GPIO ${pin}` });
            for (const [line, from] of Object.entries(supply || {})) lines.push({ line, to: from });
            if (Object.keys(supply || {}).length) lines.push({ line: 'GND', to: 'GND' });
            const number = pick.use.match(/_(\d+)$/)?.[1];
            return { use: pick.use, title: number ? `${pick.module.title} ${number}` : pick.module.title, lines };
        });
    }

    // What each module puts on the lines of the chip, against what its pins take.
    function levelsOf(resolved, picks, base, project) {
        const lines = [];
        const shifted = [];
        const wired = (pick) => wiringOf(base, project, [pick])[0].lines.filter((wire) => /^GPIO/.test(wire.to)).length;
        const limit = resolved.mcu.facts.gpio.high_mv_max;
        for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
            const low = pick.module.device.high_min_mv ?? pick.module.device.ways?.[0]?.high_min_mv;
            if (low > CHIP_HIGH_MV) {
                lines.push({ level: 'do', text: t('{0}: it takes {1} V as high and this chip gives {2} V: put a level shifter on its line', pick.module.title, low / 1000, CHIP_HIGH_MV / 1000) });
                shifted.push({ both: false, lines: wired(pick) });
                continue;
            }
            const logic = resolved.devices[`${pick.use}_${pick.module.part}`]?.logic;
            if (logic === 'none') continue;
            const mv = logic ? lineMv(resolved, logic) : null;
            if (mv === null || limit === undefined) lines.push({ level: 'unknown', text: t('{0}: the level of its lines against this chip is not in the data', pick.module.title) });
            else if (mv > limit) {
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

    function priceOf(doc, picks, currency, addons = []) {
        const own = rangeOf(doc.price, currency);
        const missing = own ? [] : [doc.title ?? doc.name];
        const unpriced = own ? [] : [{ title: doc.title ?? doc.name, item: `boards/${doc.name}` }];
        let low = own ? own[0] : 0;
        let high = own ? own[1] : 0;
        let known = Boolean(own);
        const packs = [];
        const counted = new Map();
        for (const pick of picks.filter((item) => !item.way)) counted.set(pick.module.name, { title: pick.module.title, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
        for (const item of addons) counted.set(item.name, item);
        for (const [name, { title, count }] of counted) {
            const kind = name in (catalog.addons ?? {}) ? 'addons' : 'modules';
            const price = catalog[kind][name].price;
            const range = rangeOf(price, currency);
            if (range) {
                // what is sold by the pack is paid for by the pack
                const bought = Math.max(count, Math.min(...Object.values(price).map((offer) => offer.qty ?? 1)));
                low += range[0] * bought;
                high += range[1] * bought;
                if (bought > count) packs.push({ title, bought, cost: cents(range[0] * bought) });
                known = true;
            } else {
                missing.push(title);
                unpriced.push({ title, item: `${kind}/${name}` });
            }
        }
        return { low: cents(low), high: cents(high), currency, missing, unpriced, known, packs };
    }

    function kitsOfBoard(name, wanted) {
        const doc = catalog.boards[name];
        const board = loader.resolve(doc);
        const says = [];
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
        for (const [part] of unasked) {
            const brought = broughtBy(part);
            if (!brought) unused.devices[part] = { used: false };
            else unused.modules[brought[0]] = { module: brought[1].module, devices: { ...unused.modules[brought[0]]?.devices, [part.slice(brought[0].length + 1)]: { used: false } } };
        }
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
            if (answering.length < need.count) shortfalls.push({ need, count: need.count - answering.length });
        }
        if (!shortfalls.length && !unasked.length) return [kit(name, doc, board, says, null, [])];
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
            const item = result.project ? kit(name, doc, result.resolved, [...says, ...also], result.project, result.picks, board) : { name, title: doc.title ?? name, fits: false, says: [...says, { level: 'no', text: result.problem, ...(result.judgement ? { judgement: result.judgement } : {}) }], modules: [], wires: [], price: null, project: null };
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

        function kit(boardName, source, resolved, reasons, project, picks, base) {
            const counted = new Map();
            for (const pick of picks.filter((item) => !item.way)) counted.set(pick.module.name, { ...pick, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
            const pictureOf = (name) => Object.values(catalog.modules[name]?.images ?? {})[0];
            const modules = [...counted.values()].map((pick) => ({ name: pick.module.name, title: pick.module.title, count: pick.count, on: pick.transport,
                ...(pictureOf(pick.module.name) ? { picture: `modules/${pick.module.name}/${pictureOf(pick.module.name).file}`, credit: pictureOf(pick.module.name).source } : {}) }));
            const named = (item) => `${item.count > 1 ? `${item.count} x ` : ''}${item.title}`;
            const lines = [...reasons];
            const arduino = platform?.ecosystem === 'arduino';
            for (const item of modules) lines.push({ level: 'yes', text: t('{0} on {1}', named(item), item.on.toUpperCase()) });
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
            for (const pick of picks.filter((item) => item.module.own)) lines.push({ level: 'do', text: t('{0}: your own part, not in the catalog: {1}', pick.module.title, [...Object.entries(project.devices[pick.use].pins ?? {}).map(([line, pin]) => `${line} GPIO ${pin}`), ...Object.keys(project.devices[pick.use].on ?? {}).map((bus) => bus.toUpperCase())].join(', ') || t('no lines')) });
            for (const pick of new Map(picks.filter((item) => item.way && !item.need.output && !item.module.own).map((item) => [item.need.id, item])).values()) lines.push({ level: 'do', text: t('{0}: no part of the catalog, the kit only gives it pins: {1}', pick.module.title, pick.way.lines.join(', ')) });
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
                // the wires list no supply that the data does not name
                const steps = pick.module.power.filter((step) => step.source === 'connector');
                if (!steps.length) lines.push({ level: 'unknown', text: t('{0}: what feeds it is not in the data', pick.module.title) });
                for (const step of steps.filter((item) => !item.volts)) lines.push({ level: 'unknown', text: t('{0}: the voltage of {1} is not in the data', pick.module.title, step.name) });
                if (!KIT_BUSES[pick.transport].fixed) continue;
                lines.push({ level: 'do', text: t('{0}: a ribbon to the {1} connector', pick.module.title, pick.transport.toUpperCase()) });
                lines.push({ level: 'unknown', text: t('{0}: its timings are measured on a board, and not on this one', pick.module.title) });
            }
            const price = priceOf({ ...source, price: board.price }, picks, wanted.currency, addons);
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
                        if (entry.strapping && entry.boot && entry.owners.length && !before[pin]?.owners.length) lines.push({ level: 'note', text: t(judgement.says, `GPIO ${pin}`, entry.boot.footnote ?? t('it selects {0}', entry.boot.selects.join(', '))), judgement: judgement.id, pin: +pin });
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
            if (unasked.length) lines.push({ level: 'note', text: t('what nobody asked for is worth about {0} {1}: a part by the price of its chip, or by the cheapest of its role', cents(unasked.reduce((sum, [, device]) => sum + worthOf(device), 0)), KIT_CURRENCY) });
            for (const title of price.missing) lines.push({ level: 'unknown', text: t('no price for {0}', title) });
            const fits = !none && (wanted.limits.price === undefined || !price.known || price.low <= wanted.limits.price);
            if (!fits) lines.push({ level: 'no', text: t('it costs at least {0} {1}', price.low, price.currency) });
            const title = source.title ?? boardName;
            const headline = [title, ...modules.map(named), ...addons.map(named)].join(' + ');
            const pictures = Object.values(board.images || {});
            const picture = pictures.find((item) => item.shows === 'front') ?? pictures[0];
            return { name: boardName, title, headline, libraries, addons, unasked: unasked.length, unaskedWorth: cents(unasked.reduce((sum, [, device]) => sum + worthOf(device), 0)), imported: Boolean(doc.origin), writable: !doc.origin && platform?.writes_projects !== false, picture: picture ? `boards/${boardName}/${picture.file}` : null, fits, says: lines, modules, wires: project ? wiresOf(base, project, picks) : [], wiring: project ? wiringOf(base, project, picks) : [], price, project, free: freePins(resolved).length };
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
            (a, b) => b.fits - a.fits || unknowns(a) - unknowns(b) || (a.unaskedWorth ?? 0) - (b.unaskedWorth ?? 0) || (budget && spent(a) - spent(b)) || a.modules.length + (a.addons?.length ?? 0) - b.modules.length - (b.addons?.length ?? 0) || a.wires.length - b.wires.length || (!budget && spent(a) - spent(b)) || a.name.localeCompare(b.name)
        );
    }

    // What a project keeps of how it was chosen, so that the choice can be read and made again.
    function selectionOf(kit, kits, answers, currency) {
        const others = kits.filter((item) => item !== kit);
        return {
            ...KIT_FORMAT,
            currency,
            answers,
            board: kit.name,
            modules: kit.modules.map(({ name, count, on }) => ({ name, count, on })),
            libraries: kit.libraries.map(({ name, version }) => ({ name, version })),
            says: kit.says.map(({ level, text, judgement }) => ({ level, text, ...(judgement ? { judgement } : {}) })),
            others: others.filter((item) => item.fits).map((item) => item.headline),
            rejected: others.filter((item) => !item.fits).map((item) => ({ board: item.name, why: item.says.filter((line) => line.level === 'no').map((line) => line.text) })),
        };
    }

    // The parts of the catalog a block can have, for the person to fix one: none for a block the board itself gives.
    function partsOfBlock(block) {
        const [need] = blocksInNeeds([{ ...block, part: undefined }]);
        if (!need || need.own || need.provides || need.output) return [];
        return [...new Map(modulesWith(need).map((module) => [module.name, { name: module.name, title: module.title }])).values()];
    }

    return { solve, holds, selectionOf, partsOfBlock };
}

if (typeof module !== 'undefined') module.exports = { kitSolver, auditSummary, auditedOrder, within };
