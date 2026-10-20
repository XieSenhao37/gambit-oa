#!/usr/bin/env python3
"""Apply only the reviewed shared-quota/return/buyout schema to the explicitly verified test database.
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
SQL = ROOT.parent / 'GambitServer/sql/20261017_shared_game_inventory.sql'
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
allowed=re.compile(r'^(?:CREATE TABLE IF NOT EXISTS game_service_(?:inventories|refund_parts)\s*\(|SET @game_migration_sql\s*=|PREPARE game_migration_stmt\b|EXECUTE game_migration_stmt$|DEALLOCATE PREPARE game_migration_stmt$)', re.I)
if len(statements)!=62 or any(not allowed.match(s) for s in statements):
    sys.exit('MIGRATION_BLOCKED: schema includes unrecognized statements')
if any(word in clean.upper() for word in ('DROP TABLE','TRUNCATE','DELETE FROM','INSERT INTO','UPDATE ')):
    sys.exit('MIGRATION_BLOCKED: schema includes business-data mutations')
engine=create_engine(os.environ['DATABASE_URL'], echo=False)
tables=['game_service_inventories','game_service_refund_parts']
order_columns=['reserved_at','return_requested_at','return_tracking_company','return_tracking_number','auto_refund','deposit_applied','parent_order_id','parent_line_id','buyout_refund']
line_columns=['buyout_price','buyout_until','bought','buyout_terms']
with engine.connect() as conn:
    if conn.execute(text('SELECT DATABASE()')).scalar()!='gambit': sys.exit('MIGRATION_BLOCKED: selected database mismatch')
    inspector=inspect(conn)
    existing=[name for name in tables if inspector.has_table(name)]
    present=[c['name'] for c in inspector.get_columns('game_service_orders')]
    line_present=[c['name'] for c in inspector.get_columns('game_service_order_lines')]
    old_offers=conn.execute(text('SELECT COUNT(*) FROM game_service_stocks')).scalar()
    active_orders=conn.execute(text("SELECT COUNT(*) FROM game_service_orders WHERE status NOT IN ('completed','cancelled','refunded')")).scalar()
    multi_offers=conn.execute(text('SELECT COUNT(*) FROM (SELECT store_id,board_game_id,kind FROM game_service_stocks GROUP BY store_id,board_game_id,kind HAVING COUNT(*)>1) t')).scalar()
    print(json.dumps({'Preflight':'passed','Target':'Guangzhou test database','ExistingNewTables':existing,'MissingOrderColumns':[c for c in order_columns if c not in present],'MissingLineColumns':[c for c in line_columns if c not in line_present],'ExistingOffers':old_offers,'ActiveOrders':active_orders,'MultipleOfferGroupsRequiringReview':multi_offers,'SchemaSHA256':payload['SHA256']},ensure_ascii=True),flush=True)
    if payload.get('Convert') and (active_orders or multi_offers):
        sys.exit('MIGRATION_BLOCKED: conversion requires no active orders and no multiple-offer groups')
    if payload['Apply']:
        for statement in statements: conn.exec_driver_sql(statement)
        conn.commit()
        inspector=inspect(conn)
        if not all(inspector.has_table(name) for name in tables) or not set(order_columns).issubset(c['name'] for c in inspector.get_columns('game_service_orders')) or not set(line_columns).issubset(c['name'] for c in inspector.get_columns('game_service_order_lines')):
            sys.exit('MIGRATION_FAILED: schema verification did not pass')
        print(json.dumps({'Migration':'verified','Tables':tables,'AddedOrderColumns':order_columns,'AddedLineColumns':line_columns,'BusinessDataChanged':False},ensure_ascii=True),flush=True)
        if payload.get('Convert'):
            # Parent -> shared row -> offers: same lock order as the new Go backend.
            groups=conn.execute(text('SELECT DISTINCT store_id,board_game_id FROM game_service_stocks ORDER BY store_id,board_game_id')).all()
            converted=0
            for store,game in groups:
                total=conn.execute(text('SELECT count FROM board_game_store_inventories WHERE store_id=:s AND board_game_id=:g AND deleted_at IS NULL FOR UPDATE'),{'s':store,'g':game}).scalar()
                existing=conn.execute(text('SELECT id FROM game_service_inventories WHERE store_id=:s AND board_game_id=:g FOR UPDATE'),{'s':store,'g':game}).scalar()
                if existing is not None: continue
                offers=conn.execute(text('SELECT kind,quantity,reserved,`out`,held FROM game_service_stocks WHERE store_id=:s AND board_game_id=:g ORDER BY id FOR UPDATE'),{'s':store,'g':game}).all()
                quota=sum(r[1] for r in offers)
                if total is None or quota>total or len(set(r[0] for r in offers))!=len(offers) or any(r[1]<r[2]+r[3]+r[4] or min(r[1:])<0 for r in offers):
                    raise RuntimeError('Conversion blocked: inventory/configuration changed since preflight')
                conn.execute(text('INSERT INTO game_service_inventories (store_id,board_game_id,quantity,buyout_enabled,version,created_at,updated_at) VALUES (:s,:g,:q,0,1,NOW(),NOW())'),{'s':store,'g':game,'q':quota})
                converted+=1
            conn.commit()
            print(json.dumps({'Conversion':'verified','SharedGroupsCreated':converted,'PricesChanged':False,'PhysicalTotalsChanged':False,'BuyoutEnabled':False},ensure_ascii=True),flush=True)
engine.dispose()
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--convert-existing',action='store_true',help='After the new backend is deployed, convert old single-offer groups to shared quota; requires explicit data migration authorization')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('test_deploy',ROOT/'scripts/deploy-test-server.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.config()
    sql=SQL.read_text()
    payload={'SQL':sql,'SHA256':hashlib.sha256(sql.encode()).hexdigest(),'Apply':args.apply,'Convert':args.convert_existing}
    command='docker exec -i gambit-oa-test python -c '+shlex.quote(REMOTE)
    env=dict(os.environ,LC_ALL='C',LANG='C',DISPLAY='codex',SSH_ASKPASS_REQUIRE='force',SSH_ASKPASS=str(ROOT/'scripts/ssh-askpass-test-server.sh'))
    result=subprocess.run(['ssh','-T','-o','BatchMode=no','-o','PreferredAuthentications=password','-o','NumberOfPasswordPrompts=1','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-p','22','root@49.232.4.107',command],input=json.dumps(payload),text=True,env=env)
    raise SystemExit(result.returncode)
if __name__=='__main__': main()
