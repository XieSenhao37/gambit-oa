const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync('src/components/AdaptiveTable/columns.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const context = { exports: {} };
vm.runInNewContext(code, context);
const { fitColumns, fitScrollWidth } = context.exports;

test('退款等宽表不会挤压未声明宽度的订单信息，且不修改调用方列', () => {
  const source = [{ title: '申请ID', width: 90 }, { title: '订单信息' }, { title: '用户', width: 180 }, { title: '操作', width: 184 }];
  const result = fitColumns(source);
  assert.ok(result.columns[1].width >= 240);
  assert.equal(source[1].width, undefined);
  const scroll = fitScrollWidth(result.width, 300, true, true);
  assert.ok(scroll >= result.columns.reduce((sum, column) => sum + column.width, 0) + 112);
});
test('仅搜索字段与隐藏列不占用表格宽度，分组按可见子列计算', () => {
  const result = fitColumns([{ title: '查询', hideInTable: true, width: 1000 }, { title: '隐藏', hidden: true, width: 1000 }, { title: '组', children: [{ title: 'A', width: 100 }, { title: 'B', width: 200 }] }]);
  assert.equal(result.width, 300);
});
test('保留更大的滚动宽度和像素列宽，长表头有足够空间', () => {
  const result = fitColumns([{ title: '活动完整报名人数', width: 50 }, { title: 'B', width: '280px' }]);
  assert.ok(result.columns[0].width > 50);
  assert.equal(result.columns[1].width, 280);
  assert.equal(fitScrollWidth(result.width, 1600, false, false), 1600);
});
