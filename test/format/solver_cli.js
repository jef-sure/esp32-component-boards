// Runs the solver over the cases of test/solver/ and prints what is wrong, for check_format.py.
'use strict';
const fs = require('fs');
const path = require('path');
const { catalogOf, read } = require('./catalog_of.js');
const { boardResolver } = require('../../editor/resolve.js');
const { schemaReader } = require('../../editor/schema.js');
const { check } = require('../../editor/rules.js');
const { pinMap, pinProblems } = require('../../editor/pins.js');
const { documentChecks } = require('../../editor/checks.js');
const { kitSolver, auditSummary, auditedOrder, within } = require('../../editor/solver.js');

const ROOT = path.join(__dirname, '../../catalog');
const CASES = path.join(__dirname, '../solver');
const catalog = catalogOf([ROOT]);
const loader = boardResolver(catalog);
const checksOf = documentChecks({ schema: read(path.join(ROOT, 'format.schema.json')), rules: read(path.join(ROOT, 'rules.json')), loader, schemaReader, check, pinProblems });
const rates = read(path.join(ROOT, 'rates.json')).rates;
const schema = read(path.join(ROOT, 'format.schema.json'));
const roles = read(path.join(ROOT, 'roles.json')).groups;
const judgements = read(path.join(ROOT, 'judgements.json')).judgements;
const solver = kitSolver({ catalog, loader, questions: read(path.join(ROOT, 'questions.json')).questions, roles, rates, levels: schema.$defs.level.enum, checksOf, pinMap, judgements });
const selections = schemaReader({ $defs: schema.$defs });
// The catalog with imported/ behind it, for the cases that say "imported".
const wider = catalogOf([ROOT, path.join(__dirname, '../../imported-shops'), path.join(__dirname, '../../imported')]);
const widerLoader = boardResolver(wider);
const widerChecks = documentChecks({ schema, rules: read(path.join(ROOT, 'rules.json')), loader: widerLoader, schemaReader, check, pinProblems });
const auditsOf = (dir, depth) => (depth ? fs.readdirSync(dir, { withFileTypes: true }).filter((entry) => entry.isDirectory()).flatMap((entry) => auditsOf(path.join(dir, entry.name), depth - 1)) : fs.existsSync(path.join(dir, 'audit.json')) ? [[path.relative(path.join(ROOT, 'libraries'), dir), auditSummary(read(path.join(dir, 'audit.json')))]] : []);
const libraries = { all: read(path.join(ROOT, 'libraries/libraries.json')).libraries, byChip: read(path.join(ROOT, 'libraries/chip_libraries.json')).chips, audits: Object.fromEntries(auditsOf(path.join(ROOT, 'libraries'), 3)) };
const widerSolver = kitSolver({ catalog: wider, loader: widerLoader, questions: read(path.join(ROOT, 'questions.json')).questions, roles, libraries, rates, levels: schema.$defs.level.enum, checksOf: widerChecks, pinMap, judgements });

const wrong = [];
const projects = new Map();

