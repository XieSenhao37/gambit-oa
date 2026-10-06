"""将现有首页 Banner 迁入 OA 配置；逐环境输入密码，不改变旧客户端数据。"""
import argparse
import datetime
import getpass
import importlib.util
import json
import os
import pathlib
import queue
import shutil
import subprocess
import tempfile
import threading
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--environment', choices=['test'], default='test')
options = parser.parse_args()
source = pathlib.Path(__file__).resolve().parents[1] / 'app/services/home_banners.py'
spec = importlib.util.spec_from_file_location('home_banners_migration', source)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
MYSQL = shutil.which('mysql') or '/opt/homebrew/opt/mysql-client@8.0/bin/mysql'
BASE = pathlib.Path(tempfile.mkdtemp(prefix='gambit-home-banners-'))
pathlib.Path('/tmp/gambit-home-banners-latest-path').write_text(str(BASE))
def save(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
def literal(value): return "CONVERT(X'" + value.encode('utf-8').hex() + "' USING utf8mb4)"
class Client:
    def __init__(self,config,env):
        self.errors=BASE/(env+'-client.log')
        self.err=self.errors.open('w')
        self.proc=subprocess.Popen([MYSQL,'--defaults-extra-file='+str(config),'--connect-timeout=20','--default-character-set=utf8mb4','--batch','--raw','--skip-column-names','--unbuffered','--skip-reconnect','gambit'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        self.lines=queue.Queue()
        def read():
            for line in self.proc.stdout:self.lines.put(line.rstrip('\n'))
            self.lines.put(None)
        threading.Thread(target=read,daemon=True).start()
    def query(self,sql):
        marker='DONE_'+uuid.uuid4().hex
        self.proc.stdin.write(sql+';\nSELECT '+literal(marker)+';\n');self.proc.stdin.flush()
        rows=[]
        while True:
            try:line=self.lines.get(timeout=45)
            except queue.Empty:raise RuntimeError('数据库响应超时')
            if line is None:raise RuntimeError(self.errors.read_text().strip() or 'MySQL 连接已关闭')
            if line==marker:return rows
            rows.append(line)
    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.err.close()

results = []
for env, host, port in [('test','gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com',21085),('production','sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com',22120)]:
    if options.environment not in ('both', env): continue
    client = None
    config_file = BASE / (env+'-connection.cnf')
    committed = False
    print('\n'+('测试库' if env == 'test' else '正式库')+' Banner 迁移：'+host+':'+str(port), flush=True)
    password = getpass.getpass('请输入此环境 root 密码（不会显示）：')
    try:
        escaped = password.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')
        with os.fdopen(os.open(config_file, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600),'w') as f:
            f.write('[client]\nhost='+host+'\nport='+str(port)+'\nuser=root\npassword="'+escaped+'"\n')
        del password, escaped
        client = Client(config_file, env)
        identity = client.query('SELECT DATABASE(),VERSION(),@@hostname')
        if len(identity) != 1 or identity[0].split('\t')[0] != 'gambit': raise RuntimeError('数据库身份核验失败')
        client.query('START TRANSACTION')
        rows = client.query("SELECT JSON_OBJECT('id',id,'value',config_value,'deleted',deleted_at) FROM configs WHERE config_key='CommonConfig' FOR UPDATE")
        if len(rows) != 1: raise RuntimeError('未找到唯一公共配置，已停止，请检查该环境')
        row = json.loads(rows[0])
        if row['deleted'] is not None: raise RuntimeError('公共配置已停用，停止迁移')
        before = row['value']
        if not isinstance(before,dict): raise RuntimeError('公共配置格式错误')
        save(BASE/(env+'-before.json'), before)
        items = helper.validate_items(helper.migrate_banners(before))
        if helper.ITEMS_KEY not in before:
            client.query("UPDATE configs SET config_value=JSON_SET(config_value,'$.HomeBannerItems',CAST("+literal(json.dumps(items,ensure_ascii=False))+" AS JSON)),updated_at=NOW(3) WHERE id="+str(int(row['id'])))
        read_sql = 'SELECT config_value FROM configs WHERE id='+str(int(row['id']))
        after = json.loads(client.query(read_sql)[0])
        if {k:v for k,v in after.items() if k != helper.ITEMS_KEY} != {k:v for k,v in before.items() if k != helper.ITEMS_KEY}: raise RuntimeError('其他公共配置发生变化，已停止')
        if after.get(helper.ITEMS_KEY) != before.get(helper.ITEMS_KEY,items): raise RuntimeError('Banner 配置核验失败')
        client.query('COMMIT'); committed = True
        confirmed = json.loads(client.query(read_sql)[0])
        if confirmed != after: raise RuntimeError('提交后配置核验失败')
        save(BASE/(env+'-after.json'),confirmed)
        result={'environment':env,'status':'completed','host':host,'count':len(items),'items':[{'title':b['Title'],'action':b['Action']} for b in items],'already_migrated':helper.ITEMS_KEY in before}
        results.append(result); save(BASE/'status.json',results)
        print('迁移完成：'+str(len(items))+' 条 Banner，原有点击方式及其他配置已保留。',flush=True)
    except Exception as exc:
        if client and not committed:
            try: client.query('ROLLBACK')
            except Exception: pass
        results.append({'environment':env,'status':'failed','committed':committed,'error':str(exc)})
        save(BASE/'status.json',results)
        print('迁移失败：'+str(exc),flush=True)
        break
    finally:
        if client: client.close()
        config_file.unlink(missing_ok=True)
expected=2 if options.environment=='both' else 1
print('\n备份及核验结果：'+str(BASE),flush=True)
print('ALL_BANNER_MIGRATIONS_COMPLETED' if len(results)==expected and all(r['status']=='completed' for r in results) else 'BANNER_MIGRATION_INCOMPLETE',flush=True)
