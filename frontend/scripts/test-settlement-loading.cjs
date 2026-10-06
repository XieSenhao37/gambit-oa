// Exercise the page's effects with isolated hook state and controlled requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const React = {};
let hooks = [], cursor = 0, effects = [], tree;
const react = { ...React,
  useState(init) { const i = cursor++; if (!(i in hooks)) hooks[i] = typeof init === 'function' ? init() : init; return [hooks[i], v => { hooks[i] = typeof v === 'function' ? v(hooks[i]) : v; }]; },
  useRef(init) { const i = cursor++; return hooks[i] ||= { current: init }; },
  useEffect(fn, deps) { const i = cursor++, old = hooks[i]; if (!old || deps.some((d, j) => d !== old.deps[j])) { old?.cleanup?.(); const entry = { deps }; hooks[i] = entry; effects.push(() => { entry.cleanup = fn(); }); } },
};
const ui = new Proxy({}, { get(target, name) {
  if (!target[name]) { const f = () => null; f.displayName = name;
    if (name === 'Form') f.useForm = () => [{ resetFields() {}, setFieldsValue() {} }];
    target[name] = f;
  } return target[name];
}});
let calls = [];
const services = { settlementGet(path) { return new Promise((resolve, reject) => calls.push({ path, resolve, reject })); } };
const storage = new Map();
const sandbox = { exports: {}, Date, setTimeout,
  sessionStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v) },
  require(name) {
    if (name === 'react') return react;
    if (name === 'react/jsx-runtime') return { jsx: (type, props, key) => ({ type, props, key }), jsxs: (type, props, key) => ({ type, props, key }) };
    if (name === 'dayjs') return require(name);
    if (name === 'antd') return ui;
    if (name === './MetricHelp') return { metricLabel: label => label };
    if (name === '@umijs/max') return { useModel: () => ({ initialState: { auth: { Headquarters: true, UserId: 1, Stores: [] } } }) };
    if (name === '@/services/settlement') return services;
    if (name === '@ant-design/pro-components') return { PageContainer: ui.PageContainer };
    return { __esModule: true, default: ui.Child, ReceiptProof: ui.Child };
  },
};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/pages/Settlement/index.tsx', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText, sandbox);
function render() { cursor = 0; effects = []; tree = sandbox.exports.default(); effects.forEach(fn => fn()); }
function find(type, node) { if (!node || typeof node !== 'object') return; if (node.type === type) return node; for (const child of [].concat(node.props?.children || [])) { const result = find(type, child); if (result) return result; } }
async function finish(call, data) { call.resolve({ Data: data }); for (let i = 0; i < 6; i++) await Promise.resolve(); render(); }
(async () => {
  render();
  await finish(calls[0], { Enabled: true, Totals: [] });
  find(ui.Tabs, tree).props.onChange('cards'); render();
  assert.ok(find(ui.Tabs, tree), 'tab strip stays mounted while rows load');
  assert.equal(calls.filter(c => c.path === 'overview').length, 1);
  await finish(calls.at(-1), { Items: [], Total: 0 });
  find(ui.Tabs, tree).props.onChange('cash'); render();
  calls.at(-1).reject(new Error('mock failure'));
  for (let i = 0; i < 6; i++) await Promise.resolve(); render();
  assert.ok(find(ui.Tabs, tree), 'detail failure does not remove the summary or tabs');
  const count = calls.length;
  find(ui.Tabs, tree).props.onChange('cards'); render();
  assert.equal(calls.length, count, 'visited detail is served from cache');
  find(ui.Child, tree).props.refresh(); render();
  assert.equal(calls.length, count + 2, 'refresh invalidates both summary and detail cache');
  console.log('Settlement loading: summary retained, independent errors, tab cache passed');
})().catch(e => { console.error(e); process.exitCode = 1; });
