const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const resolverRequire = createRequire(require.resolve('@rollup/plugin-node-resolve'));
const merge = resolverRequire('deepmerge');

test('patched merge preserves data without invoking prototype setters', () => {
  const poisoned = JSON.parse('{"__proto__":{"injected":true},"nested":{"__proto__":{"injected":true}}}');
  for (const result of [merge(poisoned, {}), merge({}, poisoned), merge({ items: [poisoned] }, {})]) {
    assert.equal(result.injected, undefined);
    assert.equal(Object.getPrototypeOf(result), Object.prototype);
    if (result.nested) assert.equal(result.nested.injected, undefined);
    if (result.items) assert.equal(result.items[0].injected, undefined);
  }
  assert.equal({}.injected, undefined);
  assert.deepEqual(merge({ items: [1], nested: { a: 1 } }, { items: [2], nested: { b: 2 } }),
    { items: [1, 2], nested: { a: 1, b: 2 } });
  const input = { extensions: ['.js'], modulesOnly: false };
  const copy = merge({}, input);
  copy.extensions.push('.ts');
  assert.deepEqual(input.extensions, ['.js']);
});

test('Workbox template dependency keeps the CommonJS render contract', () => {
  const omtRequire = createRequire(require.resolve('@trickfilm400/rollup-plugin-off-main-thread'));
  assert.equal(omtRequire('ejs').render('<%= value %>', { value: '<safe>' }), '&lt;safe&gt;');
});
