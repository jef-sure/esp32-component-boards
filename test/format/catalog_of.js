// The catalog as the page holds it, from directories in the layout of catalog/.
'use strict';
const fs = require('fs');
const path = require('path');

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

module.exports = { catalogOf, read };
