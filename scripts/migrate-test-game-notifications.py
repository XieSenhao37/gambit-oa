#!/usr/bin/env python3
"""Apply only the reviewed board-game confirmation notification table to the explicitly verified test database.
Default mode performs read-only preflight. Credentials remain inside the test container.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT.parent / 'GambitServer/docs/sql/20261018_game_confirmation_notifications.sql'
REMOTE = r'''
import hashlib, json, os, re, sys
from urllib.parse import urlsplit
from sqlalchemy import create_engine, text, inspect
payload=json.load(sys.stdin)
u=urlsplit(os.environ.get('DATABASE_URL',''))
base=os.environ.get('GAMBIT_SERVER_BASE_URL','').rstrip('/')
if not (u.scheme=='mysql+pymysql' and u.hostname=='gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com' and u.port==21085 and u.path=='/gambit' and base=='https://test-golang-137415-10-1301993689.sh.run.tcloudbase.com'):
    sys.exit('MIGRATION_BLOCKED: target differs from the authorized test environment')
sql=payload['SQL']
if hashlib.sha256(sql.encode()).hexdigest()!=payload['SHA256']:
    sys.exit('MIGRATION_BLOCKED: schema checksum differs')
clean=re.sub(r'(?m)^--[^\n]*','',sql)
statements=[s.strip() for s in clean.split(';') if s.strip()]
if len(statements)!=1 or not re.match(r'^CREATE TABLE IF NOT EXISTS game_confirmation_notifications\s*\(',statements[0],re.I):
    sys.exit('MIGRATION_BLOCKED: unexpected schema statement')
if any(word in clean.upper() for word in ('DROP TABLE','TRUNCATE','DELETE FROM','INSERT INTO','UPDATE ')):
    sys.exit('MIGRATION_BLOCKED: business-data mutation')
engine=create_engine(os.environ['DATABASE_URL'], echo=False)
name='game_confirmation_notifications'
with engine.connect() as conn:
    if conn.execute(text('SELECT DATABASE()')).scalar()!='gambit': sys.exit('MIGRATION_BLOCKED: database mismatch')
    exists=inspect(conn).has_table(name)
    print(json.dumps({'Preflight':'passed','Target':'Guangzhou test database:21085/gambit','Table':name,'Exists':exists,'SchemaSHA256':payload['SHA256']},ensure_ascii=True),flush=True)
    if payload['Apply']:
        conn.exec_driver_sql(statements[0])
        conn.commit()
        inspector=inspect(conn)
        columns={c['name'] for c in inspector.get_columns(name)}
        expected={'id','created_at','updated_at','order_id','status','attempts','next_attempt_at','last_error','sent_at'}
        unique=inspector.get_indexes(name)
        if columns!=expected or not any(i.get('unique') and i['column_names']==['order_id'] for i in unique):
            sys.exit('MIGRATION_FAILED: table shape mismatch')
        print(json.dumps({'Migration':'verified','Table':name,'ExistingBusinessDataChanged':False},ensure_ascii=True),flush=True)
engine.dispose()
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('test_deploy',ROOT/'scripts/deploy-test-server.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.config()
    sql=SQL.read_text()
    payload={'SQL':sql,'SHA256':hashlib.sha256(sql.encode()).hexdigest(),'Apply':args.apply}
    command='docker exec -i gambit-oa-test python -c '+shlex.quote(REMOTE)
    env=dict(os.environ,LC_ALL='C',LANG='C',DISPLAY='codex',SSH_ASKPASS_REQUIRE='force',SSH_ASKPASS=str(ROOT/'scripts/ssh-askpass-test-server.sh'))
    result=subprocess.run(['ssh','-T','-o','BatchMode=no','-o','PreferredAuthentications=password','-o','NumberOfPasswordPrompts=1','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-p','22','root@49.232.4.107',command],input=json.dumps(payload),text=True,env=env)
    raise SystemExit(result.returncode)
if __name__=='__main__': main()
