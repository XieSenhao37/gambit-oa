const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ts = require('typescript');
const source = fs.readFileSync(require.resolve('../src/utils/requestKey.ts'), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
function load(crypto) {
  const context = { exports: {}, crypto, Uint8Array };
  vm.runInNewContext(js, context);
  return context.exports.createRequestKey;
}
const format = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
assert.match(load(webcrypto)(), format);
// Reproduce a non-secure browser context: getRandomValues exists, randomUUID does not.
const fallback = load({ getRandomValues: array => webcrypto.getRandomValues(array) });
const keys = new Set();
for (let i = 0; i < 5000; i++) { const key = fallback(); assert.match(key, format); keys.add(key); }
assert.equal(keys.size, 5000);
assert.throws(load(undefined), /浏览器/);
console.log('Request keys: native UUID, HTTP fallback, format, uniqueness and missing-crypto handling passed.');
