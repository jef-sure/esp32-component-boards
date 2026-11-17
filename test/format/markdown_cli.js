// The Markdown of the dialog: what models write comes out as blocks, and nothing of the text can become HTML or a script.
// Prints the cases that went wrong, one a line; check_format.py runs it.
'use strict';
const { markdownBlocks } = require('../../editor/markdown.js');

const text = (runs) => runs.map((run) => (run.kind === 'text' || run.kind === 'code' ? run.text : `<${run.kind}>${text(run.runs)}`)).join('');
const cases = [
    ['**bold** and *em* and `code`', (b) => b[0].kind === 'paragraph' && text(b[0].lines[0]) === '<strong>bold and <em>em and code'],
    ['- one\n  goes on\n- two\n    - under two\n- three', (b) => b[0].kind === 'list' && b[0].items.length === 3 && text(b[0].items[0].runs) === 'one goes on' && b[0].items[1].list?.items.length === 1],
    ['1. one\n2. two', (b) => b[0].ordered === true && b[0].items.length === 2],
    ['| a | b |\n|---|:-:|\n| 1 | 2 |', (b) => b[0].kind === 'table' && b[0].head.length === 2 && b[0].rows.length === 1],
    ['## Why\ntext', (b) => b[0].kind === 'heading' && b[0].level === 2 && b[1].kind === 'paragraph'],
    ['```\n<script>x</script>\n```', (b) => b[0].kind === 'code' && b[0].text === '<script>x</script>'],
    ['[web](https://example.com) [bad](javascript:alert(1)) <b>raw</b>', (b) => {
        const runs = b[0].lines[0];
        return runs.filter((run) => run.kind === 'link').length === 1 && runs[0].href === 'https://example.com' && text(runs).includes('[bad](javascript:alert(1)) <b>raw</b>');
    }],
    ['snake_case_name and 2_000', (b) => text(b[0].lines[0]) === 'snake_case_name and 2_000'],
    ['line one\nline two', (b) => b[0].lines.length === 2],
    ['**not closed', (b) => text(b[0].lines[0]) === '**not closed'],
    ['text\n---\nmore', (b) => b.map((block) => block.kind).join() === 'paragraph,rule,paragraph'],
    ['- a\n- b\n---', (b) => b.map((block) => block.kind).join() === 'list,rule'],
];
const wrong = cases.filter(([source, holds]) => !holds(markdownBlocks(source))).map(([source]) => `markdown: ${JSON.stringify(source)}`);
process.stdout.write(wrong.join('\n'));
