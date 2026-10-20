const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ts = require('typescript');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/services/requestKey.ts'), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText;
// HTTP browsers may provide getRandomValues but omit randomUUID entirely.
for (const api of [undefined, {getRandomValues: v => crypto.webcrypto.getRandomValues(v)}, {randomUUID: () => crypto.randomUUID()}]) {
  const context = {exports: {}, crypto: api};
  vm.runInNewContext(js, context);
  const keys = Array.from({length:1000}, () => context.exports.newRequestKey());
  assert.equal(new Set(keys).size, 1000);
  assert.ok(keys.every(k => k.length >= 8 && k.length <= 64 && k.trim() === k));
}
console.log('Request keys work on HTTP, HTTPS and legacy browser contexts');
