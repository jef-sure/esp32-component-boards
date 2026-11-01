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
const MM_IN_INCH = 25.4;
const cents = (value) => Math.round(value * 100) / 100;

function kitSolver({ catalog, loader, questions, checksOf, pinMap }) {
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
        diagonal_in: { of: diagonalOf, short: (asked) => `the display is smaller than ${asked} inches`, unknown: 'the size of the display is not in the data' },
        range_mm: { of: (device) => device.provides?.nfc?.range_mm ?? null, short: (asked) => `no reader that reaches ${asked} mm`, unknown: 'the reading distance is not in the data' },
        swing_v: { of: (device) => (device.ways ? Math.max(...device.ways.map((way) => way.gives?.swing_v ?? 0)) : null), short: (asked) => `no way to wire it gives ${asked} V`, unknown: 'the swing is not in the data' },
    };

    function holds(question, answers) {
        return Object.entries(question.when || {}).every(([id, value]) => (value === true ? Boolean(answers[id]) : answers[id] === value));
    }

    function limitOf(need, wanted) {
        const question = questions.find((item) => item.limit?.of === need.class);
        const asked = question && wanted.limits[question.limit.measure];
        return asked ? { asked, key: question.limit.measure, ...MEASURES[question.limit.measure] } : null;
    }

    // What the answers ask for: {class or provides, count, title}, and the numbers that limit them.
    function wantedBy(answers) {
        const needs = [];
        const limits = {};
        for (const question of questions) {
            const answer = answers[question.id];
            if (!holds(question, answers) || answer === undefined || answer === null || answer === '' || answer === false || answer === 0) continue;
            if (question.limit) {
                limits[question.limit.measure] = answer;
                continue;
            }
            const choice = (question.choices || []).find((item) => item.value === answer);
            const need = choice ? choice.needs : question.needs;
            if (need) needs.push({ ...need, count: question.type === 'count' ? answer : 1, title: choice ? choice.text : question.text });
        }
        return { needs, limits };
    }

    function rangeOf(price) {
        const ranges = Object.values(price || {}).filter((offer) => offer.currency === KIT_CURRENCY && offer.range).map((offer) => offer.range);
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
    function busOf(board, kind, pins, added, hz, alone, kept) {
        const spec = KIT_BUSES[kind];
        const named = Object.keys(board.buses?.[kind] || {});
        const held = (own) => Object.values(board.devices).some((device) => `${kind}.${own}` in (device.on || {}) && (spec.fixed || (device.classes || []).includes('display')));
        if (spec.fixed) return named.find((own) => !held(own)) ?? null;
        const sharing = !spec.alone && !alone;
        const open = sharing && Object.keys(added[kind] || {}).find((own) => !kept.has(own));
        if (open) return open;
        const shared = sharing && named.find((own) => !held(own) && reaches(board, kind, own));
        if (shared) return shared;
        if (kind === 'i2c' && named.length) return null; // the glue makes one I2C master
        const kinds = Object.keys(KIT_BUSES).filter((other) => KIT_BUSES[other].host === spec.host);
        const taken = new Set(kinds.flatMap((other) => [...Object.keys(board.buses?.[other] || {}), ...Object.keys(added[other] || {})]));
        const own = hostNames(board, spec.host).find((name) => !taken.has(name));
        if (!own || pins.length < spec.lines.length) return null;
        added[kind] = { ...added[kind], [own]: { ...Object.fromEntries(spec.lines.map((line) => [line, pins.shift()])), ...(hz ? { hz } : {}) } };
        if (alone) kept.add(own);
        return own;
    }

    // A project of a board and the modules picked, or null when the pins or the hosts run out.
    function projectOf(name, board, picks) {
        const pins = freePins(board);
        const buses = {};
        const modules = {};
        const kept = new Set(); // the buses a display of its own holds
        for (const pick of picks) {
            if (pick.way) {
                if (pins.length < pick.way.lines.length) return null;
                modules[pick.use] = { module: pick.module.name, pins: Object.fromEntries(pick.way.lines.map((line) => [line, pins.shift()])) };
                continue;
            }
            const alone = (pick.module.device.classes || []).includes('display') && KIT_BUSES[pick.transport].select;
            const own = busOf(board, pick.transport, pins, buses, pick.module.device.on?.[pick.transport]?.hz, alone, kept);
            if (!own) return null;
            const wires = {};
            if (KIT_BUSES[pick.transport].select) {
                if (!pins.length) return null;
                wires.cs = pins.shift();
            }
            const lines = catalog.devices[pick.module.device.chip]?.on?.[pick.transport]?.lines || [];
            if (pins.length < lines.length) return null;
            const needed = Object.fromEntries(lines.map((line) => [line, pins.shift()]));
            const supply = supplyOf(board, pick.module);
            modules[pick.use] = { module: pick.module.name, on: { [`${pick.transport}.${own}`]: wires }, ...(lines.length ? { pins: needed } : {}), ...(Object.keys(supply).length ? { supply } : {}) };
        }
        return { ...KIT_FORMAT, kind: 'project', name: 'kit', extends: name, title: `${board.title} with modules`, ...(Object.keys(buses).length ? { buses } : {}), modules };
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
            const { device } = choice[i];
            const way = device.ways?.find((item) => !shortfall.limit || item.gives?.[shortfall.limit.key] >= shortfall.limit.asked);
            return Array.from({ length: shortfall.count }, (_, n) => ({
                use: shortfall.count > 1 ? `${shortfall.need.class}_${n + 1}` : shortfall.need.class,
                module: choice[i],
                transport: transports[i],
                need: shortfall.need,
                way,
            }));
        });
    }

    // Tries the ways to wire a choice of modules; the checks of the tools take the first that holds.
    function wired(name, board, shortfalls, choice) {
        const unfed = choice.find((module) => !supplyOf(board, module));
        if (unfed) return { problem: `${unfed.title}: no line of this board gives the voltage it takes` };
        const ways = choice.map((module) => transportsOf(module.device));
        if (ways.some((list) => !list.length)) return { problem: `${choice.find((module) => !transportsOf(module.device).length).title}: on no bus the solver wires` };
        let problem = 'the free pins, the hosts or the connectors of this board do not allow it';
        for (const transports of product(ways)) {
            const picks = picksFor(shortfalls, choice, transports);
            const channels = picks.reduce((sum, pick) => sum + (pick.way?.ledc ?? 0), 0);
            if (channels > (board.mcu.facts.hosts?.ledc ?? 0)) return { problem: `it takes ${channels} LEDC channels and this chip has ${board.mcu.facts.hosts?.ledc ?? 0}` };
            const project = projectOf(name, board, picks);
            if (!project) continue;
            const checks = checksOf(project);
            if (!checks.problems.length) return { project, picks, resolved: checks.resolved };
            problem = checks.problems[0].text;
        }
        return { problem };
    }

    function switchesOf(picks) {
        const notes = new Set();
        for (const pick of picks) {
            const control = pick.module.device.controls?.interface;
            const value = control?.values?.[pick.transport];
            if (control?.how === 'switch' && value) notes.add(`${pick.module.title}: set ${control.lines.map((line, i) => `${line} to ${value[i]}`).join(', ')} for ${pick.transport.toUpperCase()}`);
        }
        return [...notes];
    }

    // The lines of a kit as a person wires them.
    function wiresOf(board, project, picks) {
        const rows = [];
        const buses = new Set(picks.flatMap((pick) => Object.keys(project.modules[pick.use].on || {})));
        for (const bus of buses) {
            const [kind, own] = bus.split('.');
            for (const line of KIT_BUSES[kind].lines) rows.push({ what: `${kind.toUpperCase()} ${own}`, line, pin: project.buses?.[kind]?.[own]?.[line] ?? board.buses[kind][own][line].gpio });
        }
        for (const pick of picks) {
            const { on, pins } = project.modules[pick.use];
            for (const wires of [...Object.values(on || {}), pins || {}]) for (const [line, pin] of Object.entries(wires)) rows.push({ what: pick.use, line, pin });
        }
        return rows;
    }

    // What each module puts on the lines of the chip, against what its pins take.
    function levelsOf(resolved, picks) {
        const lines = [];
        const limit = resolved.mcu.facts.gpio.high_mv_max;
        for (const pick of new Map(picks.map((item) => [item.module.name, item])).values()) {
            const logic = resolved.devices[`${pick.use}_${pick.module.part}`]?.logic;
            if (logic === 'none') continue;
            const mv = logic ? lineMv(resolved, logic) : null;
            if (mv === null || limit === undefined) lines.push({ level: 'unknown', text: `${pick.module.title}: the level of its lines against this chip is not in the data` });
            else if (mv > limit) lines.push({ level: 'do', text: `${pick.module.title}: its lines go up to ${mv / 1000} V and the pins of this chip take ${limit / 1000} V: put a level shifter on them` });
        }
        return lines;
    }

    function priceOf(doc, picks) {
        const own = rangeOf(doc.price);
        const missing = own ? [] : [doc.title ?? doc.name];
        let low = own ? own[0] : 0;
        let high = own ? own[1] : 0;
        let known = Boolean(own);
        const counted = new Map();
        for (const pick of picks) counted.set(pick.module.name, { title: pick.module.title, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
        for (const [name, { title, count }] of counted) {
            const price = catalog.modules[name].price;
            const range = rangeOf(price);
            if (range) {
                // what is sold by the pack is paid for by the pack
                const bought = Math.max(count, Math.min(...Object.values(price).map((offer) => offer.qty ?? 1)));
                low += range[0] * bought;
                high += range[1] * bought;
                known = true;
            } else missing.push(title);
        }
        return { low: cents(low), high: cents(high), missing, known };
    }

    function kitsOfBoard(name, wanted) {
        const doc = catalog.boards[name];
        const board = loader.resolve(doc);
        const says = [];
        const say = (level, text) => says.push({ level, text });
        const rejected = () => [{ name, title: doc.title ?? name, fits: false, says, modules: [], wires: [], price: null, project: null }];
        const shortfalls = [];
        for (const need of wanted.needs) {
            if (need.provides) {
                if (!board.provides?.[need.provides]) {
                    say('no', `no ${titleOf(need)} on this board`);
                    return rejected();
                }
                say('yes', `${need.title} is on the board`);
                continue;
            }
            const limit = limitOf(need, wanted);
            const on = Object.values(board.devices).filter((device) => isClass(device, need));
            const large = on.filter((device) => !limit || limit.of(device) === null || limit.of(device) >= limit.asked);
            if (limit && on.length > large.length) {
                say('no', limit.short(limit.asked));
                return rejected();
            }
            if (limit && large.some((device) => limit.of(device) === null)) say('unknown', limit.unknown);
            if (large.length) say('yes', `${need.title} is on the board`);
            if (large.length < need.count) shortfalls.push({ need, count: need.count - large.length, limit });
        }
        if (!shortfalls.length) return [kit(name, doc, board, says, null, [])];
        const reaching = (need, module) => {
            const limit = limitOf(need, wanted);
            return !limit || limit.of(module.device) === null || limit.of(module.device) >= limit.asked;
        };
        const found = shortfalls.map(({ need }) => modulesWith(need).filter((module) => reaching(need, module)));
        const lacking = shortfalls.find((_, i) => !found[i].length);
        if (lacking) {
            const limit = limitOf(lacking.need, wanted);
            say('no', limit && modulesWith(lacking.need).length ? limit.short(limit.asked) : `the catalog has no module for: ${titleOf(lacking.need)}`);
            return rejected();
        }
        const kits = [];
        for (const choice of product(found)) {
            const result = wired(name, board, shortfalls, choice);
            if (result.project) kits.push(kit(name, doc, result.resolved, [...says], result.project, result.picks, board));
            else kits.push({ name, title: doc.title ?? name, fits: false, says: [...says, { level: 'no', text: result.problem }], modules: [], wires: [], price: null, project: null });
        }
        const good = kits.filter((item) => item.fits);
        return good.length ? good : kits.slice(0, 1);

        function kit(boardName, source, resolved, reasons, project, picks, base) {
            const counted = new Map();
            for (const pick of picks) counted.set(pick.module.name, { ...pick, count: (counted.get(pick.module.name)?.count ?? 0) + 1 });
            const modules = [...counted.values()].map((pick) => ({ name: pick.module.name, title: pick.module.title, count: pick.count, on: pick.transport, ...(pick.way ? { lines: pick.way.lines.length } : {}) }));
            const lines = [...reasons];
            for (const item of modules) lines.push({ level: 'yes', text: `${item.count > 1 ? `${item.count} x ` : ''}${item.title} on ${item.on.toUpperCase()}${item.lines ? `, ${item.lines} pin(s) each` : ''}` });
            for (const text of switchesOf(picks)) lines.push({ level: 'do', text });
            if (project) lines.push(...levelsOf(resolved, picks));
            for (const pick of new Map(picks.map((item) => [item.module.name, item])).values()) {
                const limit = limitOf(pick.need, wanted);
                if (limit && limit.of(pick.module.device) === null) lines.push({ level: 'unknown', text: `${pick.module.title}: ${limit.unknown}` });
                if (pick.way?.do) lines.push({ level: 'do', text: `${pick.module.title}: ${pick.way.do}` });
                const mount = catalog.modules[pick.module.name].mechanics?.do;
                if (mount) lines.push({ level: 'do', text: `${pick.module.title}: ${mount}` });
                if (!KIT_BUSES[pick.transport].fixed) continue;
                lines.push({ level: 'do', text: `${pick.module.title}: a ribbon to the ${pick.transport.toUpperCase()} connector` });
                lines.push({ level: 'unknown', text: `${pick.module.title}: its timings are measured on a board, and not on this one` });
            }
            const price = priceOf({ ...source, price: board.price }, picks);
            for (const title of price.missing) lines.push({ level: 'unknown', text: `no price for ${title}` });
            const fits = wanted.limits.price_eur === undefined || !price.known || price.low <= wanted.limits.price_eur;
            if (!fits) lines.push({ level: 'no', text: `it costs at least ${price.low} euro` });
            const supply = Object.entries(project?.modules || {}).flatMap(([use, entry]) => Object.entries(entry.supply || {}).map(([line, from]) => ({ what: use, line, from })));
            return { name: boardName, title: source.title ?? boardName, fits, says: lines, modules, wires: project ? wiresOf(base, project, picks) : [], supply, price, project, free: freePins(resolved).length };
        }
    }

    // Every board with a verdict: the kits that fit first, then the fewest unknowns, the fewest modules, the fewest wires.
    // The price counts last, unless a budget makes it a criterion: then it comes right after the unknowns, and a missing price is one of them.
    function solve(answers) {
        const wanted = wantedBy(answers);
        const budget = wanted.limits.price_eur !== undefined;
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
