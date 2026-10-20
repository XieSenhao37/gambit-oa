#!/usr/bin/env python3
"""Apply only the additive board-game schema to the explicitly verified test database.
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
SQL = ROOT.parent / 'GambitServer/sql/20261008_create_game_services.sql'
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
allowed=re.compile(r'^(?:SET NAMES utf8mb4\b|CREATE TABLE IF NOT EXISTS game_(?:service_policies|service_stocks|service_orders|service_order_lines|service_movements|player_intents|player_shares)\s*\(|SET @game_pay_(?:column|sql)\s*=|PREPARE game_pay_stmt\b|EXECUTE game_pay_stmt$|DEALLOCATE PREPARE game_pay_stmt$)', re.I)
if len(statements)!=13 or any(not allowed.match(s) for s in statements):
    sys.exit('MIGRATION_BLOCKED: schema includes unrecognized statements')
if any(word in clean.upper() for word in ('DROP TABLE','TRUNCATE','DELETE FROM','INSERT INTO','UPDATE PAY_')):
    sys.exit('MIGRATION_BLOCKED: schema includes data mutations')
engine=create_engine(os.environ['DATABASE_URL'], echo=False)
tables=['game_service_policies','game_service_stocks','game_service_orders','game_service_order_lines','game_service_movements','game_player_intents','game_player_shares']
with engine.connect() as conn:
    if conn.execute(text('SELECT DATABASE()')).scalar()!='gambit': sys.exit('MIGRATION_BLOCKED: selected database mismatch')
    inspector=inspect(conn)
    columns=[c['name'] for c in inspector.get_columns('pay_orders')]
    existing=[name for name in tables if inspector.has_table(name)]
    print(json.dumps({'Preflight':'passed','Target':'Guangzhou test database','ExistingModuleTables':len(existing),'PayColumnPresent':'board_game_order_id' in columns,'SchemaSHA256':payload['SHA256']},ensure_ascii=True),flush=True)
    if payload['Apply']:
        for statement in statements:
            conn.exec_driver_sql(statement)
        conn.commit()
        inspector=inspect(conn)
        if not all(inspector.has_table(name) for name in tables) or 'board_game_order_id' not in [c['name'] for c in inspector.get_columns('pay_orders')] or 'lost' not in [c['name'] for c in inspector.get_columns('game_service_order_lines')]:
            sys.exit('MIGRATION_FAILED: schema verification did not pass')
        print(json.dumps({'Migration':'verified','Tables':tables,'PayColumn':'board_game_order_id','SeededBusinessRows':0},ensure_ascii=True),flush=True)
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
