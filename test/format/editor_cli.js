// Runs the engines of the editor over what a file gives and prints the results, for check_format.py to compare with Python.
'use strict';
const fs = require('fs');
const path = require('path');
const { schemaReader } = require('../../editor/schema.js');
const { catalogJson } = require('../../editor/resolve.js');
const { pinMap, pinProblems } = require('../../editor/pins.js');

const schema = JSON.parse(fs.readFileSync(path.join(__dirname, '../../catalog/format.schema.json')));
const raw = schemaReader(schema);
const resolved = schemaReader({ $ref: '#/$defs/resolved', $defs: schema.$defs });
const given = JSON.parse(fs.readFileSync(process.argv[2]));
const each = (docs, change) => Object.fromEntries(Object.entries(docs).map(([name, doc]) => [name, change(doc)]));

console.log(
    JSON.stringify({
        raw: each(given.raw, (doc) => raw.valid(schema, doc)),
        resolved: each(given.resolved, (doc) => resolved.valid({ $ref: '#/$defs/resolved' }, doc)),
        dumped: each(given.dumped, catalogJson),
        pins: each(given.wired, (board) => ({ map: pinMap(board), problems: pinProblems(board) })),
        keywords: given.keywords.map(([part, value]) => schemaReader(part).valid(part, value)),
    })
);
