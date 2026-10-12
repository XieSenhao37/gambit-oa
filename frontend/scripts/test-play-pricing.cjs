const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/pages/PlayPricing/pricingForm.ts');
const moduleUnderTest = new Module(filename, module);
moduleUnderTest._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, filename);
const {fromPrice,toPrice,priceTotal,fromSchedule,toSchedule,regularDraft} = moduleUnderTest.exports;
const hours=[1,2,3,4,6,10];
const draft=toSchedule(regularDraft);
assert.deepEqual(hours.map(h=>priceTotal(draft.Common,h)),[2800,5600,7800,7800,7800,7800]);
assert.deepEqual(hours.map(h=>priceTotal(draft.Holiday,h)),[2800,5600,7800,8800,10800,14800]);
assert.deepEqual(draft.HolidayWeekdays,[0,5,6]);
for(const price of [
 {Price:2800,MaxTotal:7800,MaxHour:3,AdditionPrice:1000},
 {Price:2800,MaxTotal:7800,MaxHour:3,AdditionPrice:0},
 {Price:2000,MaxTotal:6800,MaxHour:3,AdditionPrice:1000},
 {Price:2000,MaxTotal:5800,MaxHour:3,AdditionPrice:1000,BundlePricing:true},
 {Price:2000,MaxTotal:5800,MaxHour:3,AdditionPrice:0,BundlePricing:true},
]) {
 const converted=toPrice(fromPrice(price));
 assert.deepEqual(hours.map(h=>priceTotal(converted,h)),hours.map(h=>priceTotal(price,h)),'loading/saving must preserve charges');
}
assert.equal(fromPrice({Price:2000,MaxTotal:6800,MaxHour:3,AdditionPrice:1000}).Mode,'legacy');
assert.equal(toPrice({...regularDraft.Holiday,Mode:'daily_cap'}).AdditionPrice,0,'hidden continuation cannot affect an all-day cap');
const custom={...draft,HolidayWeekdays:[],DateTypes:{'2026-10-01':'common'},SpecialMap:{'2026-11-01':draft.Holiday},TimeRules:[{Name:'晚间',DayType:'any',StartDate:'',EndDate:'',StartTime:'22:00',EndTime:'02:00',Price:draft.Holiday}]};
assert.deepEqual(toSchedule(fromSchedule(custom)),custom,'advanced settings and an empty weekday selection must round-trip');
assert.throws(()=>toSchedule({...regularDraft,DateOverrides:[{Date:'2026-10-01',DayType:'common'},{Date:'2026-10-01',DayType:'holiday'}]}));
console.log('Pricing form: regular prices, mode changes, legacy preservation and advanced settings passed');
