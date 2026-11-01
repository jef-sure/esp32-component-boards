// The languages of the page. English is the source: a text is its own key, and a text with no translation stays
// English, so a new language is one file in lang/. {0} and the like are the values put into a text.
'use strict';

const LANGUAGES = { en: { title: 'English', texts: {} } };

function translate(language, text, ...values) {
    const found = LANGUAGES[language]?.texts[text] ?? text;
    return found.replace(/\{(\d)\}/g, (_, i) => values[+i]);
}

if (typeof module !== 'undefined') module.exports = { LANGUAGES, translate };
