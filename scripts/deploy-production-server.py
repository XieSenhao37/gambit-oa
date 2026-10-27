#!/usr/bin/env python3
"""Deploy a reviewed OA image by digest; Go deployment is outside this command.

Default is read-only preflight. --apply replaces the production OA image and
preserves every runtime environment value. --sms-login additionally performs the
previously supported explicit SMS login switch. Credentials never leave the server.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'ccr.ccs.tencentyun.com/gambit/gambit_oa'


def remote(payload):
    import datetime
    import hashlib
    import secrets
    import socket
    import time
    from urllib.parse import urlsplit
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

    def docker(*args):
        result=subprocess.run(['docker',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        if result.returncode:
            raise RuntimeError('Docker command failed: '+args[0])
        return result.stdout.decode('utf-8').strip()

    def inspect(name):
        return json.loads(docker('inspect',name))[0]

    def environment(container):
        return dict(item.split('=',1) for item in container['Config']['Env'] if '=' in item)

    def stamp(container):
        return [container['Id'],container['Image'],container['State']['StartedAt']]

    def emit(event,**values):
        print(json.dumps({'event':event,**values}),flush=True)

    def http(base,path):
        try:
            with urlopen(Request(base+path,headers={'Accept-Encoding':'gzip'}),timeout=10) as response:
                return response.status,dict(response.headers),response.read()
        except HTTPError as error:
            return error.code,dict(error.headers),error.read()

    def validate_http(port,expected_version=None):
        base='http://127.0.0.1:'+str(port)
        for attempt in range(30):
            try:
                status,_,body=http(base,'/health')
                if status==200 and json.loads(body).get('status')=='healthy':break
            except Exception:pass
            time.sleep(1)
        else:raise RuntimeError('OA health check failed')
        status,headers,body=http(base,'/version.json')
        version=json.loads(body)['version']
        if status!=200 or 'no-store' not in headers.get('Cache-Control',''):
            raise RuntimeError('OA version manifest check failed')
        if expected_version and version!=expected_version:
            raise RuntimeError('OA build version mismatch')
        status,_,html=http(base,'/login')
        if status!=200 or version.encode() not in html:
            raise RuntimeError('OA login page version mismatch')
        assets=re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]+\.(?:js|css))[\"\x27]',html)
        if not assets:raise RuntimeError('No entry assets in OA HTML')
        for asset in assets:
            path='/'+asset.decode().lstrip('/')
            status,headers,_=http(base,path)
            if status!=200 or not any(t in headers.get('Content-Type','') for t in ('javascript','css')):
                raise RuntimeError('OA entry asset is unavailable')
        status,_,body=http(base,'/admin_api/auth/v1/status')
        auth=json.loads(body)
        if status!=200 or auth.get('Data',{}).get('LoginMode')!='sms' or not auth['Data'].get('SmsReady'):
            raise RuntimeError('OA SMS login configuration check failed')
        for path in ('/admin_api/game-service/v1/orders','/admin_api/game-service/v1/community','/admin_api/month-card/v1/config','/admin_api/dish/v1/categories'):
            if http(base,path)[0]!=401:raise RuntimeError('Anonymous access guard failed')
        return {'version':version,'entry_assets':len(assets),'login_mode':'sms','sms_ready':True,'anonymous_guards':'passed'}

    try:
        prod=inspect('gambit-oa');test=inspect('gambit-oa-test')
        previous_stamp=stamp(prod);test_stamp=stamp(test)
        env=environment(prod);test_env=environment(test)
        u=urlsplit(env.get('DATABASE_URL',''))
        if (u.scheme,u.hostname,u.port,u.path)!=('mysql+pymysql','sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com',22120,'/gambit'):
            raise RuntimeError('Production database target mismatch')
        if env.get('GAMBIT_SERVER_BASE_URL','').rstrip('/')!='https://golang-mfne-137415-10-1301993689.sh.run.tcloudbase.com':
            raise RuntimeError('Production Go target mismatch')
        if prod['Id']!=payload['expected_container_id'] or not prod['State']['Running']:
            raise RuntimeError('Production container changed since review')
        if prod['Mounts'] or prod['HostConfig']['NetworkMode']!='bridge':
            raise RuntimeError('Unexpected production mounts or network; refusing to discard configuration')
        if prod['HostConfig']['PortBindings']!={'8080/tcp':[{'HostIp':'','HostPort':'8080'}]}:
            raise RuntimeError('Production port mapping mismatch')
        required=('JWT_SECRET','SECRET_KEY','PHONE_CRYPTO_KEY','GAMBIT_INTERNAL_TOKEN','STORE_SETTLEMENT_ENABLED')
        if not all(env.get(key) for key in required):raise RuntimeError('Missing production configuration')
        if payload['sms_login']:
            public_sms=('TENCENT_SMS_APP_ID','TENCENT_SMS_SIGN_NAME','TENCENT_SMS_TEMPLATE_ID')
            if not all(test_env.get(key) for key in public_sms):raise RuntimeError('Reviewed SMS configuration unavailable')
            if test_env.get('TENCENT_SMS_SECRET_ID')!=env.get('COS_SECRET_ID') or test_env.get('TENCENT_SMS_SECRET_KEY')!=env.get('COS_SECRET_KEY'):
                raise RuntimeError('Reviewed SMS credentials do not match production cloud credentials')
        emit('preflight',container_id=prod['Id'],old_image=prod['Image'],settlement_enabled=env['STORE_SETTLEMENT_ENABLED'],test_container_id=test['Id'])
        if not payload['apply']:
            emit('result',status='checked_not_applied');return
        image=IMAGE+'@'+payload['digest']
        docker('pull',image)
        expected_image=json.loads(docker('image','inspect',image))[0]
        if expected_image['Architecture']!='amd64':raise RuntimeError('Unexpected image architecture')
        release=expected_image['Config'].get('Labels',{}).get('org.opencontainers.image.revision','')
        if release!=payload['source_commit']:raise RuntimeError('Unexpected OA source revision')
        directory=Path('/root/gambit-oa-codex-production')
        directory.mkdir(mode=0o700,exist_ok=True)
        os.chmod(directory,0o700)
        backup=directory/('release-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+release)
        backup.mkdir(mode=0o700)
        with os.fdopen(os.open(backup/'previous-container.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w',encoding='utf-8') as stream:
            json.dump(prod,stream)
        updated=dict(env)
        if payload['sms_login']:
            updated['OA_LOGIN_MODE']='sms'
            if len(updated.get('OA_AUTH_SECRET',''))<32:updated['OA_AUTH_SECRET']=secrets.token_hex(32)
            updated['TENCENT_SMS_SECRET_ID']=env['COS_SECRET_ID']
            updated['TENCENT_SMS_SECRET_KEY']=env['COS_SECRET_KEY']
            for key in public_sms:updated[key]=test_env[key]
            updated['TENCENT_SMS_REGION']=test_env.get('TENCENT_SMS_REGION','ap-guangzhou')
        changed=sorted(key for key in updated if updated[key]!=env.get(key))
        allowed={'OA_LOGIN_MODE','OA_AUTH_SECRET','TENCENT_SMS_SECRET_ID','TENCENT_SMS_SECRET_KEY','TENCENT_SMS_APP_ID','TENCENT_SMS_SIGN_NAME','TENCENT_SMS_TEMPLATE_ID','TENCENT_SMS_REGION'}
        if not payload['sms_login'] and changed:raise RuntimeError('Runtime configuration must remain unchanged')
        if set(changed)-allowed:raise RuntimeError('Unapproved runtime configuration change')
        if any('\n' in value or '\r' in value for value in updated.values()):raise RuntimeError('Unsupported multiline runtime value')
        envfile=backup/'runtime.env'
        with os.fdopen(os.open(envfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w',encoding='utf-8') as stream:
            stream.write('\n'.join(key+'='+value for key,value in updated.items())+'\n')
        candidate='gambit-oa-candidate-'+release
        with socket.socket() as sock:sock.bind(('127.0.0.1',28080))
        docker('run','-d','--name',candidate,'--restart=no','--network=bridge','-p','127.0.0.1:28080:8080','--env-file',str(envfile),image)
        candidate_check=validate_http(28080)
        emit('candidate_verified',**candidate_check)
        acceptance = r"""
