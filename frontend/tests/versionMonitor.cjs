const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const ts = require('typescript');
const vm = require('node:vm');
const {writeVersion} = require('../scripts/write-version.cjs');
const oldVersion = 'a'.repeat(32), nextVersion = 'b'.repeat(32), thirdVersion = 'c'.repeat(32);
const output = ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/services/versionMonitor.ts'),'utf8'), {
  compilerOptions: {module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020},
}).outputText;
function setup() {
  let now = 0, calls = 0, response = {version:oldVersion}, failure = false, held;
  const events = [];
  const intervals = new Map(), timeouts = new Map();
  const window = new EventTarget();
  const document = new EventTarget(); document.visibilityState = 'visible';
  Object.assign(window, {
    fetch: async (url,options) => {
      calls++; assert.equal(url,'/version.json'); assert.equal(options.cache,'no-store');
      assert.equal(options.credentials,'omit'); assert.ok(options.signal);
      if (failure) throw Error('offline');
      if (held) return held;
      return {ok:true,json:async()=>response};
    },
    setInterval: (fn,ms)=>{ assert.equal(ms,60000); const id=Symbol(); intervals.set(id,fn); return id; },
    clearInterval:id=>intervals.delete(id),
    setTimeout: (fn,ms)=>{ assert.equal(ms,10000); const id=Symbol(); timeouts.set(id,fn); return id; },
    clearTimeout:id=>timeouts.delete(id),
  });
  const context = {exports:{},window,document,AbortController,Date:{now:()=>now}};
  vm.runInNewContext(output,context);
  const flush = ()=>new Promise(resolve=>setImmediate(resolve));
  return {
    api:context.exports,events,window,document,intervals,timeouts,flush,
    stop:undefined,
    start(version=oldVersion){this.stop=this.api.startVersionMonitor(version,v=>events.push(v));},
    tick(){ now+=60000; for(const fn of intervals.values()) fn(); },
    wake(event='focus'){now+=2000;(event==='visibilitychange'?document:window).dispatchEvent(new Event(event));},
    respond:value=>{response=value;},fail:value=>{failure=value;},hold:value=>{held=value;},calls:()=>calls,
  };
}
(async()=>{
  let s=setup();s.start();await s.flush();assert.equal(s.calls(),1);assert.deepEqual(s.events,[]);
  s.respond({version:nextVersion});s.tick();await s.flush();assert.deepEqual(s.events,[nextVersion]);
  s.tick();s.wake();await s.flush();assert.deepEqual(s.events,[nextVersion]);
  s.respond({version:thirdVersion});s.wake();await s.flush();assert.deepEqual(s.events,[nextVersion,thirdVersion]);
  s.respond({version:oldVersion});s.tick();await s.flush();assert.equal(s.events.at(-1),'');
  s.document.visibilityState='hidden';s.tick();const calls=s.calls();s.wake();await s.flush();assert.equal(s.calls(),calls);
  s.document.visibilityState='visible';s.respond({version:nextVersion});s.wake('visibilitychange');await s.flush();assert.equal(s.calls(),calls+1);
  s.fail(true);s.tick();await s.flush();assert.equal(s.events.at(-1),nextVersion);
  s.fail(false);for(const data of [{},null,{version:'bad'},'HTML']){s.respond(data);s.tick();await s.flush();assert.equal(s.events.at(-1),nextVersion);}
  s.stop();assert.equal(s.intervals.size,0);assert.equal(s.timeouts.size,0);const stopped=s.calls();s.wake();await s.flush();assert.equal(s.calls(),stopped);
  s=setup();s.start('');s.tick();await s.flush();assert.equal(s.calls(),0);
  s=setup();let resolve;s.hold(new Promise(r=>{resolve=r;}));s.start();s.tick();s.wake();assert.equal(s.calls(),1);
  s.stop();resolve({ok:true,json:async()=>({version:nextVersion})});await s.flush();assert.deepEqual(s.events,[]);
  s=setup();let captured;s.window.fetch=async(_,options)=>{captured=options.signal;return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted'))));};
  s.start();for(const fn of s.timeouts.values())fn();await s.flush();assert.equal(captured.aborted,true);assert.deepEqual(s.events,[]);s.stop();
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'oa-version-'));
  try{
    fs.writeFileSync(path.join(dir,'index.html'),`<meta content="${oldVersion}" name="oa-build-version">`);
    assert.equal(writeVersion(dir),oldVersion);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'version.json'))).version,oldVersion);
    fs.writeFileSync(path.join(dir,'index.html'),'<html>missing version</html>');assert.throws(()=>writeVersion(dir));
  }finally{fs.rmSync(dir,{recursive:true});}
  console.log('Version detection, visibility, deduplication, rollback, offline, timeout, cleanup and build metadata checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
