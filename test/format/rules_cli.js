// Runs rules.js over a directory of resolved boards and prints what it finds, for check_v2.py to compare with rules.py.
'use strict';
const fs = require('fs');
const path = require('path');
const { check } = require("../../editor/rules.js");
const data = JSON.parse(fs.readFileSync(path.join(__dirname, "../../catalog/rules.json")));
const out = {};
for (const name of fs.readdirSync(process.argv[2]).sort())
    out[name] = check(JSON.parse(fs.readFileSync(path.join(process.argv[2], name))), data);
console.log(JSON.stringify(out));
