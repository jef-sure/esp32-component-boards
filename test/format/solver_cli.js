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
const { kitSolver } = require('../../editor/solver.js');

const ROOT = path.join(__dirname, '../../catalog');
const CASES = path.join(__dirname, '../solver');
const catalog = catalogOf([ROOT]);
const loader = boardResolver(catalog);
const checksOf = documentChecks({ schema: read(path.join(ROOT, 'format.schema.json')), rules: read(path.join(ROOT, 'rules.json')), loader, schemaReader, check, pinProblems });
const rates = read(path.join(ROOT, 'rates.json')).rates;
const schema = read(path.join(ROOT, 'format.schema.json'));
const solver = kitSolver({ catalog, loader, questions: read(path.join(ROOT, 'questions.json')).questions, rates, levels: schema.$defs.level.enum, checksOf, pinMap });
const selections = schemaReader({ $defs: schema.$defs });

const wrong = [];
const projects = new Map();

// What every kit must hold, whatever the answers: the pins, the buses, the order.
function holdsForEvery(kits, say) {
    const lastFit = kits.map((kit) => kit.fits).lastIndexOf(true);
    if (lastFit >= 0 && kits.slice(0, lastFit).some((kit) => !kit.fits)) say('a kit that does not fit comes before one that does');
    for (const kit of kits) {
        if (!kit.project) continue;
        const board = loader.resolve(catalog.boards[kit.name]);
        const map = pinMap(board);
        const outside = Object.values(map).some((entry) => entry.connectors.length);
        for (const { pin, what, line } of kit.wires) {
            const entry = map[pin];
            const fine = entry && entry.state === 'free' && !entry.strapping && !entry.input_only && !(entry.notes || []).length && (!outside || entry.connectors.length);
            if (!fine && !what.includes(' ')) say(`${kit.name}: ${what} ${line} is on GPIO ${pin}`);
            if (what.includes(' ') && outside && !entry?.connectors.length) say(`${kit.name}: ${what} ${line} does not come out, GPIO ${pin}`);
            if (what.includes(' ') && !board.buses?.[what.split(' ')[0].toLowerCase()]?.[what.split(' ')[1]] && !fine) say(`${kit.name}: ${what} ${line} is on GPIO ${pin}`);
        }
        const uarts = Object.values(kit.project.modules).flatMap(({ on }) => Object.keys(on || {})).filter((bus) => bus.startsWith('uart.'));
        if (new Set(uarts).size !== uarts.length) say(`${kit.name}: two devices on one UART`);
        const devices = loader.resolve(kit.project).devices;
        const isDisplay = (use) => Object.keys(devices).some((name) => name.startsWith(`${use}_`) && (devices[name].classes || []).includes('display'));
        for (const [use, { on }] of Object.entries(kit.project.modules)) {
            for (const bus of Object.keys(on)) {
                const sharing = Object.entries(kit.project.modules).filter(([other, entry]) => other !== use && bus in (entry.on || {}));
                if (isDisplay(use) && !bus.startsWith('i2c.') && sharing.length) say(`${kit.name}: ${sharing[0][0]} shares the bus of the display, ${bus}`);
                const [kind, own] = bus.split('.');
                if (kind !== 'dsi' && !kit.wires.some((wire) => wire.what === `${kind.toUpperCase()} ${own}`)) say(`${kit.name}: the lines of ${bus} are not listed`);
                if (Object.values(board.devices).some((device) => (device.classes || []).includes('display') && bus in (device.on || {}))) say(`${kit.name}: ${use} joins the bus of a display, ${bus}`);
            }
        }
    }
}

