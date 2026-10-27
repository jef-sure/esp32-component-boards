/*
 * The store of the boards editor: one board's data — the same JSON tools/boards_gen.py reads —
 * with the schema checked where a browser can: the buses a chip has, a display whole (its pixels
 * against its millimetres), a touch of a known kind, the calibration parsed back from what
 * dgx_di_calibrate_measure prints. The way of hw-fonts: Vue and Pinia from a CDN, no build step;
 * the file saved is the file the generator reads.
 */
const BoardFormat = {
    name: 'jef-sure/boards',
    version: 1
};

/* what the generator knows, mirrored: the hosts a chip has, the panel drivers and their
   depths, the character drivers and their geometries, the kinds of a touch */
const SpiHosts = { esp32: ['spi2', 'spi3'], esp32s3: ['spi2', 'spi3'], esp32p4: ['spi2', 'spi3'] };
const PanelDrivers = { jd9165: [16, 24], jd9365: [16, 24], nv3041a: [16], ili9341: [16] };
const CharacterDrivers = { hd44780: ['8x2', '16x2', '16x4', '20x2', '20x4', '40x2'] };
const TouchKinds = ['gt911', 'gsl3680', 'esp_lcd_touch'];
const OrientX = ['left-right', 'right-left'];
const OrientY = ['top-bottom', 'bottom-top'];

/* a bus of a kind the component sets up: the fields the generator asks of it. req: an error
   while empty; nullable: kept as null (a line the board does not wire); opt: the key itself
   gone while empty. A kind not here is still the board's data — every value a pin, a number
   or a word — kept for the program (board_bus_get), the sdio of a radio beside the chip */
const BusKinds = {
    spi:  { title: 'SPI',        own: 'a host of the chip: spi2, spi3', fields: { hz: 'opt', mosi: 'req', miso: 'req', sclk: 'req' } },
    qspi: { title: 'QSPI',       own: 'a host of the chip: spi2, spi3', fields: { hz: 'opt', d0: 'req', d1: 'req', d2: 'req', d3: 'req', sclk: 'req' } },
    i2c:  { title: 'I2C',        own: 'a port of the chip: i2c0',       fields: { sda: 'req', scl: 'req' } },
    i2s:  { title: 'I2S',        own: 'a port of the chip: i2s0',       fields: { mclk: 'req', bclk: 'req', ws: 'req', dout: 'req', din: 'nullable' } },
    dsi:  { title: 'MIPI-DSI',   own: 'the DSI of the chip: dsi0',      fields: { lanes: 'req', lane_mbps: 'req', phy_ldo_chan: 'req', phy_ldo_mv: 'req' } },
    p8:   { title: 'Intel 8080', own: 'any name',                       fields: { d0: 'req', d1: 'req', d2: 'req', d3: 'req', d4: 'req', d5: 'req', d6: 'req', d7: 'req', wr: 'req', rd: 'nullable', dc: 'req', hz: 'req' } }
};

/* the lines a panel of a bus kind carries itself: its strobes (a DSI panel has none, the
   bus is the panel's) */
const PanelStrobes = { spi: ['cs', 'dc'], qspi: ['cs'], p8: ['cs'], dsi: [] };

function busParts(name) {
    const s = String(name || '');
    const at = s.indexOf('.');
    return at < 0 ? [s, null] : [s.slice(0, at), s.slice(at + 1)];
}

function busOf(board, name) {
    const [kind, own] = busParts(name);
    if (!own || !(board.buses || {})[kind]) return undefined;
    return board.buses[kind][own];
}

function isInt(x) {
    return Number.isInteger(x);
}

/* the board checked, the generator's own questions asked where a browser can; what it answers
   is what tools/boards_gen.py would refuse the file for */
