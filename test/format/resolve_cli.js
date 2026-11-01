// Runs resolve.js over what a file gives and prints the results, for check_format.py to compare with resolve.py.
'use strict';
const fs = require('fs');
const path = require('path');
const { boardResolver } = require('../../editor/resolve.js');

const ROOTS = [path.join(__dirname, '../../catalog'), path.join(__dirname, 'catalog')];
const FILES = { mcu: 'mcu.json', devices: 'device.json', modules: 'module.json', boards: 'board.json', connectors: 'connector.json' };
const read = (file) => JSON.parse(fs.readFileSync(file));
const below = (dir) => (fs.existsSync(dir) ? fs.readdirSync(dir).sort().map((name) => path.join(dir, name)) : []);

function catalogOf(roots) {
    const catalog = { libraries: {} };
    for (const root of roots) {
        for (const [kind, file] of Object.entries(FILES)) {
            catalog[kind] = catalog[kind] || {};
            for (const dir of below(path.join(root, kind))) {
                const name = path.basename(dir);
                if (!(name in catalog[kind]) && fs.existsSync(path.join(dir, file))) catalog[kind][name] = read(path.join(dir, file));
            }
        }
        for (const ecosystem of below(path.join(root, 'libraries'))) {
            for (const dir of below(ecosystem).flatMap(below)) {
                const record = read(path.join(dir, 'library.json'));
                const id = `${record.ecosystem}/${record.owner}/${record.name}`;
                if (!(id in catalog.libraries)) catalog.libraries[id] = record;
            }
        }
    }
    return catalog;
}

const loader = boardResolver(catalogOf(ROOTS));
const given = read(process.argv[2]);

function attempt(call, ...args) {
    try {
        return call(...args);
    } catch (error) {
        if (error instanceof loader.Refused) return { refused: error.message };
        throw error;
    }
}

const resolved = Object.fromEntries(Object.entries(given.docs).map(([name, doc]) => [name, attempt(loader.resolve, doc)]));
const trust = Object.fromEntries(
    Object.entries(resolved)
        .filter(([, board]) => !board.refused)
        .map(([name, board]) => [name, Object.keys(board.devices).map((device) => loader.trust(board, `devices.${device}`, given.levels))])
);
console.log(
    JSON.stringify({
        resolved,
        trust,
        overlaid: given.overlaid.map(([doc, layers]) => attempt(loader.resolve, doc, layers)),
        versions: given.versions.map(([a, b, scheme]) => Math.sign(loader.compareVersions(a, b, scheme))),
        settings: given.settings.map((mcu) => attempt(loader.chipSettings, mcu)),
        devices: given.devices.map((device) => attempt(loader.applyType, device)),
        libraries: given.libraries.map(([id, version]) => attempt(loader.libraryAt, loader.load('libraries', id), version).chips),
    })
);
