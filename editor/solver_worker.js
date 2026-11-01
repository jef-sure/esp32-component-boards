// The solver apart from the page: with a hundred boards an answer takes a second, and the page has to stay alive.
'use strict';

importScripts('schema.js', 'rules.js', 'resolve.js', 'pins.js', 'checks.js', 'solver.js', 'lang.js', 'lang/ru.js');

let solver = null;
let language = 'en';

function take({ catalog, schema, rules, questions, rates, roles }) {
    const loader = boardResolver(catalog);
    const checksOf = documentChecks({ schema, rules, loader, schemaReader, check, pinProblems });
    solver = kitSolver({ catalog, loader, questions, roles, rates, levels: schema.$defs.level.enum, t: (text, ...values) => translate(language, text, ...values), checksOf, pinMap });
}

onmessage = ({ data }) => {
    if (data.documents) take(data.documents);
    language = data.language;
    postMessage({ id: data.id, kits: solver.solve(data.answers) });
};
