const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const pages = require('../src/config/pages.json');
const storage = new Map([['token', 'isolated']]);
const sessionStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) };
let hooks = [], cursor = 0, effects = [], pathname = '/workbench';
const auth = { UserId: 1, Stores: [
  { Id: 1, Name: 'A', Pages: ['workbench', 'games'] },
  { Id: 2, Name: 'B', Pages: ['workbench', 'games', 'dashboard', 'game-service-orders'] },
] };
const react = {
  useState(initial) { const i = cursor++; if (!(i in hooks)) hooks[i] = initial; return [hooks[i], value => { hooks[i] = value; }]; },
  useEffect(fn, deps) { const i = cursor++, old = hooks[i]; if (!old || deps.some((d, j) => d !== old.deps[j])) { old?.cleanup?.(); const entry = hooks[i] = { deps }; effects.push(() => { entry.cleanup = fn(); }); } },
  useSyncExternalStore: (_, snapshot) => snapshot(),
};
const Select = 'Select', Outlet = 'Outlet';
const history = [];
const imports = {
  react,
  'react/jsx-runtime': { jsx: (type, props, key) => ({type, props, key}), jsxs: (type, props, key) => ({type, props, key}) },
  '@umijs/max': { useModel: () => ({ initialState: {auth} }), useLocation: () => ({pathname}), Outlet, Navigate: 'Navigate', history: {push: url => history.push(url)} },
  antd: { Select, Result: 'Result', Tooltip: 'Tooltip' },
  '@/config/pages.json': pages,
  '@/components/FunctionSearch': {default: 'Search', __esModule: true},
  '@/components/GameOrderTodos': {default: 'Todos', __esModule: true},
  '@/services/auth': {getMe: async () => ({Data: auth})},
};
function load(file) {
  const sandbox = {exports: {}, sessionStorage, localStorage: sessionStorage,
    setInterval: () => 1, clearInterval() {},
    window: {addEventListener() {}, removeEventListener() {}},
    require: id => { assert.ok(imports[id], `unexpected dependency ${id}`); return imports[id]; },
  };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true},
  }).outputText, sandbox);
  return sandbox.exports;
}
const stores = imports['@/utils/pageStores'] = load('utils/pageStores.ts');
imports['./pageStores'] = stores;
imports['@/hooks/usePreferredStore'] = load('hooks/usePreferredStore.ts');
const switcher = imports['@/components/StoreSwitcher'] = load('components/StoreSwitcher.tsx');
const wrapper = load('wrappers/auth.tsx');
function render() {
  cursor = 0; effects = [];
  const tree = wrapper.default();
  const outlet = find(Outlet, tree);
  if (outlet) assert.equal(stores.getCurrentStoreId(), Number(outlet.key.split(':').at(-1)), 'first content request sees the selected store');
  effects.forEach(fn => fn());
  return tree;
}
function find(type, node) {
  if (!node || typeof node !== 'object') return;
  if (node.type === type) return node;
  for (const child of [].concat(node.props?.children || [])) { const found = find(type, child); if (found) return found; }
}
render();
let tree = render();
assert.ok(find(Outlet, tree));
find(Select, switcher.default({})).props.onChange(2);
tree = render();
assert.ok(find('Search', tree), 'context bar stays present while content switches');
assert.equal(find(Outlet, tree), undefined, 'old-store content is removed before setting the request context');
tree = render();
assert.equal(stores.getCurrentStoreId(), 2);
assert.ok(find(Outlet, tree));
assert.equal(find(Select, switcher.default({})).props.value, 2);
pathname = '/games'; render(); tree = render();
assert.equal(find(Select, switcher.default({})).props.value, 2, 'next module inherits the store');
// A module without access to the preferred store falls back and synchronizes globally.
auth.Stores[1].Pages = ['games', 'dashboard', 'game-service-orders'];
pathname = '/workbench'; render(); tree = render();
assert.equal(stores.getCurrentStoreId(), 1);
assert.equal(stores.getPreferredStore(1), 1);
pathname = '/games'; render(); tree = render();
assert.equal(find(Select, switcher.default({})).props.value, 1);
const visit = load('utils/visitGameTodo.ts').visitGameTodo;
visit(auth, {ID: 8, StoreID: 2});
assert.equal(stores.getPreferredStore(1), 2);
assert.deepEqual(history, ['/game-service-orders?orderId=8']);
visit(auth, {ID: 9, StoreID: 99});
assert.equal(history.length, 1, 'unauthorized todo cannot change context or navigate');
console.log('Store switching: no document reload, shared modules, request ordering, permission fallback and todo navigation passed');
