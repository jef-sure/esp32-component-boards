// From the answers to the questions of catalog/questions.json to kits: a board of the catalog and the modules it
// lacks, with the wires. The solver only proposes: a kit is a project, and the checks of the tools decide about it.
'use strict';

const KIT_FORMAT = { format: 'jef-sure/boards', format_version: 2 };
const CHIP_HIGH_MV = 3300; // what a pin of an ESP32 gives as high
const MOST_MODULES = 6; // tried for one need: fifty thermometers on a hundred boards tell a person nothing more
// What the solver wires by itself, in the order it tries them. select: a line of its own for each device; alone: a bus
// for each device; fixed: the pins belong to the chip, so a module takes a free bus of the board, on a ribbon.
const KIT_BUSES = {
    i2c: { host: 'i2c', lines: ['sda', 'scl'] },
    spi: { host: 'spi', lines: ['mosi', 'miso', 'sclk'], select: true },
    qspi: { host: 'spi', lines: ['sclk', 'd0', 'd1', 'd2', 'd3'], select: true },
    uart: { host: 'uart', lines: ['tx', 'rx'], alone: true },
    dsi: { lines: [], fixed: true },
    gpio: { lines: [] }, // no bus: the lines are those of a way of the device
};
const KIT_CURRENCY = 'EUR';
const PRESCALES_TRIED = 8; // the smallest prescalers that fit: a larger one only loses resolution
const MM_IN_INCH = 25.4;
const cents = (value) => Math.round(value * 100) / 100;