import contextlib,inspect,io,json
from flask import g
from sqlalchemy import text
from app import create_app,db
from app.models import Store
from app.security.models import StaffAccount
from app.security.policy import principal
from app.api.v1.user import get_user_list
from app.api.v1.game import list_inventory_games
from app.api.v1.month_card import get_month_card_config
from app.api.v1.play_pricing import get_pricing
from app.api.v1.auth import me
from app.api.v1.dish import list_categories
app=create_app({'TESTING':True})
checks=[]
with app.app_context():
 db.session.execute(text('SET TRANSACTION READ ONLY'))
 db.session.execute(text('SET SESSION MAX_EXECUTION_TIME=5000'))
 account=StaffAccount.query.filter_by(enabled=True,headquarters=True).order_by(StaffAccount.user_id).first()
 sid=Store.query.filter_by(deleted_at=None,status=1).order_by(Store.id).first().id
 uid=account.user_id
 # Keep the user smoke query bounded to this existing staff account. An
 # unfiltered paginated list also counts every joined user/payment row.
 for name,fn,path in [('users',get_user_list,f'/admin_api/user/v1/list?Current=1&PageSize=1&Id={uid}'),('inventory',list_inventory_games,'/admin_api/game/v1/inventory/list?PageNum=1&PageSize=1'),('month_card_config',get_month_card_config,'/admin_api/month-card/v1/config'),('play_pricing',get_pricing,'/admin_api/play-pricing/v1'),('staff_permissions',me,'/admin_api/auth/v1/me'),('dish_categories',list_categories,'/admin_api/dish/v1/categories')]:
  with app.test_request_context(path):
   g.staff,g.staff_user,g.grants=principal(uid)
   g.store_id=sid;g.scope_store=sid
   with contextlib.redirect_stdout(io.StringIO()):response=app.make_response(inspect.unwrap(fn)())
   if response.status_code!=200 or response.get_json().get('Code')!=0:raise RuntimeError('Read-only acceptance failed: '+name)
   checks.append(name)
 db.session.rollback()