// What every kit must hold, whatever the answers: the pins, the buses, the order.
function holdsForEvery(kits, say) {
    for (const kit of kits.filter((item) => item.project)) {
        const onHost = {};
        for (const module of Object.values(kit.project.modules ?? {})) for (const bus of Object.keys(module.on ?? {}).filter((key) => key.startsWith('spi.'))) onHost[bus] = (onHost[bus] ?? 0) + 1;
        for (const [bus, count] of Object.entries(onHost)) if (count > 6) say(`${kit.name}: ${count} parts on ${bus}, a host takes six`);
    }
    const lastFit = kits.map((kit) => kit.fits).lastIndexOf(true);
    if (lastFit >= 0 && kits.slice(0, lastFit).some((kit) => !kit.fits)) say('a kit that does not fit comes before one that does');
    for (const kit of kits) {
        if (!kit.project) continue;
        const board = loader.resolve(catalog.boards[kit.name]);
        const map = pinMap(board);
        const outside = Object.values(map).some((entry) => entry.connectors.length);
        for (const { pin, what, line } of kit.wires) {
            const entry = map[pin];
            // a strapping pin only where a judgement let it, and the kit says so; its note is the judgement's
            const judged = kit.says.some((said) => said.judgement === 'strapping_by_harm' && said.pin === pin);
            const costed = kit.says.some((said) => said.judgement === 'jtag_is_a_cost' && said.pin === pin);
            const notes = (entry?.notes || []).filter((note) => !note.startsWith('Strapping pin') && !(note === 'JTAG' && costed));
            const fine = entry && entry.state === 'free' && (!entry.strapping || judged) && !entry.input_only && !notes.length && (!outside || entry.connectors.length);
            if (!fine && !what.includes(' ')) say(`${kit.name}: ${what} ${line} is on GPIO ${pin}`);
            if (what.includes(' ') && outside && !entry?.connectors.length) say(`${kit.name}: ${what} ${line} does not come out, GPIO ${pin}`);
            if (what.includes(' ') && !board.buses?.[what.split(' ')[0].toLowerCase()]?.[what.split(' ')[1]] && !fine) say(`${kit.name}: ${what} ${line} is on GPIO ${pin}`);
        }
        const uarts = Object.values(kit.project.modules).flatMap(({ on }) => Object.keys(on || {})).filter((bus) => bus.startsWith('uart.'));
        if (new Set(uarts).size !== uarts.length) say(`${kit.name}: two devices on one UART`);
        const devices = loader.resolve(kit.project).devices;
        const isDisplay = (use) => Object.keys(devices).some((name) => name.startsWith(`${use}_`) && ((devices[name].classes || []).includes('display') || devices[name].provides?.display));
        for (const [use, { on }] of Object.entries(kit.project.modules)) {
            for (const bus of Object.keys(on || {})) {
                const sharing = Object.entries(kit.project.modules).filter(([other, entry]) => other !== use && bus in (entry.on || {}));
                if (isDisplay(use) && !bus.startsWith('i2c.') && sharing.length) say(`${kit.name}: ${sharing[0][0]} shares the bus of the display, ${bus}`);
                const [kind, own] = bus.split('.');
                if (kind !== 'dsi' && !kit.wires.some((wire) => wire.what === `${kind.toUpperCase()} ${own}`)) say(`${kit.name}: the lines of ${bus} are not listed`);
                if (Object.values(board.devices).some((device) => (device.classes || []).includes('display') && bus in (device.on || {}))) say(`${kit.name}: ${use} joins the bus of a display, ${bus}`);
            }
        }
    }
}

