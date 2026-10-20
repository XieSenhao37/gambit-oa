"""Apply the two store return contacts supplied by the user on 2026-10-19.
Default is read-only. Updates only the existing policy JSON through the test Go API.
"""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
remote = r'''docker exec -i gambit-oa-test python - <<'CHECK'
import json, os
from urllib.parse import urlsplit
import requests
from sqlalchemy import text
from app import create_app, db
apply = APPLY_VALUE
expected = {
    '南山店': {'ReturnRecipient': '桌游归', 'ReturnPhone': '17376748528', 'ReturnAddress': '广东省深圳市南山区万科云城设计公社D-0203（Gambit）'},
    '罗湖店': {'ReturnRecipient': '桌游归', 'ReturnPhone': '19584699387', 'ReturnAddress': '广东省深圳市罗湖区新白马次元9号B1层（Gambit）'},
}
app = create_app()
with app.app_context():
    u = urlsplit(app.config['SQLALCHEMY_DATABASE_URI'])
    base = app.config['GAMBIT_SERVER_BASE_URL'].rstrip('/')
    assert u.hostname == 'gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com' and u.port == 21085 and u.path == '/gambit'
    assert base == 'https://test-golang-137415-10-1301993689.sh.run.tcloudbase.com'
    token = app.config['GAMBIT_INTERNAL_TOKEN']
    def call(path, method='GET', payload=None):
        r = requests.request(method, base + '/microapp_api/admin/game-service/v1/' + path, params=payload if method == 'GET' else None, json=payload if method != 'GET' else None, headers={'X-GAMBIT-INTERNAL-TOKEN': token}, timeout=25)
        r.raise_for_status()
        body = r.json()
        assert body.get('Code') == 0, body.get('Msg', 'request failed')
        return body.get('Data')
    db.session.execute(text('SET TRANSACTION READ ONLY'))
    rows = db.session.execute(text("SELECT id, name FROM stores WHERE name IN ('南山店', '罗湖店') AND status=1 AND deleted_at IS NULL")).mappings().all()
    assert len(rows) == 2 and {r['name'] for r in rows} == set(expected), 'Store identity mismatch'
    db.session.rollback()
    planned = []
    for row in rows:
        current = call('policy', payload={'StoreID': row['id']})
        desired = expected[row['name']]
        for key, value in desired.items():
            assert not current['Policy'].get(key) or current['Policy'][key] == value, 'Existing return contact differs; refusing overwrite'
        planned.append((dict(row), current, desired))
    print(json.dumps({'Preflight': 'passed', 'Stores': [r['name'] for r, _, _ in planned], 'OnlyFields': list(next(iter(expected.values()))), 'Apply': apply}, ensure_ascii=False))
    if apply:
        caps = requests.get(base + '/microapp_api/game-service/v1/capabilities', timeout=25).json()['Data']
        assert caps['Ready'] and caps['Version'] == '2026-10-19.6', 'Wait for verified Go deployment'
        # Preserve a private recovery snapshot in the test container; never log internal credentials.
        backup = '/tmp/game-return-addresses-before-20261019.json'
        try:
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f: json.dump(planned, f, ensure_ascii=False)
        except FileExistsError:
            pass
        for row, current, desired in planned:
            if not all(current['Policy'].get(k) == v for k, v in desired.items()):
                call('policy', 'PUT', {'StoreID': row['id'], 'Revision': current['Revision'], 'Policy': {**current['Policy'], **desired}, 'Actor': 'codex-user-return-address-request'})
            actual = call('policy', payload={'StoreID': row['id']})['Policy']
            assert all(actual.get(k) == v for k, v in desired.items())
            assert all(actual.get(k) == v for k, v in current['Policy'].items() if k not in desired), 'Other policy fields changed'
            print(json.dumps({'Store': row['name'], 'StoreID': row['id'], 'ReturnContactVerified': True, 'OtherPolicyFieldsUnchanged': True}, ensure_ascii=False))
CHECK'''.replace('APPLY_VALUE', str(args.apply))
env = dict(os.environ, DISPLAY='codex', SSH_ASKPASS_REQUIRE='force', SSH_ASKPASS=str(root/'scripts/ssh-askpass-test-server.sh'))
result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=no', '-o', 'PreferredAuthentications=password', '-o', 'NumberOfPasswordPrompts=1', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', 'root@49.232.4.107', 'bash -s'], input=remote, text=True, env=env)
raise SystemExit(result.returncode)