print(json.dumps({'read_only_business_queries':checks,'business_writes':False,'new_login_sessions':False}))
"""
        acceptance_result = json.loads(docker('exec','-i',candidate,'python','-c',acceptance).splitlines()[-1])
        emit('candidate_read_only_queries_verified',**acceptance_result)
        if stamp(inspect('gambit-oa'))!=previous_stamp:raise RuntimeError('Production changed before switch')
        if stamp(inspect('gambit-oa-test'))!=test_stamp:raise RuntimeError('Test container changed before switch')
        archived='gambit-oa-before-'+release
        docker('stop','--time','30','gambit-oa')
        docker('rename','gambit-oa',archived)
        docker('update','--restart=no',archived)
        restart=prod['HostConfig']['RestartPolicy']['Name'] or 'no'
        docker('run','-d','--name','gambit-oa','--restart='+restart,'--network=bridge','-p','8080:8080','--env-file',str(envfile),image)
        final_check=validate_http(8080,candidate_check['version'])
        new=inspect('gambit-oa');new_env=environment(new)
        if new['Image']!=expected_image['Id']:raise RuntimeError('Running production image mismatch')
        if new_env!=updated:raise RuntimeError('Running production environment mismatch')
        if stamp(inspect('gambit-oa-test'))!=test_stamp:raise RuntimeError('Test container changed during deployment')
        docker('rm','-f',candidate)
        report={'status':'completed','source_commit':release,'image_digest':payload['digest'],'image_id':new['Image'],
                'production_container_id':new['Id'],'previous_container':archived,'private_configuration_directory':str(backup),
                'changed_environment_keys':changed,'other_runtime_configuration_preserved':True,'settlement_enabled':new_env['STORE_SETTLEMENT_ENABLED'],
                'test_container_unchanged':True,'go_deployment_performed':False,**final_check}
        (backup/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        emit('result',**report)
    except Exception as error:
        import traceback
        emit('failed',error=str(error) if isinstance(error,RuntimeError) else type(error).__name__,location=[{'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)])
        raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--digest',required=True)
    parser.add_argument('--expected-container-id',required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--sms-login',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',args.digest):parser.error('Invalid image digest')
    if not re.fullmatch(r'[0-9a-f]{64}',args.expected_container_id):parser.error('Invalid container ID')
    if not re.fullmatch(r'[0-9a-f]{7,40}',args.source_commit):parser.error('Invalid source commit')
    payload=vars(args)
    payload['runner']=Path(__file__).read_text()
    report=Path(tempfile.mkdtemp(prefix='gambit-oa-production-20261021-'))
    print(json.dumps({'audit_directory':str(report)}),flush=True)
    code="import json,sys,types; p=json.load(sys.stdin); m=types.ModuleType('reviewed_oa_deployment'); m.__file__='/tmp/reviewed_oa_deployment.py'; exec(compile(p['runner'],m.__file__,'exec'),m.__dict__); m.remote(p)"
    command='python3 -c '+shlex.quote(code)
    env=dict(os.environ,LC_ALL='C',LANG='C',DISPLAY='codex',SSH_ASKPASS_REQUIRE='force',SSH_ASKPASS=str(ROOT/'scripts/ssh-askpass-test-server.sh'))
    result=subprocess.run(['ssh','-T','-o','BatchMode=no','-o','PreferredAuthentications=password',
        '-o','NumberOfPasswordPrompts=1','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
        '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-p','22','root@49.232.4.107',command],
        input=json.dumps(payload),text=True,capture_output=True,env=env,timeout=600)
    (report/'events.jsonl').write_text(result.stdout)
    print(result.stdout)
    if result.returncode:print('Deployment not complete; audit directory: '+str(report))
    return result.returncode


if __name__=='__main__':sys.exit(main())