// the modules a case adds: written in it, or named, from the modules of the program of examples/local_boards
const PROGRAM_MODULES = path.join(__dirname, '../../examples/local_boards/components/local-boards/modules');
const modulesOf = (given) => (Array.isArray(given.modules) ? Object.fromEntries(given.modules.map((name) => [name, read(path.join(PROGRAM_MODULES, name, 'module.json'))])) : given.modules || {});
const names = fs.readdirSync(CASES).sort();
for (const name of names) {
    const given = read(path.join(CASES, name));
    const prices = Object.entries(given.prices || {}).map(([board, range]) => [board, catalog.boards[board].price]);
    for (const [board, range] of Object.entries(given.prices || {})) catalog.boards[board].price = { shop: { shop: 'test', currency: 'EUR', range, date: '2026-11-01', source: 'the case' } };
    const kept = Object.keys(given.change || {}).map((board) => [board, catalog.boards[board]]);
    for (const [board, patch] of Object.entries(given.change || {})) catalog.boards[board] = loader.merge(structuredClone(catalog.boards[board]), patch);
    const added = modulesOf(given);
    Object.assign(catalog.modules, added);
    const keptRates = { ...rates };
    Object.assign(rates, given.rates || {});
    const kits = (given.imported ? widerSolver : solver).solve(given.answers);
    const fit = kits.filter((kit) => kit.fits);
    const say = (text) => wrong.push(`${name}: ${text}`);
    const same = (kit, want) =>
        (!want.name || kit.name === want.name) &&
        JSON.stringify(kit.modules.map((item) => [item.name, item.count]).sort()) === JSON.stringify(Object.entries(want.modules).sort()) &&
        Object.entries(want.on || {}).every(([module, on]) => kit.modules.find((item) => item.name === module)?.on === on);
    if (given.first && !(fit[0] && same(fit[0], given.first))) say(`first is ${fit[0] ? `${fit[0].name} ${JSON.stringify(fit[0].modules)}` : 'nothing'}`);
    if (given.first_takes_a_module && !fit[0]?.modules.length) say(`first is ${fit[0]?.name ?? 'nothing'}, which takes no module`);
    if (given.kit && !fit.some((kit) => same(kit, given.kit))) say(`no such kit: ${fit.map((kit) => `${kit.name} ${JSON.stringify(kit.modules)}`).join('; ')}`);
    if (given.fit && JSON.stringify([...new Set(fit.map((kit) => kit.name))].sort()) !== JSON.stringify(given.fit)) say(`fit ${fit.map((kit) => kit.name)}`);
    if (given.lines) {
        const kit = fit.find((item) => item.name === given.lines.board);
        if (kit?.wires.length !== given.lines.count) say(`${given.lines.board}: ${kit?.wires.length} wires`);
    }
    if (given.cost) {
        const kit = fit.find((item) => item.name === given.cost.board && (!given.cost.module || item.modules.some((module) => module.name === given.cost.module)));
        if (kit?.price.low !== given.cost.low) say(`${given.cost.board} costs at least ${kit?.price.low}`);
        if (given.cost.high !== undefined && kit?.price.high !== given.cost.high) say(`${given.cost.board} costs at most ${kit?.price.high}`);
        // what of the price is the board and what the parts, as the card says it
        for (const share of ['board', 'parts'].filter((key) => given.cost[`of_${key}`])) {
            const range = kit?.price[share];
            if (JSON.stringify(range && [range.low, range.high]) !== JSON.stringify(given.cost[`of_${share}`])) say(`${given.cost.board}: the ${share} cost ${range && [range.low, range.high]}`);
        }
    }
    if (given.wiring) {
        const kit = fit.find((item) => item.name === given.wiring.board);
        const lines = kit?.wiring.find((module) => module.use === given.wiring.use)?.lines.map((wire) => wire.line);
        if (JSON.stringify(lines) !== JSON.stringify(given.wiring.lines)) say(`the wires of ${given.wiring.use}: ${lines}`);
    }
    if (given.picture && kits.find((item) => item.name === given.picture.board)?.picture !== given.picture.file) say('the picture of a kit is not there');
    if (given.quiet && kits.find((item) => item.name === given.quiet.board)?.says.some((line) => line.text.includes(given.quiet.text))) say(`${given.quiet.board} says "${given.quiet.text}"`);
    if (given.avoids) {
        const kit = fit.find((item) => item.name === given.avoids.board);
        // every pin of the project but those of the part the pins belong to
        const others = (doc) => Object.entries(doc ?? {}).filter(([use]) => use !== given.avoids.owner).flatMap(([, item]) => [...Object.values(item.pins ?? {}), ...Object.values(item.on ?? {}).flatMap((wires) => Object.values(wires))]);
        const used = [...others(kit?.project.devices), ...others(kit?.project.modules), ...Object.values(kit?.project.buses ?? {}).flatMap((hosts) => Object.values(hosts).flatMap((lines) => Object.values(lines)))];
        if (!kit?.project || used.some((pin) => given.avoids.pins.includes(pin))) say(`${given.avoids.board} uses a pin it was told is in use`);
    }
    // the wires of the parts whose titles hold these words come out on this edge: {board, edge, title}, or a list of them
    for (const side of [].concat(given.edges ?? [])) {
        const kit = fit.find((item) => item.name === side.board);
        const wires = (kit?.wiring ?? []).filter((part) => part.title.includes(side.title)).flatMap((part) => part.lines.filter((wire) => /^GPIO \d/.test(wire.to)));
        const off = wires.filter((wire) => !wire.where?.endsWith(`${side.edge} edge`));
        if (!wires.length || off.length) say(`${side.board}: ${side.title} on ${side.edge}: ${wires.length ? off.map((wire) => `${wire.to} ${wire.where ?? 'nowhere'}`).join(', ') : 'no wires'}`);
    }
    if (given.project) {
        // a value of the board of the program a kit writes, by its path there; null for none
        const kit = fit.find((item) => item.name === given.project.board);
        const value = given.project.at.split('.').reduce((node, key) => node?.[key], kit?.project) ?? null;
        if (JSON.stringify(value) !== JSON.stringify(given.project.is)) say(`${given.project.board}: ${given.project.at} is ${JSON.stringify(value)}`);
    }
    if (given.unused) {
        const kit = fit.find((item) => item.name === given.unused.board);
        const left = Object.entries(kit?.project?.devices ?? {}).filter(([, device]) => device.used === false).map(([part]) => part).sort();
        if (JSON.stringify(left) !== JSON.stringify(given.unused.parts)) say(`${given.unused.board} leaves alone: ${left}`);
    }
    if (given.shared) {
        const kit = fit.find((item) => item.name === given.shared.board);
        const [first, second] = given.shared.uses.map((use) => kit?.project.devices[use]?.pins ?? {});
        for (const line of given.shared.lines) if (first[line] === undefined || first[line] !== second[line]) say(`${line} is not one line of ${given.shared.uses}`);
        const own = given.shared.own ?? 'latch';
        if (first[own] === second[own]) say(`${given.shared.uses} share ${own}, which is their own`);
    }
    if (given.adc) {
        const kit = fit.find((item) => item.name === given.adc.board);
        for (const line of given.adc.lines ?? ['in']) {
            const pin = kit?.project.devices[given.adc.use]?.pins[line];
            if (!catalog.mcu[catalog.boards[given.adc.board].mcu?.target ?? 'esp32'].gpio.adc1.includes(pin)) say(`${given.adc.use}.${line} is on GPIO ${pin}, not on ADC1`);
        }
    }
    if (given.without && fit.some((kit) => [...kit.modules, ...(kit.addons ?? [])].some((module) => module.name === given.without))) say(`a kit with ${given.without} fits`);
    if (given.same_worth) {
        const worth = given.same_worth.map((board) => fit.find((kit) => kit.name === board)?.unaskedWorth);
        if (worth.some((value) => value === undefined) || new Set(worth).size > 1) say(`what nobody asked for weighs ${worth.join(' and ')} on ${given.same_worth.join(' and ')}`);
    }
    if (given.fed) {
        const kit = fit.find((item) => item.name === given.fed.board && item.project?.modules[given.fed.use]);
        if (JSON.stringify(kit?.project.modules[given.fed.use].supply) !== JSON.stringify(given.fed.supply)) say(`fed by ${JSON.stringify(kit?.project.modules[given.fed.use].supply)}`);
    }
    if (given.says && !kits.some((kit) => kit.says.some((line) => line.text.includes(given.says)))) say(`no kit says "${given.says}"`);
    // the parts of a kit as the project writes them: the class of each, and the level that means on of a line
    if (given.parts) {
        const kit = fit.find((item) => item.name === given.parts.board);
        for (const [use, want] of Object.entries(given.parts.devices)) {
            const device = kit?.project?.devices?.[use];
            if (device?.class !== want.class || Object.entries(want.active ?? {}).some(([line, level]) => device?.pins?.[line]?.active !== level)) say(`${use} of ${given.parts.board} is ${JSON.stringify(device)}`);
        }
    }
    // an order of audited libraries carries its basis: a row for each library, with the file of its audit
    for (const line of kits.flatMap((kit) => kit.says).filter((item) => item.text.includes('audited libraries in order: '))) {
        const named = line.text.split('audited libraries in order: ')[1].split(', ');
        const rows = line.basis?.split('\n') ?? [];
        if (rows.length !== named.length || named.some((name, i) => !rows[i].startsWith(`${name} `) || !rows[i].includes('/audit.json)'))) say(`the order ${named.join(', ')} has no basis for each library`);
    }
    // no line of the kit on these pins, as the strapping pins of a chip
    if (given.keeps_out) {
        const kit = fit.find((item) => item.name === given.keeps_out.board);
        const used = [];
        const walk = (node) => { if (typeof node === 'number') used.push(node); else if (node && typeof node === 'object') Object.entries(node).forEach(([key, value]) => key !== 'hz' && key !== 'address' && walk(value)); };
        walk({ buses: kit?.project?.buses, devices: kit?.project?.devices, modules: Object.values(kit?.project?.modules ?? {}).map((item) => ({ on: item.on, pins: item.pins })) });
        if (!kit) say(`no kit on ${given.keeps_out.board}`);
        for (const pin of given.keeps_out.pins) if (used.includes(pin)) say(`${given.keeps_out.board}: GPIO ${pin} is in the kit`);
    }
    // a line a judgement made is checked by its id, not by its text
    if (given.judged) {
        const kit = fit.find((item) => item.name === given.judged.board);
        const ids = new Set(kit?.says.filter((line) => line.judgement).map((line) => line.judgement));
        for (const id of given.judged.ids) if (!ids.has(id)) say(`${given.judged.board}: no line of the judgement ${id}`);
        for (const [bus, lines] of Object.entries(given.judged.buses ?? {})) for (const [line, pin] of Object.entries(lines)) if (kit?.project.buses?.spi?.[bus]?.[line] !== pin) say(`${given.judged.board}: ${bus}.${line} is ${kit?.project.buses?.spi?.[bus]?.[line]}, not ${pin}`);
        // the cs of the part on a host
        for (const [bus, pin] of Object.entries(given.judged.cs ?? {})) {
            const on = Object.values(kit?.project.modules ?? {}).map((item) => item.on?.[`spi.${bus}`]?.cs).filter((cs) => cs !== undefined);
            if (!on.includes(pin)) say(`${given.judged.board}: the cs on ${bus} is ${on.join(', ') || 'none'}, not ${pin}`);
        }
    }
    for (const kit of fit) if (kit.project && (given.imported ? widerChecks : checksOf)(kit.project).problems.length) say(`${kit.name}: its project does not pass the checks`);
    if (given.imported && !kits.some((kit) => kit.imported && kit.fits)) say('no imported board fits');
    if (!given.imported) holdsForEvery(kits, say);
    // the page writes a copy of the kit it chose: it is not among the others
    const selection = fit[0] && JSON.parse(JSON.stringify(solver.selectionOf([{ kit: JSON.parse(JSON.stringify(fit[0])), board: fit[0].name }], fit[0].name, kits, given.answers, 'EUR', 'case_project')));
    if (selection) for (const error of selections.errors({ $ref: '#/$defs/selection' }, selection)) say(`selection: ${error.path.join('.')}: ${error.message}`);
    if (selection?.others.includes(fit[0].headline)) say('selection: the kit chosen is among the others');
    for (const module of Object.keys(added)) delete catalog.modules[module];
    Object.assign(rates, keptRates);
    for (const [board, price] of prices) catalog.boards[board].price = price;
    for (const [board, doc] of kept) catalog.boards[board] = doc;
    // a module of a case is not in the catalog the generator reads
    if (!given.modules && !given.imported) for (const kit of fit) if (kit.project && !projects.has(JSON.stringify(kit.project))) projects.set(JSON.stringify(kit.project), kit.project);
}
// The order of audited libraries, on a table of its own: the real results change with every reading.
const heard = (statuses, high, medium, health = 0) => ({ statuses: { 'transports.spi': 'yes', 'several.several_readers': 'yes', 'several.shared_spi_bus': 'yes', ...statuses }, high, medium, health });
const table = {
    all: { a: { platforms: ['p'] }, b: { platforms: ['p'] }, c: { platforms: ['p'], requires: ['base'] }, base: { requires: ['unread'] }, d: { platforms: ['q'] }, e: { platforms: ['p'] }, f: { platforms: ['p'] }, g: { platforms: ['p'] }, unread: {} },
    byChip: { chip: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'none'] },
    audits: { a: heard({}, 1, 2), b: heard({}, 0, 9), c: heard({}, 0, 1), base: heard({}, 1, 1), d: heard({}, 0, 0), e: heard({ 'transports.spi': 'no' }, 0, 0), f: heard({ 'several.several_readers': 'partly', 'transports.spi': 'partly' }, 1, 2, 3), g: heard({ 'cards.x': 'yes', 'several.several_readers': 'no' }, 1, 2) },
};
const orderOf = (asked) => auditedOrder(table, { chip: 'chip', platform: 'p', bus: 'spi', ...asked }).map((item) => item.id).join(' ');
const expected = [[{}, 'b f a c g'], [{ several: true }, 'b f a c'], [{ standard: 'x' }, 'g'], [{ bus: 'uart' }, '']];
for (const [asked, order] of expected) if (orderOf(asked) !== order) wrong.push(`audited order for ${JSON.stringify(asked)}: ${orderOf(asked)}`);
const answering = auditedOrder(table, { chip: 'chip', platform: 'p', bus: 'spi' }).find((item) => item.id === 'c');
if (JSON.stringify([answering.health, answering.high, answering.medium, answering.unread]) !== JSON.stringify([0, 1, 2, ['unread']])) wrong.push('a library does not answer for what it requires');
// Ranges of manifests against the versions of a platform: a line meets a range when some release of it does.
for (const [version, range, meets] of [['5.5', '>=5.2.0', true], ['5.5', '>=5.5.2', true], ['5.5', '>=6.0', false], ['6.1', '^5.3', false], ['5.5', '^5.3', true],
    ['5.5', '~5.4', false], ['6.1', '>=5.3,<6.0', false], ['5.5', '>=5.3 <6.0', true], ['5.5', '*', true], ['5.5', 'git+https://x', true], ['5.5', '!=5.5', false], ['6.1', '>=5.0,!=6.0', true], ['6.1', '>=5.0 !=6.1', false]])
    if (within(version, range) !== meets) wrong.push(`${version} against ${range}: ${!meets}`);
console.log(JSON.stringify({ cases: names.length, wrong, projects: [...projects.values()] }));
