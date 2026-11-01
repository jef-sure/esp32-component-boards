// Compiles every template of editor/app.js with the Vue of the page: a mistake in one leaves the page blank, and no other check sees it.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const EDITOR = path.join(__dirname, '../../editor');
// what the compiler of Vue asks of the DOM: to decode the entities of a text and of an attribute
const decoder = () => ({
    html: '',
    set innerHTML(value) { this.html = value; },
    get textContent() { return this.html; },
    get children() { const html = this.html; return [{ getAttribute: () => html.replace(/^<div foo="|">$/g, '') }]; },
});
const sandbox = { console, window: {}, document: { createElement: decoder, createElementNS: decoder }, navigator: { userAgent: '' }, setTimeout, Promise };
vm.createContext(sandbox);
vm.runInContext(`${fs.readFileSync(path.join(EDITOR, 'vendor/vue.global.prod.js'), 'utf8')};this.Vue = Vue;`, sandbox);
const source = fs.readFileSync(path.join(EDITOR, 'app.js'), 'utf8');
const templates = [...source.matchAll(/template: (`(?:[^`\\]|\\.)*`)/g)].map((match) => vm.runInNewContext(match[1]));
let wrong = 0;
for (const template of templates) {
    try {
        sandbox.Vue.compile(template);
    } catch (error) {
        console.log(`a template of the page does not compile: ${error.message}`);
        wrong += 1;
    }
}
console.log(`the page: ${templates.length} templates, ${wrong} wrong`);
process.exit(wrong || !templates.length ? 1 : 0);
