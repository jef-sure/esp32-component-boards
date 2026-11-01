// The files of the editor in a browser: a folder opened by the File System Access API, or files read
// from an input where the browser has no such API, and then saved as downloads.
// Paths are relative to the catalog: boards/<name>/board.json.
'use strict';

const CATALOG_MARK = 'format.schema.json';
const LOCAL_BOARDS = ['components', 'local-boards']; // tools/resolve.py: LOCAL_BOARDS

async function readFolder(folder, prefix, files) {
    for await (const [name, handle] of folder.entries()) {
        if (handle.kind === 'directory') await readFolder(handle, `${prefix}${name}/`, files);
        else if (name.endsWith('.json')) files[`${prefix}${name}`] = await (await handle.getFile()).text();
    }
}

async function inFolder(folder, name, get) {
    try {
        return await folder[get](name);
    } catch (error) {
        if (error.name === 'NotFoundError' || error.name === 'TypeMismatchError') return null;
        throw error;
    }
}

const fileIn = (folder, name) => inFolder(folder, name, 'getFileHandle');
const folderIn = (folder, name) => inFolder(folder, name, 'getDirectoryHandle');

// The catalog a folder is or holds.
async function catalogOf(picked) {
    if (await fileIn(picked, CATALOG_MARK)) return picked;
    const inside = await folderIn(picked, 'catalog');
    return inside && (await fileIn(inside, CATALOG_MARK)) ? inside : null;
}

// The local-boards a folder is or holds. A program without them gets the folder.
async function localOf(picked) {
    const [parent, name] = LOCAL_BOARDS;
    if (picked.name === name) return picked;
    const components = await folderIn(picked, parent);
    const local = components && (await folderIn(components, name));
    if (local) return local;
    if (!(await fileIn(picked, 'CMakeLists.txt'))) return null;
    return (await picked.getDirectoryHandle(parent, { create: true })).getDirectoryHandle(name, { create: true });
}

const host = {
    folder: null,
    localFolder: null,

    get canOpenFolder() {
        return typeof window.showDirectoryPicker === 'function';
    },

    // The catalog beside the page, when a server gives it; null when it does not.
    async fetchCatalog() {
        let answer;
        try {
            answer = await fetch('../catalog/index.json');
        } catch {
            return null; // a page from file:// fetches nothing
        }
        if (!answer.ok) return null;
        const paths = await answer.json();
        const texts = await Promise.all(paths.map(async (path) => (await fetch(`../catalog/${path}`)).text()));
        return Object.fromEntries(paths.map((path, i) => [path, texts[i]]));
    },

    // A catalog, or a program with its local-boards: {local, files}.
    async openFolder() {
        const picked = await window.showDirectoryPicker({ mode: 'readwrite' });
        const files = {};
        const catalog = await catalogOf(picked);
        if (catalog) {
            await readFolder(catalog, '', files);
            this.folder = catalog;
            return { local: false, files };
        }
        const local = await localOf(picked);
        if (!local) throw new Error(`${picked.name}: neither a catalog nor a program: no ${CATALOG_MARK}, no ${LOCAL_BOARDS.join('/')}, no CMakeLists.txt`);
        await readFolder(local, '', files);
        this.localFolder = local;
        return { local: true, files };
    },

    // What an <input webkitdirectory> gives: the paths start at the folder picked.
    async readPicked(list) {
        const picked = [...list].filter((file) => file.name.endsWith('.json'));
        const paths = picked.map((file) => file.webkitRelativePath);
        const mark = paths.find((path) => path.endsWith(`/${CATALOG_MARK}`) && path.split('/').length <= 3);
        const local = `${LOCAL_BOARDS[1]}/`;
        const start = mark ? mark.slice(0, -CATALOG_MARK.length) : paths.find((path) => path.includes(local))?.replace(new RegExp(`${local}.*`), local);
        if (!start) throw new Error(`neither a catalog nor local-boards: no ${CATALOG_MARK}, no ${LOCAL_BOARDS.join('/')}`);
        const files = {};
        for (const file of picked) if (file.webkitRelativePath.startsWith(start)) files[file.webkitRelativePath.slice(start.length)] = await file.text();
        return { local: !mark, files };
    },

    async write(path, text, local = false) {
        const root = local ? this.localFolder : this.folder;
        if (!root) {
            const link = document.createElement('a');
            link.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
            link.download = path.split('/').pop();
            link.click();
            URL.revokeObjectURL(link.href);
            return false;
        }
        const parts = path.split('/');
        const name = parts.pop();
        let folder = root;
        for (const part of parts) folder = await folder.getDirectoryHandle(part, { create: true });
        const writable = await (await folder.getFileHandle(name, { create: true })).createWritable();
        await writable.write(text);
        await writable.close();
        return true;
    },
};