const names = fs.readdirSync(CASES).sort();
for (const name of names) {
    const given = read(path.join(CASES, name));
    const prices = Object.entries(given.prices || {}).map(([board, range]) => [board, catalog.boards[board].price]);
    for (const [board, range] of Object.entries(given.prices || {})) catalog.boards[board].price = { shop: { shop: 'test', currency: 'EUR', range, date: '2026-11-01', source: 'the case' } };
    const kept = Object.keys(given.change || {}).map((board) => [board, catalog.boards[board]]);
    for (const [board, patch] of Object.entries(given.change || {})) catalog.boards[board] = loader.merge(structuredClone(catalog.boards[board]), patch);
    Object.assign(catalog.modules, given.modules || {});
    const keptRates = { ...rates };
    Object.assign(rates, given.rates || {});
    const kits = solver.solve(given.answers);
    const fit = kits.filter((kit) => kit.fits);
    const say = (text) => wrong.push(`${name}: ${text}`);
    const same = (kit, want) =>
        (!want.name || kit.name === want.name) &&
        JSON.stringify(kit.modules.map((item) => [item.name, item.count]).sort()) === JSON.stringify(Object.entries(want.modules).sort()) &&
        Object.entries(want.on || {}).every(([module, on]) => kit.modules.find((item) => item.name === module)?.on === on);
    if (given.first && !(fit[0] && same(fit[0], given.first))) say(`first is ${fit[0] ? `${fit[0].name} ${JSON.stringify(fit[0].modules)}` : 'nothing'}`);
    if (given.kit && !fit.some((kit) => same(kit, given.kit))) say(`no such kit: ${fit.map((kit) => `${kit.name} ${JSON.stringify(kit.modules)}`).join('; ')}`);
    if (given.fit && JSON.stringify([...new Set(fit.map((kit) => kit.name))].sort()) !== JSON.stringify(given.fit)) say(`fit ${fit.map((kit) => kit.name)}`);
    if (given.lines) {
        const kit = fit.find((item) => item.name === given.lines.board);
        if (kit?.wires.length !== given.lines.count) say(`${given.lines.board}: ${kit?.wires.length} wires`);
    }
    if (given.cost) {
        const kit = fit.find((item) => item.name === given.cost.board && (!given.cost.module || item.modules.some((module) => module.name === given.cost.module)));
        if (kit?.price.low !== given.cost.low) say(`${given.cost.board} costs at least ${kit?.price.low}`);
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
        if (!kit?.wires.length || kit.wires.some((wire) => given.avoids.pins.includes(wire.pin))) say(`${given.avoids.board} uses a pin it was told is in use`);
    }
    if (given.fed) {
        const kit = fit.find((item) => item.name === given.fed.board && item.project?.modules[given.fed.use]);
        if (JSON.stringify(kit?.project.modules[given.fed.use].supply) !== JSON.stringify(given.fed.supply)) say(`fed by ${JSON.stringify(kit?.project.modules[given.fed.use].supply)}`);
    }
    if (given.says && !kits.some((kit) => kit.says.some((line) => line.text.includes(given.says)))) say(`no kit says "${given.says}"`);
    for (const kit of fit) if (kit.project && checksOf(kit.project).problems.length) say(`${kit.name}: its project does not pass the checks`);
    holdsForEvery(kits, say);
    if (fit[0]) for (const error of selections.errors({ $ref: '#/$defs/selection' }, JSON.parse(JSON.stringify(solver.selectionOf(fit[0], kits, given.answers, 'EUR'))))) say(`selection: ${error.path.join('.')}: ${error.message}`);
    for (const module of Object.keys(given.modules || {})) delete catalog.modules[module];
    Object.assign(rates, keptRates);
    for (const [board, price] of prices) catalog.boards[board].price = price;
    for (const [board, doc] of kept) catalog.boards[board] = doc;
    // a module of a case is not in the catalog the generator reads
    if (!given.modules) for (const kit of fit) if (kit.project && !projects.has(JSON.stringify(kit.project))) projects.set(JSON.stringify(kit.project), kit.project);
}
console.log(JSON.stringify({ cases: names.length, wrong, projects: [...projects.values()] }));
