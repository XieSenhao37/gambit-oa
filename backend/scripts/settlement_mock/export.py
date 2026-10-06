"""Export reviewed fixture SQL and manifest without opening any database."""
import os,sys,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
os.environ['DATABASE_URL']='sqlite://'
sys.path.insert(0,str(ROOT))
from app import db
from app import models
from app.settlement import models as settlement_models
from fixture import build,insert_sql,PREFIX,BASE,START

def export():
    rows,fixes,labels=build(db.metadata)
    target=Path(__file__).parent
    statements=["CREATE TEMPORARY TABLE `_mock_settlement_guard` (`ok` INT NOT NULL CHECK (`ok`=1));",
        f"INSERT INTO `_mock_settlement_guard` VALUES (IF(@gambit_mock_authorized='{PREFIX}' AND @gambit_mock_target_db=DATABASE(),1,0));",
        "UPDATE `settlement_controls` SET `cutoff`='2026-07-01 00:00:00' WHERE `id`=1 AND `cutoff`=@mock_original_cutoff;"]
    statements += [insert_sql(table,row) for table,row in rows]
    statements.append('DROP TEMPORARY TABLE `_mock_settlement_guard`;')
    sql='-- ONLY GUANGZHOU TEST DATABASE. No production use.\n-- Run with run.py: hidden password, endpoint checks, transaction, backups and validation.\n-- No COMMIT here: the runner commits ONLY after verification.\n\n'+'\n\n'.join(statements)+'\n'
    (target/'seed.sql').write_text(sql)
    manifest=dict(prefix=PREFIX,cutoff=str(START),sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        rows=[dict(table=t,values=r) for t,r in rows],fixes=fixes,counts=dict(Counter(t for t,r in rows)),
        labels={name:dict(table=t,id=r['id']) for name,(t,r) in labels.items()})
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(dict(files=['seed.sql','manifest.json'],counts=manifest['counts'],total=len(rows)),ensure_ascii=False))
    return manifest
if __name__=='__main__':export()
