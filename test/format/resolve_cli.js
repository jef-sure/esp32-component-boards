// Runs resolve.js over what a file gives and prints the results, for check_format.py to compare with resolve.py.
'use strict';
const path = require('path');
const { boardResolver } = require('../../editor/resolve.js');
const { catalogOf, read } = require('./catalog_of.js');

const ROOTS = [path.join(__dirname, '../../catalog'), path.join(__dirname, 'catalog')];

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
