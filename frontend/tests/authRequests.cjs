const fs = require('node:fs');
const ts = require('typescript');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const calls = [];
const failure = {code:'ECONNABORTED',request:{}};
const context = {exports:{},require:()=>({request:async (path,options)=>{
  calls.push({path,options}); throw failure;
}})};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/services/auth.ts','utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}
}).outputText, context);
(async()=>{
  const auth=context.exports;
  await assert.rejects(auth.sendCode('13800138001'));
  assert.equal(calls.length,1,'transport failure must not resend an SMS');
  assert.ok(calls[0].options.timeout>10000);
  assert.equal(calls[0].options.skipErrorHandler,true);
  assert.match(auth.authErrorMessage(failure,'send'),/验证码请求超时/);
  assert.doesNotMatch(auth.authErrorMessage(failure,'send'),/刷新列表|保存|新增/);
  assert.match(auth.authErrorMessage(failure,'login'),/登录请求超时/);
  assert.equal(auth.authErrorMessage({response:{status:429,data:{Message:'操作过于频繁'}}},'send'),'操作过于频繁');
  assert.equal(auth.authResultUncertain({response:{status:429},request:{}}),false);
  assert.equal(auth.authResultUncertain(failure),true);
  await assert.rejects(auth.login({ChallengeId:'isolated',Code:'000000'}));
  assert.equal(calls.length,2,'failed login must not be automatically repeated');
  assert.equal(calls[1].options.skipErrorHandler,true);
  console.log('Auth transport failures preserve one-shot requests and action-specific feedback');
})();

const notices = [], cleared = [], redirects = [];
const appContext = {
  exports:{},
  window:{location:{pathname:'/login'}},
  localStorage:{removeItem:key=>cleared.push(key)},
  sessionStorage:{setItem:()=>{}},
  require:id=> id==='antd' ? {message:{error:value=>notices.push(value)}}
    : id==='@umijs/max' ? {history:{replace:path=>redirects.push(path)}} : {},
};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/app.ts','utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}
}).outputText,appContext);
const unauthorized={response:{status:401,data:{Message:'验证码错误'}}};
const handler=appContext.exports.request.errorConfig.errorHandler;
assert.throws(()=>handler(unauthorized,{skipErrorHandler:true}));
assert.equal(notices.length,0,'login page owns its error message without duplicate shared toasts');
appContext.window.location.pathname='/events';
assert.throws(()=>handler(unauthorized,{skipErrorHandler:true}));
assert.equal(notices.length,1,'protected-page 401 must still invalidate authentication');
assert.ok(cleared.includes('token'));
assert.equal(redirects[0],'/login?reason=expired');
