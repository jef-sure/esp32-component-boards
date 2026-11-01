// The pins of a resolved board, as tools/boards_gen.py finds them: who owns each GPIO and what is wrong.
// tools/check_format.py compares the two.
'use strict';

const PIN_NOT_LINES = new Set(['hz', 'lanes', 'lane_mbps', 'phy_ldo_chan', 'phy_ldo_mv', 'baud', 'data']); // NOT_LINES of tools/resolve.py
const PIN_INPUT_LINES = new Set(['in', 'int', 'irq', 'te', 'busy']); // lines of a device that only come in

function pinsOf(board) {
    const pins = [];
    const add = (pin, owner, direction) => pins.push({ pin, owner, direction });
    for (const [kind, named] of Object.entries(board.buses || {})) {
        for (const [own, bus] of Object.entries(named || {})) {
            for (const key of Object.keys(bus || {}).sort()) {
                if (PIN_NOT_LINES.has(key) || !Number.isInteger(bus[key]?.gpio)) continue;
                add(bus[key].gpio, `${kind}.${own}.${key}`, key === 'miso' || key === 'din' ? 'in' : 'bus');
            }
        }
    }
    for (const step of board.power || []) if (step.line?.gpio !== undefined) add(step.line.gpio, `power.${step.name ?? 'strobe'}`, 'out');
    for (const [name, device] of Object.entries(board.devices || {})) {
        for (const line of Object.keys(device.pins || {}).sort()) {
            const value = device.pins[line];
            if (value?.gpio !== undefined) add(value.gpio, `${name}.${line}`, PIN_INPUT_LINES.has(line) ? 'in' : 'out');
        }
        const pin = device.config?.divider?.switch?.gpio;
        if (pin !== undefined) add(pin, `${name}.divider`, 'out');
        for (const connection of Object.values(device.on || {})) if (connection.cs?.gpio !== undefined) add(connection.cs.gpio, `${name}.cs`, 'out');
    }
    return pins;
}

function sharedPins(board) {
    const shared = new Map();
    for (const group of Object.values(board.shared_pins || {})) if (group.line?.gpio !== undefined) shared.set(group.line.gpio, group);
    return shared;
}

// Every GPIO of the chip: what it can do, who has it, where it comes out and when it is free.
function pinMap(board) {
    const gpio = board.mcu.facts.gpio;
    const shared = sharedPins(board);
    const owners = new Map();
    for (const { pin, owner } of pinsOf(board)) owners.set(pin, [...(owners.get(pin) || []), owner]);
    const outside = new Map();
    for (const [name, connector] of Object.entries(board.connectors || {})) {
        for (const pin of connector.pins || []) if (pin?.gpio !== undefined) outside.set(pin.gpio, [...(outside.get(pin.gpio) || []), name]);
    }
    const out = {};
    for (const pin of gpio.valid) {
        const entry = {
            owners: owners.get(pin) || [],
            connectors: outside.get(pin) || [],
            strapping: (gpio.strapping || []).includes(pin),
            input_only: gpio.input_only.includes(pin),
            ...(gpio.pins || {})[pin],
        };
        const when = shared.get(pin)?.only_while;
        if (when) entry.free_while = `${when.device}.${when.control} is ${when.value}`;
        entry.state = !entry.owners.length ? 'free' : shared.has(pin) ? 'shared' : 'taken';
        out[pin] = entry;
    }
    return out;
}

// Two owners of one pin, an output on an input-only GPIO, a GPIO the chip has not.
function pinProblems(board) {
    const gpio = board.mcu?.facts?.gpio;
    if (!gpio) return [];
    const problems = [];
    const shared = sharedPins(board);
    const owners = new Map();
    for (const { pin, owner, direction } of pinsOf(board)) {
        if (!gpio.valid.includes(pin)) problems.push(`GPIO ${pin} (${owner}) is no GPIO of an ${board.mcu.target}`);
        if (direction !== 'in' && gpio.input_only.includes(pin)) problems.push(`GPIO ${pin} (${owner}) is input only on an ${board.mcu.target}, and ${owner} drives it`);
        owners.set(pin, [...(owners.get(pin) || []), owner]);
    }
    for (const pin of [...owners.keys()].sort((a, b) => a - b)) {
        if (!shared.has(pin) && owners.get(pin).length > 1) problems.push(`GPIO ${pin} has two owners: ${owners.get(pin).join(', ')}`);
    }
    return problems;
}

if (typeof module !== 'undefined') module.exports = { pinsOf, pinMap, pinProblems };
