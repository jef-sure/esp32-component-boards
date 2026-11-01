// Every text of the page and of the catalog's questions has a translation in each language of editor/lang/.
'use strict';
const fs = require('fs');
const path = require('path');
const EDITOR = path.join(__dirname, '../../editor');
const { LANGUAGES, translate } = require(path.join(EDITOR, 'lang.js'));
global.LANGUAGES = LANGUAGES;
for (const name of fs.readdirSync(path.join(EDITOR, 'lang'))) require(path.join(EDITOR, 'lang', name));

const CATALOG = path.join(__dirname, '../../catalog');
const texts = new Set();
for (const file of ['solver.js', 'app.js']) {
    const source = fs.readFileSync(path.join(EDITOR, file), 'utf8').replace(/translate\(store\.language, /g, 't(');
    for (const call of source.matchAll(/\bt\(((?:[^()]|\([^()]*\))*)/g)) {
        for (const quoted of call[1].matchAll(/(['"])((?:(?!\1).)+)\1/g)) if (/[a-z] |^[a-z]+$|\{0\}/.test(quoted[2])) texts.add(quoted[2]);
    }
}
for (const name of ['the size of the display is not in the data', 'the reading distance is not in the data', 'the standards are not in the data']) texts.add(name);
for (const question of JSON.parse(fs.readFileSync(path.join(CATALOG, 'questions.json'))).questions) {
    texts.add(question.text);
    for (const choice of question.choices || []) texts.add(choice.text);
}
const read = (file) => JSON.parse(fs.readFileSync(file));
for (const group of read(path.join(CATALOG, 'roles.json')).groups) {
    texts.add(group.text);
    for (const role of group.roles) {
        texts.add(role.text);
        for (const variant of role.variants || []) texts.add(variant.text);
    }
}
for (const name of fs.readdirSync(path.join(CATALOG, 'modules'))) {
    for (const text of read(path.join(CATALOG, 'modules', name, 'module.json')).do ?? []) texts.add(text);
}
const skip = new Set(['question.text', 'choice.text', 'create']);
let missing = 0;
for (const [code, language] of Object.entries(LANGUAGES)) {
    if (code === 'en') continue;
    for (const text of texts) {
        if (!skip.has(text) && !(text in language.texts)) {
            console.log(`${code}: no translation: ${text}`);
            missing += 1;
        }
    }
}
console.log(`languages: ${Object.keys(LANGUAGES).length}, ${texts.size} texts, ${missing} missing`);
process.exit(missing ? 1 : 0);
