// The Markdown a model writes in the dialog, as blocks and runs the page draws with Vue: no HTML is made from its text.
// What models use: headings, paragraphs, lists, a table, code, bold, italic, code in a line, links of the web.
'use strict';

const LIST_ITEM = /^(\s*)([-*+•]|\d+[.)])\s+(.*)$/;
const TABLE_RULE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$|^\s*\|\s*:?-+:?\s*\|\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const NESTED_INDENT = 2; // an item indented this much more than the one before it is under it

// The runs of a line: text, strong, em, code, link; what is not closed stays text.
function markdownRuns(text) {
    const runs = [];
    const plain = (value) => {
        if (!value) return;
        const last = runs[runs.length - 1];
        if (last?.kind === 'text') last.text += value;
        else runs.push({ kind: 'text', text: value });
    };
    let at = 0;
    while (at < text.length) {
        const rest = text.slice(at);
        const code = rest.match(/^`([^`]+)`/);
        const strong = rest.match(/^\*\*(?=\S)(.+?)(?<=\S)\*\*/) ?? rest.match(/^__(?=\S)(.+?)(?<=\S)__/);
        const em = rest.match(/^\*(?=[^\s*])(.+?)(?<=[^\s*])\*/) ?? (/\w/.test(text[at - 1] ?? '') ? null : rest.match(/^_(?=\S)(.+?)(?<=\S)_(?!\w)/));
        const link = rest.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/);
        if (code) runs.push({ kind: 'code', text: code[1] });
        else if (strong) runs.push({ kind: 'strong', runs: markdownRuns(strong[1]) });
        else if (em) runs.push({ kind: 'em', runs: markdownRuns(em[1]) });
        else if (link) runs.push({ kind: 'link', href: link[2], runs: markdownRuns(link[1]) });
        else {
            plain(text[at]);
            at += 1;
            continue;
        }
        at += (code ?? strong ?? em ?? link)[0].length;
    }
    return runs;
}

const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => markdownRuns(cell.trim()));

// The blocks of a text: heading, paragraph (lines), list (ordered, items with their own lists), table, code, rule.
function markdownBlocks(text) {
    const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
    const blocks = [];
    let at = 0;
    while (at < lines.length) {
        const line = lines[at];
        if (!line.trim()) {
            at += 1;
            continue;
        }
        const fence = line.match(/^\s*(```|~~~)/);
        if (fence) {
            const body = [];
            at += 1;
            while (at < lines.length && !lines[at].trim().startsWith(fence[1])) body.push(lines[at++]);
            blocks.push({ kind: 'code', text: body.join('\n') });
            at += 1;
            continue;
        }
        const heading = line.match(/^\s*(#{1,6})\s+(.*?)\s*#*\s*$/);
        if (heading) {
            blocks.push({ kind: 'heading', level: heading[1].length, runs: markdownRuns(heading[2]) });
            at += 1;
            continue;
        }
        if (RULE.test(line)) {
            blocks.push({ kind: 'rule' });
            at += 1;
            continue;
        }
        if (line.includes('|') && TABLE_RULE.test(lines[at + 1] ?? '')) {
            const head = cells(line);
            const rows = [];
            at += 2;
            while (at < lines.length && lines[at].includes('|') && lines[at].trim()) rows.push(cells(lines[at++]));
            blocks.push({ kind: 'table', head, rows });
            continue;
        }
        if (LIST_ITEM.test(line)) {
            // a stack of the lists open, by indent: a deeper item opens a list under the item before it
            const open = [];
            while (at < lines.length) {
                const item = lines[at].match(LIST_ITEM);
                if (!item) {
                    // an indented line goes on the item before it; anything else ends the list
                    if (!lines[at].trim() || !/^\s/.test(lines[at])) break;
                    open[open.length - 1].items.at(-1).lines.push(lines[at].trim());
                    at += 1;
                    continue;
                }
                const indent = item[1].length;
                const ordered = /\d/.test(item[2]);
                while (open.length > 1 && indent < open[open.length - 1].indent) open.pop();
                const top = open[open.length - 1];
                if (!top) open.push({ indent, ordered, items: [] });
                else if (indent >= top.indent + NESTED_INDENT && top.items.length) {
                    const last = top.items.at(-1);
                    last.list = { indent, ordered, items: [] };
                    open.push(last.list);
                }
                open[open.length - 1].items.push({ lines: [item[3]] });
                at += 1;
            }
            const done = (list) => ({ ordered: list.ordered, items: list.items.map((item) => ({ runs: markdownRuns(item.lines.join(' ')), ...(item.list ? { list: done(item.list) } : {}) })) });
            blocks.push({ kind: 'list', ...done(open[0]) });
            continue;
        }
        const paragraph = [];
        while (at < lines.length && lines[at].trim() && !LIST_ITEM.test(lines[at]) && !RULE.test(lines[at]) && !/^\s*(#{1,6}\s|```|~~~)/.test(lines[at])
               && !(lines[at].includes('|') && TABLE_RULE.test(lines[at + 1] ?? ''))) paragraph.push(markdownRuns(lines[at++].trim()));
        blocks.push({ kind: 'paragraph', lines: paragraph });
    }
    return blocks;
}

if (typeof module !== 'undefined') module.exports = { markdownBlocks, markdownRuns };
