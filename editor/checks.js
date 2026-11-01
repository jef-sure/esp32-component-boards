// The checks of a document, as tools/check_format.py goes through them: the schema, the loader, the schema of
// the result, the rules and the pins. The page runs them on every change, the solver on every kit it makes.
'use strict';

function documentChecks({ schema, rules, loader, schemaReader, check, pinProblems }) {
    const isPlain = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
    const dropNulls = (v) => (isPlain(v) ? Object.fromEntries(Object.entries(v).filter(([, item]) => item !== null).map(([key, item]) => [key, dropNulls(item)])) : v);
    const reader = schemaReader(schema);
    const resolvedReader = schemaReader({ $defs: schema.$defs });
    const fileRules = { ...rules, rules: rules.rules.filter((rule) => rule.in_files) };

    return function checksOf(doc) {
        const problems = [];
        const say = (stage, text, path = null) => {
            if (!problems.some((problem) => problem.text === text)) problems.push({ stage, text, path });
        };
        for (const error of reader.errors(schema, doc.extends ? dropNulls(doc) : doc)) say('schema', `${error.path.join('.') || 'the file'}: ${error.message}`, error.path);
        // a board inherits what it covers, so its rules wait for the resolved board
        if (!['board', 'project'].includes(doc.kind)) for (const found of check(doc, fileRules)) say('rule', found.message);
        if (!['board', 'project', 'module'].includes(doc.kind)) return { problems, resolved: null, layers: doc };
        let resolved = null;
        let layers = doc;
        try {
            layers = loader.chain(structuredClone(doc));
            resolved = loader.resolve(doc);
        } catch (error) {
            say('resolve', error.message);
        }
        if (resolved) {
            for (const error of resolvedReader.errors({ $ref: '#/$defs/resolved' }, resolved)) say('resolved', `${error.path.join('.') || 'the board'}: ${error.message}`, error.path);
            try {
                for (const found of check(resolved, rules)) say('rule', found.message);
                for (const text of pinProblems(resolved)) say('pins', text);
            } catch (error) {
                say('rule', error.message);
            }
        }
        return { problems, resolved, layers };
    };
}

if (typeof module !== 'undefined') module.exports = { documentChecks };