function boardProblems(b) {
    const P = [];
    if (!b.name || !/^[a-z0-9_]+$/.test(b.name)) P.push('the name is lowercase letters, digits and _ only');
    if (!b.title) P.push('no title');
    const module = !!b.module;
    const target = (b.mcu || {}).target;
    if (module) {
        if (b.mcu) P.push('a module rides a board\'s buses: no mcu of its own');
        if (b.buses && Object.keys(b.buses).length) P.push('a module rides the carrier board\'s buses: no buses of its own to wire');
        if (b.button) P.push('a module has no button of its own');
        if (b.touch || b.sound || b.sd) P.push('a module is a display for now: no touch, sound or sd of its own');
        if (!(b.display && CharacterDrivers[b.display.driver])) P.push('a module is a character display (hd44780) for now');
    } else if (!SpiHosts[target]) {
        P.push('the target is one of ' + Object.keys(SpiHosts).join(', '));
    }
    for (const [kind, named] of Object.entries(b.buses || {})) {
        for (const [own, bus] of Object.entries(named || {})) {
            const name = `${kind}.${own}`;
            if (kind === 'spi' || kind === 'qspi') {
                if (!module && SpiHosts[target] && !SpiHosts[target].includes(own))
                    P.push(`the chip ${target} has no "${own}" to wire: ${SpiHosts[target].join(', ')}`);
                const need = kind === 'spi' ? ['mosi', 'miso', 'sclk'] : ['d0', 'd1', 'd2', 'd3', 'sclk'];
                for (const s of need) if (!isInt(bus[s])) P.push(`the bus ${name} lacks its "${s}" pin`);
            } else if (kind === 'i2c') {
                for (const s of ['sda', 'scl']) if (!isInt(bus[s])) P.push(`the bus ${name} lacks its "${s}" pin`);
            } else if (kind === 'i2s') {
                if (!/^i2s\d+$/.test(own)) P.push(`the name of an i2s bus is its port: "i2s.i2s0", not "${own}"`);
                for (const s of ['mclk', 'bclk', 'ws', 'dout']) if (!isInt(bus[s])) P.push(`the bus ${name} lacks its "${s}" pin`);
                if (bus.din != null && !isInt(bus.din)) P.push(`the bus ${name} has a din that is not a pin`);
            } else if (kind === 'dsi') {
                for (const k of ['lanes', 'lane_mbps', 'phy_ldo_chan', 'phy_ldo_mv']) if (!isInt(bus[k])) P.push(`the bus ${name} lacks its "${k}"`);
            } else if (kind === 'p8') {
                for (const k of ['d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'wr', 'dc', 'hz']) if (!isInt(bus[k])) P.push(`the bus ${name} lacks its "${k}"`);
                if (bus.rd != null && !isInt(bus.rd)) P.push(`the bus ${name} has an rd that is not a pin`);
            } else {
                for (const [k, v] of Object.entries(bus || {}))
                    if (v !== null && typeof v !== 'number' && typeof v !== 'string') P.push(`the bus ${name} has a "${k}" that is neither a pin nor a parameter`);
            }
        }
    }
    const d = b.display;
    if (d) {
        const driver = d.driver;
        if (CharacterDrivers[driver]) {
            if (!CharacterDrivers[driver].includes(d.geometry))
                P.push(`the geometry ${d.geometry} is not one the driver ${driver} takes (${CharacterDrivers[driver].join(', ')})`);
            const t = d.bus || {};
            const [kind, width] = busParts(t.bus);
            if (kind === 'i2c') {
                if (!t.address) P.push('a character LCD on I2C names the backpack\'s address beside the bus');
                if (!module && !busOf(b, t.bus)) P.push(`the character LCD rides the board's bus "${t.bus}", which the board does not wire`);
            } else if (kind === 'gpio') {
                const pins = t.pins || {};
                const need = width === '4bit' ? ['rs', 'en', 'd4', 'd5', 'd6', 'd7'] : width === '8bit' ? ['rs', 'en', 'd0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7'] : null;
                if (!need) P.push('a character LCD on GPIOs is "gpio.4bit" or "gpio.8bit"');
                else for (const s of need) if (!isInt(pins[s])) P.push(`the character LCD on gpio.${width} lacks its "${s}" pin`);
            } else {
                P.push('a character LCD rides one of three transports: "i2c.<own>" (a PCF8574 backpack), "gpio.4bit", "gpio.8bit"');
            }
        } else if (PanelDrivers[driver]) {
            const busName = (d.bus || {}).bus;
            const kind = busParts(busName)[0];
            if (!PanelStrobes[kind]) {
                P.push('the display\'s bus is a name from buses: "spi.spi2", "qspi.spi2", "dsi.dsi0", "p8.i80"');
            } else {
                if (!busOf(b, busName)) P.push(`the display's bus "${busName}" is not among the board's buses`);
                for (const line of PanelStrobes[kind]) if (!isInt(d.bus[line])) P.push(`the display lacks its "${line}" line`);
                const p = d.panel || {};
                for (const k of ['width', 'height', 'mm_w', 'mm_h']) if (!isInt(p[k])) P.push(`the panel of the display lacks its ${k}`);
                if (['width', 'height', 'mm_w', 'mm_h'].every(k => isInt(p[k]))) {
                    if (p.width > p.height && p.mm_w < p.mm_h || p.width < p.height && p.mm_w > p.mm_h)
                        P.push('the panel\'s pixels and its millimetres lie different ways: both are the glass as the controller scans it');
                    const diff = Math.abs(p.width / p.height - p.mm_w / p.mm_h) / Math.max(p.width / p.height, p.mm_w / p.mm_h);
                    if (diff > 0.2) P.push(`the panel's pixels (${p.width}x${p.height}) and its millimetres (${p.mm_w}x${p.mm_h}) are not near one proportion`);
                }
                if (!PanelDrivers[driver].includes(d.depth_bits)) P.push(`depth_bits ${d.depth_bits} is not one the driver ${driver} takes (${PanelDrivers[driver].join(', ')})`);
                const o = d.original_orientation || {};
                if (!OrientX.includes(o.x) || !OrientY.includes(o.y)) P.push('the original_orientation of the display is not left-right/right-left x top-bottom/bottom-top');
            }
        } else {
            P.push(`panel driver not known: "${driver}"`);
        }
    }
    const t = b.touch;
    if (t) {
        if (!TouchKinds.includes(t.kind)) P.push(`touch of a kind not known: "${t.kind}"`);
        if (!(d && PanelDrivers[d.driver])) P.push('a touch panel lies on a frame buffer display: the board has none');
        if (!t.calibration) P.push('the touch has no calibration: measure the board (dgx_di_calibrate_measure) and put it in the data; "measured": false marks a placeholder');
        if (!isInt(t.x_max) || !isInt(t.y_max)) P.push('the touch lacks its x_max and y_max, the range of its coordinates');
        if (!t.bus || !busOf(b, t.bus)) P.push(`the touch's bus "${t.bus}" is not among the board's buses`);
        if (t.kind === 'esp_lcd_touch') {
            if (!(t.component && t.header)) P.push('a touch of the esp_lcd_touch kind names its component and its header');
            if (t.component && (t.component.split('/').length !== 2)) P.push(`the component is named with its namespace, "atanisoft/esp_lcd_touch_xpt2046", not "${t.component}"`);
            if (busParts(t.bus)[0] !== 'spi') P.push('a touch of the esp_lcd_touch kind rides a board\'s SPI bus: bus is its name, "spi.spi2"');
            for (const line of ['cs', 'irq']) if (!isInt(t[line])) P.push(`the touch lacks its "${line}" pin`);
        } else if (t.kind === 'gt911' || t.kind === 'gsl3680') {
            if (t.bus && busParts(t.bus)[0] !== 'i2c') P.push(`the ${t.kind} rides a board's I2C bus: bus is its name, "i2c.i2c0"`);
        }
        if (t.calibration && isInt(t.x_max) && (t.calibration.x_max !== t.x_max || t.calibration.y_max !== t.y_max))
            P.push('the calibration is for another panel: its x_max/y_max differ from the touch\'s own');
    }
    const s = b.sound;
    if (s) {
        if (s.kind === 'dac') {
            if (target !== 'esp32') P.push('the DAC kind of sound is the ESP32\'s own: no other chip here has one');
            if (![25, 26].includes(s.out)) P.push(`the DAC of an ESP32 is on GPIO 25 or 26, not ${s.out}`);
            if (s.pa != null && !isInt(s.pa)) P.push('the pa of the sound is a pin or null');
        } else if (s.kind === 'es8311') {
            if (busParts(s.bus)[0] !== 'i2c' || !busOf(b, s.bus)) P.push('the codec comes on a board\'s I2C bus: bus is its name, "i2c.<own>"');
            if (!busOf(b, s.i2s_bus)) P.push('the codec streams over a board\'s I2S bus: i2s_bus is its name, "i2s.i2s0"');
            if (!s.address) P.push('the codec needs its address on the I2C bus');
            if (!isInt(s.volume)) P.push('the codec needs its volume, 0..100');
        } else {
            P.push(`sound of a kind not known: "${s.kind}"`);
        }
        if (!isInt(s.sample_rate)) P.push('the sound lacks its sample_rate');
    }
    if (b.button && !isInt(b.button.pin)) P.push('the button lacks its pin');
    if (b.sd) {
        if (busParts(b.sd.bus)[0] !== 'spi' || !busOf(b, b.sd.bus)) P.push('the sd slot is a device on a board\'s SPI bus: bus is its name, "spi.spi2"');
        if (!isInt(b.sd.cs)) P.push('the sd slot lacks its cs pin');
    }
    return P;
}

/* what dgx_di_calibrate_measure prints: a C initializer of dgx_di_calibration_t
   (dgx_di_calibration_code). Parsed into the fields of the data; what the generator adds
   itself — version, size — is dropped */
function parseCalibration(text) {
    const toks = String(text).match(/[-+]?\d+|sizeof\s*\([^)]*\)|[{}=,.]|[A-Za-z_][A-Za-z0-9_]*/g) || [];
    let at = 0;
    const next = () => toks[at++];
    function value() {
        const t = next();
        if (t === undefined) throw new Error('the calibration ends mid-way');
        if (/^[-+]?\d+$/.test(t)) return parseInt(t, 10);
        if (t.indexOf('sizeof') === 0) return null; /* sizeof(dgx_di_calibration_t): the generator's own */
        if (t !== '{') throw new Error(`"${t}" where a number or a { } was meant`);
        const list = [];
        for (;;) {
            const v = value();
            if (v !== null) list.push(v);
            const sep = next();
            if (sep === '}') break;
            if (sep !== ',') throw new Error(`"${sep}" where a , or a } was meant`);
        }
        return list;
    }
    if (next() !== '{') throw new Error('the calibration is a { ... } initializer, as dgx_di_calibrate_measure prints it');
    const fields = {};
    for (;;) {
        let t = next();
        if (t === '}') break;
        if (t !== '.') throw new Error(`"${t}" where a .field was meant`);
        const name = next();
        if (next() !== '=') throw new Error(`no = after .${name}`);
        const v = value();
        if (name !== 'version' && name !== 'size') fields[name] = v;
        const sep = next();
        if (sep === '}') break;
        if (sep !== ',') throw new Error(`"${sep}" where a , or a } was meant`);
    }
    const ints = ['x_min', 'x_max', 'y_min', 'y_max', 'width', 'height', 'flags', 'knots_x', 'knots_y', 'rounds', 'down_ms', 'up_ms', 'blink_ms', 'gap_ms', 'off_tenths', 'worst_tenths', 'left_tenths', 'left_worst_tenths'];
    const cal = {};
    for (const k of ints) if (isInt(fields[k])) cal[k] = fields[k];
    if (Array.isArray(fields.affine) && fields.affine.length >= 6 && fields.affine.every(isInt)) cal.affine = fields.affine.slice(0, 6);
    for (const ax of ['x', 'y']) {
        const knots = (Array.isArray(fields[ax]) ? fields[ax] : []).filter(Array.isArray).filter(k => k.length >= 2).map(k => [k[0], k[1]]);
        if (knots.length) cal[ax] = knots;
    }
    if (!cal.knots_x && cal.x) cal.knots_x = cal.x.length;
    if (!cal.knots_y && cal.y) cal.knots_y = cal.y.length;
    if (!Object.keys(cal).length) throw new Error('no fields of dgx_di_calibration_t in it');
    /* the fields in the order of dgx_di_calibration_t: the file this makes sits beside the
       ones written by hand, one spelling of it */
    const order = ['x_min', 'x_max', 'y_min', 'y_max', 'width', 'height', 'flags', 'knots_x', 'knots_y', 'rounds', 'affine', 'x', 'y',
                   'down_ms', 'up_ms', 'blink_ms', 'gap_ms', 'off_tenths', 'worst_tenths', 'left_tenths', 'left_worst_tenths'];
    const ordered = {};
    for (const k of order) if (cal[k] !== undefined) ordered[k] = cal[k];
    return ordered;
}

/* the calibration of the data as C again, the way dgx_di_calibration_code prints it: what
   goes back into the textarea after a paste is applied, the one spelling of it */
function calibrationCode(cal) {
    if (!cal) return '';
    const knots = (a) => (a || []).map(p => `{${p[0]}, ${p[1]}}`).join(', ');
    return `{.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = ${cal.x_min}, .x_max = ${cal.x_max}, .y_min = ${cal.y_min}, .y_max = ${cal.y_max}, .width = ${cal.width}, .height = ${cal.height}, `
        + `.flags = ${cal.flags}, .knots_x = ${cal.knots_x}, .knots_y = ${cal.knots_y}, .rounds = ${cal.rounds}, .affine = {${(cal.affine || []).join(', ')}}, `
        + `.x = {${knots(cal.x)}}, .y = {${knots(cal.y)}}, `
        + `.down_ms = ${cal.down_ms}, .up_ms = ${cal.up_ms}, .blink_ms = ${cal.blink_ms}, .gap_ms = ${cal.gap_ms}, `
        + `.off_tenths = ${cal.off_tenths}, .worst_tenths = ${cal.worst_tenths}, .left_tenths = ${cal.left_tenths}, .left_worst_tenths = ${cal.left_worst_tenths}}`;
}

function emptyBoard() {
    return {
        format: BoardFormat.name,
        format_version: BoardFormat.version,
        name: '',
        title: '',
        description: '',
        mcu: { target: 'esp32', flash_mb: 4 },
        buses: {},
        display: null,
        touch: null,
        sound: null,
        button: null,
        sd: null
    };
}

/* the JSON of the data keeps its measured floats as they were written (5.0 stays 5.0, not
   5 — JavaScript's numbers know no difference, the files of the repository do): a float is
   marked at load (a string the user cannot type into a field) and unmarked at save. What is
   edited becomes a plain number and prints as one */
function markFloats(text) {
    return text.replace(/(?:"(?:[^"\\]|\\.)*")|(-?\d+\.\d+(?:[eE][-+]?\d+)?|-?\d+[eE][-+]?\d+)/g, (m, num) => (num ? '"\\u0000f:' + num + '"' : m));
}

function unmarkFloats(text) {
    return text.replace(/"(?:\\\\u0000f|\\u0000f):([^"]*)"/g, '$1').replace(/"\\f:([^"]*)"/g, '$1');
}

/* what the editor saves: the board as it is, the parts it has not left out — the files carry
   no empty keys, and the generator asks by get() anyway */
function boardForSave(board) {
    const out = JSON.parse(JSON.stringify(board));
    for (const k of ['display', 'touch', 'sound', 'button', 'sd']) if (out[k] == null) delete out[k];
    if (out.buses && !Object.keys(out.buses).length) delete out.buses;
    return out;
}

const useBoardStore = Pinia.defineStore('board', {
    state() {
        return { board: emptyBoard(), uploadError: '', savedName: '', calibrationPaste: '', calibrationError: '', calibrationNote: '' };
    },
    getters: {
        problems(state) {
            return boardProblems(state.board);
        },
        busGroups(state) {
            const groups = [];
            for (const [kind, named] of Object.entries(state.board.buses || {})) {
                const buses = Object.entries(named || {}).map(([own, bus]) => ({ own, bus, name: `${kind}.${own}` }));
                if (buses.length) groups.push({ kind, known: !!BusKinds[kind], title: BusKinds[kind] ? BusKinds[kind].title : kind, buses });
            }
            return groups;
        },
        busNamesOf(state) {
            return (kinds) => {
                const names = [];
                for (const [kind, named] of Object.entries(state.board.buses || {}))
                    if (!kinds || kinds.includes(kind)) for (const own of Object.keys(named || {})) names.push(`${kind}.${own}`);
                return names;
            };
        }
    },
    actions: {
        newBoard() {
            this.board = emptyBoard();
            this.savedName = '';
            this.uploadError = '';
            this.calibrationPaste = this.calibrationError = this.calibrationNote = '';
        },
        load(file) {
            const reader = new FileReader();
            reader.onload = () => {
                try {
                    const data = JSON.parse(markFloats(reader.result));
                    if (data.format !== BoardFormat.name) throw new Error(`not a board of ${BoardFormat.name}`);
                    if (data.format_version !== BoardFormat.version) throw new Error(`format_version ${data.format_version} is not ${BoardFormat.version}`);
                    this.board = data;
                    this.savedName = file.name;
                    this.uploadError = '';
                    this.calibrationPaste = calibrationCode(this.board.touch && this.board.touch.calibration);
                    this.calibrationError = this.calibrationNote = '';
                } catch (err) {
                    this.uploadError = String(err.message || err);
                }
            };
            reader.readAsText(file);
        },
        save() {
            if (this.problems.length) {
                this.uploadError = 'the board has problems: fix them before saving';
                return;
            }
            const text = unmarkFloats(JSON.stringify(boardForSave(this.board), null, 4) + '\n');
            const blob = new Blob([text], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'board.json';
            a.click();
            URL.revokeObjectURL(a.href);
        },
        applyCalibration() {
            if (!this.board.touch) {
                this.calibrationError = 'the board has no touch panel to calibrate';
                return;
            }
            try {
                const cal = parseCalibration(this.calibrationPaste);
                /* a paste is a measurement: the placeholder mark goes */
                this.board.touch.calibration = Object.assign({ measured: true }, cal);
                this.calibrationError = '';
                this.calibrationNote = `for a ${cal.width} x ${cal.height} display, off ${(cal.off_tenths / 10).toFixed(1)} px without it, ${(cal.left_tenths / 10).toFixed(1)} px with it`;
                this.calibrationPaste = calibrationCode(cal);
            } catch (err) {
                this.calibrationNote = '';
                this.calibrationError = String(err.message || err);
            }
        },
        addBus(kind, own) {
            if (!kind || !own) return;
            if (!this.board.buses) this.board.buses = {};
            if (!this.board.buses[kind]) this.board.buses[kind] = {};
            if (this.board.buses[kind][own] !== undefined) return;
            const bus = {};
            const spec = BusKinds[kind];
            if (spec) for (const [f, mode] of Object.entries(spec.fields)) if (mode !== 'opt') bus[f] = null;
            this.board.buses[kind][own] = bus;
        },
        removeBus(kind, own) {
            if (!this.board.buses || !this.board.buses[kind]) return;
            delete this.board.buses[kind][own];
            if (!Object.keys(this.board.buses[kind]).length) delete this.board.buses[kind];
        }
    }
});
