// From the answers to the questions of catalog/questions.json to kits: a board of the catalog and the modules it
// lacks, with the wires. The solver only proposes: a kit is a project, and the checks of the tools decide about it.
'use strict';

const KIT_FORMAT = { format: 'jef-sure/boards', format_version: 2 };
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

function kitSolver({ catalog, loader, questions, rates, checksOf, pinMap, t = (text, ...values) => text.replace(/\{(\d)\}/g, (_, i) => values[+i]) }) {
    const shortOfPins = (wanted, left) => t('it takes {0} more pins and {1} free ones come out of this board', wanted, left);
    const valueAt = (node, path) => path.split('.').reduce((at, key) => (at === undefined || at === null ? undefined : at[key]), node);
    const isClass = (device, need) => (device.classes || []).includes(need.class) && Object.entries(need.where || {}).every(([path, value]) => valueAt(device, path) === value);
    const titleOf = (need) => need.title.toLowerCase();

    function diagonalOf(device) {
        const panel = device.config?.panel;
        const [width, height] = panel?.mm_w ? [panel.mm_w, panel.mm_h] : panel?.window_mm ?? [];
        return width ? Math.hypot(width, height) / MM_IN_INCH : null;
    }

    // What a question can limit: where the figure lies, and what to say when a part falls short or has no figure.
    const MEASURES = {
        diagonal_in: { of: diagonalOf, short: (asked) => t('the display is smaller than {0} inches', asked), unknown: 'the size of the display is not in the data' },
        range_mm: { of: (device) => device.provides?.nfc?.range_mm ?? null, short: (asked) => t('no reader that reaches {0} mm', asked), unknown: 'the reading distance is not in the data' },
    };

    function holds(question, answers) {
        return Object.entries(question.when || {}).every(([id, value]) => (value === true ? Boolean(answers[id]) : answers[id] === value));
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

    function limitOf(need, wanted) {
        const question = questions.find((item) => item.limit?.of === need.class);
        const asked = question && wanted.limits[question.limit.measure];
        return asked ? { asked, ...MEASURES[question.limit.measure] } : null;
    }

    // What the answers ask for: {class or provides, count, title}, and the numbers that limit them.
    function wantedBy(answers) {
        const needs = [];
        const limits = {};
        for (const question of questions) {
            const answer = answers[question.id];
            if (!holds(question, answers) || answer === undefined || answer === null || answer === '' || answer === false || answer === 0) continue;
            const choice = (question.choices || []).find((item) => item.value === answer);
            if (question.limit) {
                limits[question.limit.measure] = answer;
                continue;
            }
            const need = choice ? choice.needs : question.needs;
            if (need) needs.push({ ...need, count: question.type === 'count' ? answer : 1, title: t(choice ? choice.text : question.text) });
        }
        const outputs = (answers.outputs || []).filter((output) => output.hz > 0).map((output) => ({ ...output, ppm: output.ppm === '' ? undefined : output.ppm, bits: output.kind === 'pwm' ? output.bits : undefined }));
        return { needs, limits, outputs, currency: answers.currency || KIT_CURRENCY };
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

    function modulesWith(need) {
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
        return found;
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

    // The line of the board for each step a module takes from it, the lowest that fits; null when a step has none.
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
    function projectOf(name, board, picks) {
        const pins = freePins(board);
        const buses = {};
        const modules = {};
        const devices = {};
        const kept = new Set(); // the buses a display of its own holds
        for (const pick of picks) {
            if (pick.way) {
                if (pins.length < pick.way.lines.length) return { problem: shortOfPins(pick.way.lines.length, pins.length) };
                devices[pick.use] = { class: 'other', pins: Object.fromEntries(pick.way.lines.map((line) => [line, pins.shift()])) };
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
                use: shortfall.need.use ?? (shortfall.count > 1 ? `${shortfall.need.class}_${n + 1}` : shortfall.need.class),
                module: choice[i],
                transport: transports[i],
                need: shortfall.need,
                way: shortfall.need.way,
            }));
        });
    }

    // Tries the ways to wire a choice of modules; the checks of the tools take the first that holds.
    function wired(name, board, shortfalls, choice) {
        const unfed = choice.find((module) => !supplyOf(board, module));
        if (unfed) return { problem: t('{0}: no line of this board gives the voltage it takes', unfed.title) };
        const ways = choice.map((module) => transportsOf(module.device));
        if (ways.some((list) => !list.length)) return { problem: t('{0}: on no bus the solver wires', choice.find((module) => !transportsOf(module.device).length).title) };
        const problems = new Set();
        for (const transports of product(ways)) {
            const picks = picksFor(shortfalls, choice, transports);
            const project = projectOf(name, board, picks);
            if (project.problem) {
                problems.add(project.problem);
                continue;
            }
            const checks = checksOf(project);
            if (!checks.problems.length) return { project, picks, resolved: checks.resolved };
            problems.add(checks.problems[0].text);
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
    function levelsOf(resolved, picks) {
        const lines = [];
        const limit = resolved.mcu.facts.gpio.high_mv_max;
        for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
            const logic = resolved.devices[`${pick.use}_${pick.module.part}`]?.logic;
            if (logic === 'none') continue;
            const mv = logic ? lineMv(resolved, logic) : null;
            if (mv === null || limit === undefined) lines.push({ level: 'unknown', text: t('{0}: the level of its lines against this chip is not in the data', pick.module.title) });
            else if (mv > limit) lines.push({ level: 'do', text: t('{0}: its lines go up to {1} V and the pins of this chip take {2} V: put a level shifter on them', pick.module.title, mv / 1000, limit / 1000) });
        }
        return lines;
    }

    function priceOf(doc, picks, currency) {
        const own = rangeOf(doc.price, currency);
        const missing = own ? [] : [doc.title ?? doc.name];
        let low = own ? own[0] : 0;
        let high = own ? own[1] : 0;
        let known = Boolean(own);
        const packs = [];
        const counted = new Map();
        for (const pick of picks.filter((item) => !item.way)) counted.set(pick.module.name, { title: pick.module.title, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
        for (const [name, { title, count }] of counted) {
            const price = catalog.modules[name].price;
            const range = rangeOf(price, currency);
            if (range) {
                // what is sold by the pack is paid for by the pack
                const bought = Math.max(count, Math.min(...Object.values(price).map((offer) => offer.qty ?? 1)));
                low += range[0] * bought;
                high += range[1] * bought;
                if (bought > count) packs.push({ title, bought, cost: cents(range[0] * bought) });
                known = true;
            } else missing.push(title);
        }
        return { low: cents(low), high: cents(high), currency, missing, known, packs };
    }

    function kitsOfBoard(name, wanted) {
        const doc = catalog.boards[name];
        const board = loader.resolve(doc);
        const says = [];
        const say = (level, text) => says.push({ level, text });
        const rejected = () => [{ name, title: doc.title ?? name, fits: false, says, modules: [], wires: [], price: null, project: null }];
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
                    say('no', t('no {0} on this board', titleOf(need)));
                    return rejected();
                }
                say('yes', t('{0} is on the board', need.title));
                continue;
            }
            const limit = limitOf(need, wanted);
            const on = Object.values(board.devices).filter((device) => isClass(device, need));
            const large = on.filter((device) => !limit || limit.of(device) === null || limit.of(device) >= limit.asked);
            if (limit && on.length > large.length) {
                say('no', limit.short(limit.asked));
                return rejected();
            }
            if (limit && large.some((device) => limit.of(device) === null)) say('unknown', t(limit.unknown));
            if (large.length) say('yes', t('{0} is on the board', need.title));
            if (large.length < need.count) shortfalls.push({ need, count: need.count - large.length });
        }
        if (!shortfalls.length) return [kit(name, doc, board, says, null, [])];
        const reaching = (need, module) => {
            const limit = limitOf(need, wanted);
            return !limit || limit.of(module.device) === null || limit.of(module.device) >= limit.asked;
        };
        const output = (need) => ({ name: need.use, title: t('output {0}: {1} timer {2}, {3} Hz', need.index + 1, plan.sources[plan.chosen[need.index].name].title, plan.chosen[need.index].timer, wanted.outputs[need.index].hz), device: { ways: [need.way] }, power: [] });
        const found = shortfalls.map(({ need }) => (need.output ? [output(need)] : modulesWith(need).filter((module) => reaching(need, module))));
        const lacking = shortfalls.find((_, i) => !found[i].length);
        if (lacking) {
            const limit = limitOf(lacking.need, wanted);
            say('no', limit && modulesWith(lacking.need).length ? limit.short(limit.asked) : t('the catalog has no module for: {0}', titleOf(lacking.need)));
            return rejected();
        }
        const kits = [];
        for (const choice of product(found)) {
            const result = wired(name, board, shortfalls, choice);
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
            if (project) lines.push(...levelsOf(resolved, picks));
            for (const pick of new Map(picks.filter((item) => !item.way).map((item) => [item.module.name, item])).values()) {
                const limit = limitOf(pick.need, wanted);
                if (limit && limit.of(pick.module.device) === null) lines.push({ level: 'unknown', text: `${pick.module.title}: ${t(limit.unknown)}` });
                for (const text of catalog.modules[pick.module.name].do ?? []) lines.push({ level: 'do', text: `${pick.module.title}: ${t(text)}` });
                if (!KIT_BUSES[pick.transport].fixed) continue;
                lines.push({ level: 'do', text: t('{0}: a ribbon to the {1} connector', pick.module.title, pick.transport.toUpperCase()) });
                lines.push({ level: 'unknown', text: t('{0}: its timings are measured on a board, and not on this one', pick.module.title) });
            }
            const price = priceOf({ ...source, price: board.price }, picks, wanted.currency);
            for (const pack of price.packs) lines.push({ level: 'do', text: t('{0}: sold by {1}, {2} {3} the pack', pack.title, pack.bought, pack.cost, price.currency) });
            for (const title of price.missing) lines.push({ level: 'unknown', text: t('no price for {0}', title) });
            const fits = wanted.limits.price === undefined || !price.known || price.low <= wanted.limits.price;
            if (!fits) lines.push({ level: 'no', text: t('it costs at least {0} {1}', price.low, price.currency) });
            const title = source.title ?? boardName;
            const headline = [title, ...modules.map(named)].join(' + ');
            const pictures = Object.values(board.images || {});
            const picture = pictures.find((item) => item.shows === 'front') ?? pictures[0];
            return { name: boardName, title, headline, picture: picture ? `boards/${boardName}/${picture.file}` : null, fits, says: lines, modules, wires: project ? wiresOf(base, project, picks) : [], wiring: project ? wiringOf(base, project, picks) : [], price, project, free: freePins(resolved).length };
        }
    }

    // Every board with a verdict: the kits that fit first, then the fewest unknowns, the fewest modules, the fewest wires.
    // The price counts last, unless a budget makes it a criterion: then it comes right after the unknowns, and a missing price is one of them.
    function solve(answers) {
        const wanted = wantedBy(answers);
        const budget = wanted.limits.price !== undefined;
        const boards = Object.keys(catalog.boards).filter((name) => catalog.boards[name].kind === 'board').sort();
        const unknowns = (kit) => kit.says.filter((line) => line.level === 'unknown').length - (budget ? 0 : kit.price?.missing.length ?? 0);
        const spent = (kit) => (kit.price?.known ? kit.price.low : Infinity);
        return boards.flatMap((name) => kitsOfBoard(name, wanted)).sort(
            (a, b) => b.fits - a.fits || unknowns(a) - unknowns(b) || (budget && spent(a) - spent(b)) || a.modules.length - b.modules.length || a.wires.length - b.wires.length || (!budget && spent(a) - spent(b)) || a.name.localeCompare(b.name)
        );
    }

    return { solve, holds };
}

if (typeof module !== 'undefined') module.exports = { kitSolver };
