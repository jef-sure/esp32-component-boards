// JSON Schema for the editor: the keywords format.schema.json uses, read without eval so a webview's
// policy allows it, and which schemas are in force at a place, for the card of a node.
// tools/check_format.py compares it with jsonschema of Python.
'use strict';

function schemaReader(root) {
    const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
    const sorted = (v) => {
        if (Array.isArray(v)) return v.map(sorted);
        if (isObject(v)) return Object.keys(v).sort().reduce((o, k) => ((o[k] = sorted(v[k])), o), {});
        return v;
    };
    const same = (a, b) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
    const TYPES = {
        object: isObject,
        array: Array.isArray,
        string: (v) => typeof v === 'string',
        number: (v) => typeof v === 'number',
        integer: (v) => Number.isInteger(v),
        boolean: (v) => typeof v === 'boolean',
        null: (v) => v === null,
    };
    const patterns = new Map();
    function matches(pattern, text) {
        if (!patterns.has(pattern)) patterns.set(pattern, new RegExp(pattern));
        return patterns.get(pattern).test(text);
    }
    function target(ref) {
        return ref.slice(2).split('/').reduce((node, part) => node[part.replace(/~1/g, '/').replace(/~0/g, '~')], root);
    }

    function valid(schema, value) {
        return errors(schema, value).length === 0;
    }

    // The keys of an object some schema in force has looked at, for unevaluatedProperties.
    function evaluated(schema, value, keys) {
        if (!isObject(schema)) return;
        if (schema.$ref) evaluated(target(schema.$ref), value, keys);
        for (const key of Object.keys(value)) {
            const named = schema.properties && Object.hasOwn(schema.properties, key);
            if (named || Object.keys(schema.patternProperties || {}).some((pattern) => matches(pattern, key)) || 'additionalProperties' in schema) keys.add(key);
        }
        for (const part of schema.allOf || []) evaluated(part, value, keys);
        for (const part of [...(schema.anyOf || []), ...(schema.oneOf || [])]) if (valid(part, value)) evaluated(part, value, keys);
        if ('if' in schema) {
            const taken = valid(schema.if, value);
            if (taken) evaluated(schema.if, value, keys);
            evaluated(taken ? schema.then : schema.else, value, keys);
        }
    }

    function objectErrors(schema, value, path, wrong, deeper) {
        const size = Object.keys(value).length;
        for (const key of schema.required || []) if (!Object.hasOwn(value, key)) wrong(`${key} is required`);
        if ('minProperties' in schema && size < schema.minProperties) wrong(`at least ${schema.minProperties} fields`);
        if ('maxProperties' in schema && size > schema.maxProperties) wrong(`at most ${schema.maxProperties} fields`);
        for (const [key, needed] of Object.entries(schema.dependentRequired || {})) {
            if (Object.hasOwn(value, key)) for (const other of needed) if (!Object.hasOwn(value, other)) wrong(`${key} needs ${other}`);
        }
        for (const key of Object.keys(value)) {
            let taken = false;
            if (schema.properties && Object.hasOwn(schema.properties, key)) {
                taken = true;
                deeper(schema.properties[key], value[key], key);
            }
            for (const [pattern, part] of Object.entries(schema.patternProperties || {})) {
                if (matches(pattern, key)) {
                    taken = true;
                    deeper(part, value[key], key);
                }
            }
            if (!taken && 'additionalProperties' in schema) deeper(schema.additionalProperties, value[key], key);
            if ('propertyNames' in schema) deeper(schema.propertyNames, key, key);
        }
        if ('unevaluatedProperties' in schema) {
            const keys = new Set();
            evaluated({ ...schema, unevaluatedProperties: undefined }, value, keys);
            for (const key of Object.keys(value)) if (!keys.has(key)) deeper(schema.unevaluatedProperties, value[key], key);
        }
    }

    function arrayErrors(schema, value, wrong, deeper) {
        if ('minItems' in schema && value.length < schema.minItems) wrong(`at least ${schema.minItems} items`);
        if ('maxItems' in schema && value.length > schema.maxItems) wrong(`at most ${schema.maxItems} items`);
        if (schema.uniqueItems && value.some((item, i) => value.slice(i + 1).some((other) => same(item, other)))) wrong('the items repeat');
        if ('contains' in schema && !value.some((item) => valid(schema.contains, item))) wrong('no item of the kind needed');
        if ('items' in schema) value.forEach((item, i) => deeper(schema.items, item, i));
    }

    // What is wrong with a value: {path, message}, path as a list of keys.
    function errors(schema, value, path = []) {
        if (schema === true) return [];
        if (schema === false) return [{ path, message: 'not allowed here' }];
        const found = [];
        const wrong = (message) => found.push({ path, message });
        const deeper = (part, item, key) => found.push(...errors(part, item, [...path, key]));
        if (schema.$ref) found.push(...errors(target(schema.$ref), value, path));
        if ('type' in schema && ![].concat(schema.type).some((type) => TYPES[type](value))) wrong(`it should be ${[].concat(schema.type).join(' or ')}`);
        if ('enum' in schema && !schema.enum.some((item) => same(item, value))) wrong(`it should be one of ${schema.enum.join(', ')}`);
        if ('const' in schema && !same(schema.const, value)) wrong(`it should be ${schema.const}`);
        if (typeof value === 'number') {
            if ('minimum' in schema && value < schema.minimum) wrong(`the least is ${schema.minimum}`);
            if ('maximum' in schema && value > schema.maximum) wrong(`the most is ${schema.maximum}`);
            if ('exclusiveMinimum' in schema && value <= schema.exclusiveMinimum) wrong(`it should be above ${schema.exclusiveMinimum}`);
        }
        if (typeof value === 'string') {
            if ('minLength' in schema && [...value].length < schema.minLength) wrong('it is too short');
            if ('pattern' in schema && !matches(schema.pattern, value)) wrong(`it should match ${schema.pattern}`);
        }
        if (isObject(value)) objectErrors(schema, value, path, wrong, deeper);
        if (Array.isArray(value)) arrayErrors(schema, value, wrong, deeper);
        for (const part of schema.allOf || []) found.push(...errors(part, value, path));
        if (schema.anyOf && !schema.anyOf.some((part) => valid(part, value))) wrong('it fits none of the forms allowed');
        if (schema.oneOf && schema.oneOf.filter((part) => valid(part, value)).length !== 1) wrong('it should fit exactly one of the forms allowed');
        if ('not' in schema && valid(schema.not, value)) wrong('this form is not allowed');
        if ('if' in schema) {
            const branch = valid(schema.if, value) ? schema.then : schema.else;
            if (branch !== undefined) found.push(...errors(branch, value, path));
        }
        return found;
    }

    // The schema and every schema it brings in for this value; a value not there yet brings in only what always holds.
    function inForce(schemas, value) {
        const out = [];
        const add = (schema) => {
            if (!isObject(schema) || out.includes(schema)) return;
            out.push(schema);
            if (schema.$ref) add(target(schema.$ref));
            (schema.allOf || []).forEach(add);
            if (value === undefined) return;
            for (const part of [...(schema.anyOf || []), ...(schema.oneOf || [])]) if (valid(part, value)) add(part);
            if ('if' in schema) add(valid(schema.if, value) ? schema.then : schema.else);
        };
        schemas.forEach(add);
        return out;
    }

    // The schemas of a key under schemas in force.
    function below(schemas, key) {
        const out = [];
        for (const schema of schemas) {
            if (typeof key === 'number') {
                if (schema.items !== undefined) out.push(schema.items);
                continue;
            }
            const named = schema.properties && Object.hasOwn(schema.properties, key) ? [schema.properties[key]] : [];
            const patterned = Object.entries(schema.patternProperties || {}).filter(([pattern]) => matches(pattern, key)).map(([, part]) => part);
            out.push(...named, ...patterned);
            if (!named.length && !patterned.length && schema.additionalProperties !== undefined) out.push(schema.additionalProperties);
        }
        return out;
    }

    // The schemas in force at a path of a document.
    function at(doc, path) {
        let schemas = inForce(root.$defs?.resolved ? [root, { $ref: '#/$defs/resolved' }] : [root], doc);
        let value = doc;
        for (const key of path) {
            value = value === undefined || value === null ? undefined : value[key];
            schemas = inForce(below(schemas, key), value);
        }
        return schemas;
    }

    // The fields schemas in force name, each with what they say of it: {name: {schemas, description, required}}.
    function fields(schemas) {
        const out = {};
        for (const schema of schemas) {
            for (const [name, part] of Object.entries(schema.properties || {})) {
                out[name] = out[name] || { schemas: [], required: false };
                out[name].schemas.push(part);
            }
        }
        for (const schema of schemas) for (const name of schema.required || []) if (out[name]) out[name].required = true;
        return out;
    }

    // What a value here should look like: {types, values, description}, from schemas in force.
    function shape(schemas) {
        const types = new Set();
        let values = null;
        let description = '';
        for (const schema of schemas) {
            [].concat(schema.type || []).forEach((type) => types.add(type));
            if (schema.enum && !values) values = schema.enum;
            if ('const' in schema && !values) values = [schema.const];
            if (schema.description && !description) description = schema.description;
        }
        return { types: [...types], values, description };
    }

    return { errors, valid, inForce, below, at, fields, shape };
}

if (typeof module !== 'undefined') module.exports = { schemaReader };