function kitSolver({ catalog, loader, questions, roles = [], rates, levels, checksOf, pinMap, t = (text, ...values) => text.replace(/\{(\d)\}/g, (_, i) => values[+i]) }) {
    const shortOfPins = (wanted, left) => t('it takes {0} more pins and {1} free ones come out of this board', wanted, left);
    const valueAt = (node, path) => path.split('.').reduce((at, key) => (at === undefined || at === null ? undefined : at[key]), node);
    // A part of a need: by its class, or by the role it names. A variant it does not name stays in: the kit can only say so.
    const isClass = (device, need) => {
        const found = need.role ? Boolean(device.provides?.[need.role]) : (device.classes || []).includes(need.class) && Object.entries(need.where || {}).every(([path, value]) => valueAt(device, path) === value);
        const said = device.provides?.[need.id]?.variant;
        return found && (!need.variant || !said || said === need.variant);
    };
    const titleOf = (need) => need.title.toLowerCase();

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

    MEASURES.standard = { of: (device) => device.provides?.nfc?.standards ?? null, fits: (standards, asked) => standards.includes(asked), short: (asked) => t('no reader of {0}', asked), unknown: 'the standards are not in the data' };

    // What a question can ask for: a board holding such a part that nobody asked for gives more than the kit needs.
    const ASKABLE = new Set(questions.flatMap((question) => [question.needs, ...(question.choices || []).map((choice) => choice.needs)]).map((need) => need?.class));

    const roleOf = (id) => roles.flatMap((group) => group.roles).find((role) => role.id === id);

    // Blocks of one role and variant are one need: the same part for each, under the names of the blocks.
    function blocksInNeeds(blocks) {
        const same = new Map();
        for (const block of blocks) {
            const key = `${block.role}/${block.variant ?? ''}`;
            same.set(key, [...(same.get(key) ?? []), block]);
        }
        return [...same.values()].map((group) => {
            const role = roleOf(group[0].role);
            const variant = role.variants?.find((item) => item.id === group[0].variant);
            return { ...(variant?.needs ?? role.needs ?? { role: role.id }), id: role.id, variant: group[0].variant, count: group.length, names: group.map((block) => block.name), title: t(role.text) };
        });
    }

    function holds(question, answers) {
        return Object.entries(question.when || {}).every(([id, value]) => (value === true ? Boolean(answers[id]) : value.at_least ? answers[id] >= value.at_least : answers[id] === value));
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
        // xtal x (4 + sdm / 65536) / (2 x (o_div + 2)), then a whole divider of I2S. The multiplier runs from 350 to 500 MHz.
        apll(source, output) {
            if (output.bits) return [];
            const settings = [];
            for (let total = Math.ceil(source.min_hz / output.hz); total <= Math.floor(source.max_hz / output.hz) && total <= 1024; total++) {
                for (let div = 0; div < 32; div++) {
                    const multiplier = output.hz * total * 2 * (div + 2);
                    if (multiplier < 350e6 || multiplier > 500e6) continue;
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
    function limitsOf(need, wanted) {
        return questions.filter((item) => item.limit?.of && item.limit.of === need.class && wanted.limits[item.limit.measure] !== undefined)
            .map((item) => ({ asked: wanted.limits[item.limit.measure], fits: (value, asked) => value >= asked, ...MEASURES[item.limit.measure] }));
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
        const taken = String(answers.taken ?? '').match(/\d+/g)?.map(Number) ?? [];
        const unanswered = questions.filter((question) => MEASURES[question.limit?.measure]?.unanswered && holds(question, answers) && limits[question.limit.measure] === undefined);
        return { needs, limits, unanswered, outputs, taken, currency: answers.currency || KIT_CURRENCY };
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
    function freePins(board) {
        const map = pinMap(board);
        const hasOutside = Object.values(map).some((entry) => entry.connectors.length);
        return Object.entries(map)
            .filter(([, entry]) => entry.state === 'free' && !entry.strapping && !entry.input_only && !(entry.notes || []).length && (!hasOutside || entry.connectors.length))
            .map(([pin]) => +pin);
    }

    // A board with connectors in its data: a line is of use only if it comes out.
    function reaches(board, kind, own) {
        const map = pinMap(board);
        if (!Object.values(map).some((entry) => entry.connectors.length)) return true;
        return KIT_BUSES[kind].lines.every((line) => map[board.buses[kind][own][line]?.gpio]?.connectors.length);
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
    function busOf(board, kind, pins, added, hz, alone, kept, silent) {
        const spec = KIT_BUSES[kind];
        const named = Object.keys(board.buses?.[kind] || {});
        const held = (own) => Object.values(board.devices).some((device) => `${kind}.${own}` in (device.on || {}) && (spec.fixed || (device.classes || []).includes('display')));
        if (spec.fixed) return named.find((own) => !held(own)) ?? { problem: t('no free {0} bus on this board', kind.toUpperCase()) };
        const sharing = !spec.alone && !alone;
        const open = sharing && Object.keys(added[kind] || {}).find((own) => !kept.has(own));
        if (open) return open;
        const shared = sharing && named.find((own) => !held(own) && reaches(board, kind, own));
        if (shared) return shared;
        if (kind === 'i2c' && named.length) return { problem: t('the I2C bus of this board does not come out, or a display holds it, and the glue makes one I2C master') };
        const kinds = Object.keys(KIT_BUSES).filter((other) => KIT_BUSES[other].host === spec.host);
        const taken = new Set(kinds.flatMap((other) => [...Object.keys(board.buses?.[other] || {}), ...Object.keys(added[other] || {})]));
        const own = hostNames(board, spec.host).find((name) => !taken.has(name));
        if (!own) return { problem: t('no free {0} host on this board: {1}', spec.host.toUpperCase(), [...taken].join(', ') || t('it has none')) };
        const lines = spec.lines.filter((line) => !(silent && line === 'miso')); // a device with no line back leaves it unwired
        if (pins.length < lines.length) return { problem: shortOfPins(lines.length, pins.length) };
        added[kind] = { ...added[kind], [own]: { ...Object.fromEntries(spec.lines.map((line) => [line, lines.includes(line) ? pins.shift() : 'nc'])), ...(hz ? { hz } : {}) } };
        if (alone) kept.add(own);
        return own;
    }

    // A project of a board and the modules picked, or {problem} when the pins or the hosts run out.
    function projectOf(name, board, picks, taken, unused) {
        const pins = freePins(board).filter((pin) => !taken.includes(pin));
        const buses = {};
        const modules = {};
        const devices = { ...unused };
        const kept = new Set(); // the buses a display of its own holds
        for (const pick of picks) {
            if (pick.way) {
                if (pins.length < pick.way.lines.length) return { problem: shortOfPins(pick.way.lines.length, pins.length) };
                devices[pick.use] = { class: 'other', pins: Object.fromEntries(pick.way.lines.map((line) => [line, pins.shift()])) };
                continue;
            }
            // a part with no bus takes the lines of its first way
            if (pick.module.device.ways) {
                const { lines } = pick.module.device.ways[0];
                if (pins.length < lines.length) return { problem: shortOfPins(lines.length, pins.length) };
                modules[pick.use] = { module: pick.module.name, pins: Object.fromEntries(lines.map((line) => [line, pins.shift()])) };
                continue;
            }
            const alone = (pick.module.device.classes || []).includes('display') && KIT_BUSES[pick.transport].select;
            const own = busOf(board, pick.transport, pins, buses, pick.module.device.on?.[pick.transport]?.hz, alone, kept, alone && pick.module.device.logic === 'none');
            if (own.problem) return own;
            const wires = {};
            if (KIT_BUSES[pick.transport].select) {
                if (!pins.length) return { problem: shortOfPins(1, 0) };
                wires.cs = pins.shift();
            }
            const lines = catalog.devices[pick.module.device.chip]?.on?.[pick.transport]?.lines || [];
            if (pins.length < lines.length) return { problem: shortOfPins(lines.length, pins.length) };
            const needed = Object.fromEntries(lines.map((line) => [line, pins.shift()]));
            const supply = supplyOf(board, pick.module);
            // the board keeps its own display as the primary one
            const second = pick.module.device.config?.primary && Object.values(board.devices).some((device) => device.config?.primary);
            modules[pick.use] = { module: pick.module.name, on: { [`${pick.transport}.${own}`]: wires }, ...(lines.length ? { pins: needed } : {}), ...(Object.keys(supply).length ? { supply } : {}), ...(second ? { config: { primary: false } } : {}) };
        }
        return { ...KIT_FORMAT, kind: 'project', name: 'kit', extends: name, title: `${board.title} with modules`, ...(Object.keys(buses).length ? { buses } : {}), ...(Object.keys(devices).length ? { devices } : {}), modules };
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

    // The picks of a shortfall, a module for each thing lacking, the same kind of module for one need.
    function picksFor(shortfalls, choice, transports) {
        return shortfalls.flatMap((shortfall, i) => {
            return Array.from({ length: shortfall.count }, (_, n) => ({
                use: shortfall.need.use ?? (shortfall.need.names?.[n] || undefined) ?? (shortfall.count > 1 ? `${shortfall.need.id ?? shortfall.need.class}_${n + 1}` : shortfall.need.id ?? shortfall.need.class),
                module: choice[i],
                transport: transports[i],
                need: shortfall.need,
                way: shortfall.need.way,
            }));
        });
    }

    // Tries the ways to wire a choice of modules; the checks of the tools take the first that holds.
    function wired(name, board, shortfalls, choice, taken, unused) {
        const unfed = choice.find((module) => !supplyOf(board, module));
        if (unfed) return { problem: t('{0}: no line of this board gives the voltage it takes', unfed.title) };
        const ways = choice.map((module) => transportsOf(module.device));
        if (ways.some((list) => !list.length)) return { problem: t('{0}: on no bus the solver wires', choice.find((module) => !transportsOf(module.device).length).title) };
        const problems = new Set();
        for (const transports of product(ways)) {
            const picks = picksFor(shortfalls, choice, transports);
            const project = projectOf(name, board, picks, taken, unused);
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

    // The wires of each module, as a person with the module in hand connects them.
    function wiringOf(board, project, picks) {
        return picks.map((pick) => {
            const { on, pins, supply } = project.modules[pick.use] ?? project.devices[pick.use];
            const lines = [];
            if (pick.way) {
                pick.way.lines.forEach((line, i) => lines.push({ line: t('channel {0}', pick.need.channel + i), to: `GPIO ${pins[line]}${i ? `, ${t('half a period later')}` : ''}` }));
                return { use: pick.use, title: pick.module.title, lines };
            }
            for (const [bus, wires] of Object.entries(on || {})) {
                const [kind, own] = bus.split('.');
                for (const line of KIT_BUSES[kind].lines) {
                    if (line === 'miso' && pick.module.device.logic === 'none') continue; // it sends nothing back
                    const pin = project.buses?.[kind]?.[own]?.[line] ?? board.buses[kind][own][line].gpio;
                    if (pin !== 'nc') lines.push({ line, to: `GPIO ${pin}` });
                }
                for (const [line, pin] of Object.entries(wires)) lines.push({ line, to: `GPIO ${pin}` });
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
        const rejected = () => [{ name, title: doc.title ?? name, fits: false, says, modules: [], wires: [], unasked: 0, price: null, project: null }];
        const asked = (device) => wanted.needs.some((need) => isClass(device, need));
        const beneath = new Set(Object.values(board.devices).filter(asked).map((device) => device.config?.over)); // a touch asked for needs its display
        const unasked = Object.entries(board.devices).filter(([part, device]) => (device.classes || []).some((item) => ASKABLE.has(item)) && !asked(device) && !beneath.has(part));
        const unused = Object.fromEntries(unasked.map(([part]) => [part, { used: false }]));
        const shortfalls = [];
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
                if (!board.provides?.[need.provides]) {
                    // an import lists what its source describes: a chip that can do this leaves the question open
                    if (doc.origin && board.mcu.facts.provides?.[need.chip]) {
                        say('unknown', t('{0}: the chip can, the imported data does not say if this board does', titleOf(need)));
                        continue;
                    }
                    say('no', t('no {0} on this board', titleOf(need)));
                    return rejected();
                }
                say('yes', t('{0} is on the board', need.title));
                continue;
            }
            for (const question of wanted.unanswered) if (question.limit.of === need.class) say('unknown', t(MEASURES[question.limit.measure].unanswered));
            const limits = limitsOf(need, wanted);
            const on = Object.values(board.devices).filter((device) => isClass(device, need));
            const large = on.filter((device) => limits.every((limit) => meets(limit, device)));
            if (on.length > large.length) {
                const short = limits.find((limit) => on.some((device) => !meets(limit, device)));
                say('no', short.short(short.asked));
                return rejected();
            }
            for (const limit of limits) if (large.some((device) => limit.of(device) === null)) say('unknown', t(limit.unknown));
            if (need.variant && large.some((device) => !device.provides?.[need.id]?.variant)) say('unknown', t('{0} is on the board, and the data does not say of which variant', need.title));
            else if (large.length) say('yes', t('{0} is on the board', need.title));
            if (large.length < need.count) shortfalls.push({ need, count: need.count - large.length });
        }
        if (!shortfalls.length && !unasked.length) return [kit(name, doc, board, says, null, [])];
        const reaching = (need, module) => limitsOf(need, wanted).every((limit) => meets(limit, module.device));
        const output = (need) => ({ name: need.use, title: t('output {0}: {1} timer {2}, {3} Hz', need.index + 1, plan.sources[plan.chosen[need.index].name].title, plan.chosen[need.index].timer, wanted.outputs[need.index].hz), device: { ways: [need.way] }, power: [] });
        const found = shortfalls.map(({ need }) => (need.output ? [output(need)] : modulesWith(need).filter((module) => reaching(need, module)).slice(0, MOST_MODULES)));
        const lacking = shortfalls.find((_, i) => !found[i].length);
        if (lacking) {
            const short = limitsOf(lacking.need, wanted).find((limit) => modulesWith(lacking.need).some((module) => !meets(limit, module.device)));
            say('no', short ? short.short(short.asked) : t('the catalog has no module for: {0}', titleOf(lacking.need)));
            return rejected();
        }
        const kits = [];
        for (const choice of product(found)) {
            const result = wired(name, board, shortfalls, choice, wanted.taken, unused);
            if (result.project) kits.push(kit(name, doc, result.resolved, [...says], result.project, result.picks, board));
            else kits.push({ name, title: doc.title ?? name, fits: false, says: [...says, { level: 'no', text: result.problem }], modules: [], wires: [], price: null, project: null });
        }
        const good = kits.filter((item) => item.fits);
        if (good.length) return good;
        // no choice of modules can be wired: the reasons of all of them
        const reasons = [...new Set(kits.flatMap((item) => item.says.filter((line) => line.level === 'no').map((line) => line.text)))];
        return [{ ...kits[0], says: [...says, ...reasons.map((text) => ({ level: 'no', text }))] }];

        function kit(boardName, source, resolved, reasons, project, picks, base) {
            const counted = new Map();
            for (const pick of picks.filter((item) => !item.way)) counted.set(pick.module.name, { ...pick, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
            const modules = [...counted.values()].map((pick) => ({ name: pick.module.name, title: pick.module.title, count: pick.count, on: pick.transport }));
            const named = (item) => `${item.count > 1 ? `${item.count} x ` : ''}${item.title}`;
            const lines = [...reasons];
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
            if (doc.origin) lines.push({ level: 'do', text: t('imported from {0} {1}, not checked by us', doc.origin.from, doc.origin.ref) });
            if (picks.some((item) => !item.way) && !namesLines(base ?? board)) lines.push({ level: 'unknown', text: t('its supply lines are not in the data: check what feeds the modules') });
            if (picks.length && !Object.keys((base ?? board).connectors || {}).length) lines.push({ level: 'unknown', text: t('its connectors are not in the data: check that the wired pins come out') });
            const onLines = project ? levelsOf(resolved, picks, base, project) : { lines: [], shifted: [] };
            lines.push(...onLines.lines);
            const addons = addonsFor(onLines.shifted);
            for (const item of addons) lines.push({ level: 'do', text: t('{0} between the chip and these lines', named(item)) });
            for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
                for (const limit of limitsOf(pick.need, wanted)) {
                    const value = limit.of(pick.module.device);
                    if (value === null) lines.push({ level: 'unknown', text: `${pick.module.title}: ${t(limit.unknown)}` });
                    else if (limit.soft && !limit.fits(value, limit.asked)) lines.push({ level: 'unknown', text: limit.soft(pick.module.title, value, limit.asked) });
                }
                for (const text of catalog.modules[pick.module.name].do ?? []) lines.push({ level: 'do', text: `${pick.module.title}: ${t(text)}` });
                if (!KIT_BUSES[pick.transport].fixed) continue;
                lines.push({ level: 'do', text: t('{0}: a ribbon to the {1} connector', pick.module.title, pick.transport.toUpperCase()) });
                lines.push({ level: 'unknown', text: t('{0}: its timings are measured on a board, and not on this one', pick.module.title) });
            }
            const price = priceOf({ ...source, price: board.price }, picks, wanted.currency, addons);
            for (const pack of price.packs) lines.push({ level: 'do', text: t('{0}: sold by {1}, {2} {3} the pack', pack.title, pack.bought, pack.cost, price.currency) });
            if (project && loader.trust(resolved, 'connectors', levels)[0].endsWith('unchecked')) lines.push({ level: 'do', text: t('{0}: its connectors are from memory: check them against the board before wiring', source.title ?? boardName) });
            for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
                if (!resolved.devices[`${pick.use}_${pick.module.part}`]?.library) lines.push({ level: 'unknown', text: t('{0}: the catalog has no library for its chip', pick.module.title) });
            }
            for (const item of modules) {
                const entries = Object.values(catalog.modules[item.name].checked ?? {});
                if (entries.some((entry) => entry.level === 'unchecked' && entry.covers?.includes('power'))) lines.push({ level: 'do', text: t('{0}: its supply and levels are not measured', item.title) });
            }
            const libraries = librariesOf(resolved);
            for (const item of libraries.filter((library) => library.own)) lines.push({ level: 'do', text: t('{0} {1}: the project gets it, the program starts {2} with {3}()', item.name, item.version, item.devices.join(', '), item.call) });
            const started = libraries.filter((library) => !library.own);
            if (started.length) lines.push({ level: 'yes', text: t('the board starts: {0}', started.map((item) => `${item.name} ${item.version}`).join(', ')) });
            if (unasked.length) lines.push({ level: 'do', text: t('on the board and not asked: {0}. The project leaves them unused and their pins stay taken', unasked.map(([name, device]) => device.chip ?? name).join(', ')) });
            for (const title of price.missing) lines.push({ level: 'unknown', text: t('no price for {0}', title) });
            const fits = wanted.limits.price === undefined || !price.known || price.low <= wanted.limits.price;
            if (!fits) lines.push({ level: 'no', text: t('it costs at least {0} {1}', price.low, price.currency) });
            const title = source.title ?? boardName;
            const headline = [title, ...modules.map(named), ...addons.map(named)].join(' + ');
            const pictures = Object.values(board.images || {});
            const picture = pictures.find((item) => item.shows === 'front') ?? pictures[0];
            return { name: boardName, title, headline, libraries, unasked: unasked.length, imported: Boolean(doc.origin), picture: picture ? `boards/${boardName}/${picture.file}` : null, fits, says: lines, modules, wires: project ? wiresOf(base, project, picks) : [], wiring: project ? wiringOf(base, project, picks) : [], price, project, free: freePins(resolved).length };
        }
    }

    // Every board with a verdict: the kits that fit first, then the fewest unknowns, the fewest modules, the least nobody asked for, the fewest wires.
    // The price counts last, unless a budget makes it a criterion: then it comes right after the unknowns, and a missing price is one of them.
    function solve(answers) {
        modulesOfNeed.clear();
        const wanted = wantedBy(answers);
        const budget = wanted.limits.price !== undefined;
        const boards = Object.keys(catalog.boards).filter((name) => catalog.boards[name].kind === 'board').sort();
        const unknowns = (kit) => kit.says.filter((line) => line.level === 'unknown').length - (budget ? 0 : kit.price?.missing.length ?? 0);
        const spent = (kit) => (kit.price?.known ? kit.price.low : Infinity);
        return boards.flatMap((name) => kitsOfBoard(name, wanted)).sort(
            (a, b) => b.fits - a.fits || unknowns(a) - unknowns(b) || (budget && spent(a) - spent(b)) || a.modules.length - b.modules.length || a.unasked - b.unasked || a.wires.length - b.wires.length || (!budget && spent(a) - spent(b)) || a.name.localeCompare(b.name)
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
            says: kit.says.map(({ level, text }) => ({ level, text })),
            others: others.filter((item) => item.fits).map((item) => item.headline),
            rejected: others.filter((item) => !item.fits).map((item) => ({ board: item.name, why: item.says.filter((line) => line.level === 'no').map((line) => line.text) })),
        };
    }

    return { solve, holds, selectionOf };
}

if (typeof module !== 'undefined') module.exports = { kitSolver };
