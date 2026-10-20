#!/usr/bin/env python3
"""Deploy an already-published OA image to the explicitly authorized test server."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'ccr.ccs.tencentyun.com/gambit/gambit_oa'
REMOTE = r'''
export LC_ALL=C LANG=C
set -euo pipefail
cd "$1"
DIGEST="$2"
MODE="$3"
EXPECTED_SCRIPT="$4"
[ -f deploy.sh ] && [ -f .env.deploy.local ]
ACTUAL_SCRIPT=$(sha256sum deploy.sh | awk '{print $1}')
if [ "$ACTUAL_SCRIPT" != "$EXPECTED_SCRIPT" ]; then
  echo 'DEPLOY_BLOCKED: deployment script differs from the verified local version' >&2
  exit 1
fi
set -a
. ./.env.deploy.local
set +a
# Resolve exactly the same test defaults as deploy.sh. Do not print credential values.
export DATABASE_URL="${DATABASE_URL:-}"
export CONTAINER="${CONTAINER:-gambit-oa-test}"
export HOST_PORT="${HOST_PORT:-18080}"
export GAMBIT_SERVER_BASE_URL="${GAMBIT_SERVER_BASE_URL:-https://test-golang-137415-10-1301993689.sh.run.tcloudbase.com}"
python3 - <<'CHECK'
import json, os, sys
from urllib.parse import urlsplit
u = urlsplit(os.environ['DATABASE_URL']) if os.environ['DATABASE_URL'] else None
valid = (os.environ['CONTAINER'] == 'gambit-oa-test' and os.environ['HOST_PORT'] == '18080'
         and os.environ['GAMBIT_SERVER_BASE_URL'].rstrip('/') == 'https://test-golang-137415-10-1301993689.sh.run.tcloudbase.com')
if u:
    valid = valid and u.scheme == 'mysql+pymysql' and u.hostname == 'gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com' and u.port == 21085 and u.path == '/gambit'
else:
    valid = valid and bool(os.environ.get('DB_PASSWORD_ENCODED')) and os.environ.get('DB_NAME', 'gambit') == 'gambit'
required = ['JWT_SECRET', 'GAMBIT_INTERNAL_TOKEN', 'PHONE_CRYPTO_KEY']
mode = os.environ.get('OA_LOGIN_MODE', 'password')
valid = valid and mode in ('password', 'sms')
if mode == 'password': required.append('OA_ADMIN_PASSWORD')
else:
    required.extend(['OA_AUTH_SECRET', 'TENCENT_SMS_SECRET_ID', 'TENCENT_SMS_SECRET_KEY', 'TENCENT_SMS_APP_ID', 'TENCENT_SMS_SIGN_NAME', 'TENCENT_SMS_TEMPLATE_ID'])
    valid = valid and len(os.environ.get('OA_AUTH_SECRET', '')) >= 32
valid = valid and all(os.environ.get(key) for key in required)
if not valid:
    sys.exit('DEPLOY_BLOCKED: test target or required configuration does not match the authorized scope')
print(json.dumps({'Preflight':'passed','Container':'gambit-oa-test','Port':18080,'Database':'Guangzhou test database'}, ensure_ascii=True))
CHECK
PROD_BEFORE=$(docker inspect --format '{{.Id}} {{.Image}} {{.State.StartedAt}}' gambit-oa)
if [ "$MODE" = deploy ]; then
  export DEPLOY_IMAGE="ccr.ccs.tencentyun.com/gambit/gambit_oa@$DIGEST"
  docker pull "$DEPLOY_IMAGE"
  TARGET_ID=$(docker image inspect "$DEPLOY_IMAGE" --format '{{.Id}}')
  CURRENT_ID=$(docker inspect gambit-oa-test --format '{{.Image}}' 2>/dev/null || true)
  RUNNING=$(docker inspect gambit-oa-test --format '{{.State.Running}}' 2>/dev/null || true)
  if [ "$CURRENT_ID" = "$TARGET_ID" ] && [ "$RUNNING" = true ]; then
    echo 'IMAGE_ALREADY_CURRENT: verifying health without restarting'
  else
    DEPLOY_CONFIG="$PWD/.env.deploy.local" bash deploy.sh test
  fi
fi
python3 - "$DIGEST" <<'HEALTH'
import json, subprocess, sys, time
from urllib.request import urlopen
image='ccr.ccs.tencentyun.com/gambit/gambit_oa@'+sys.argv[1]
expected=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]['Id']
container=json.loads(subprocess.check_output(['docker','inspect','gambit-oa-test']))[0]
if container['Image'] != expected or not container['State']['Running']:
    sys.exit('DEPLOY_FAILED: test container is not running the expected image')
healthy=False
for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:18080/health', timeout=3) as response:
            healthy=response.status == 200 and json.loads(response.read().decode('utf-8')).get('status') == 'healthy'
    except Exception:
        healthy=False
    if healthy: break
    time.sleep(2)
if not healthy: sys.exit('DEPLOY_FAILED: health check did not pass')
print(json.dumps({'Deployment':'verified','ImageDigest':sys.argv[1],'Container':'gambit-oa-test','Health':'healthy'}, ensure_ascii=True))
HEALTH
PROD_AFTER=$(docker inspect --format '{{.Id}} {{.Image}} {{.State.StartedAt}}' gambit-oa)
[ "$PROD_BEFORE" = "$PROD_AFTER" ] || { echo 'DEPLOY_FAILED: production container metadata changed' >&2; exit 1; }
echo 'PRODUCTION_CONTAINER_UNCHANGED'
'''


def config():
    path = ROOT / '.env.remote-test.local'
    if not path.is_file():
        raise SystemExit('请先运行 scripts/setup-test-server-access.py 配置本机连接。')
    values = dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#') and '=' in line)
    if (values.get('OA_TEST_SSH_HOST'), values.get('OA_TEST_SSH_PORT'), values.get('OA_TEST_SSH_USER')) != ('49.232.4.107', '22', 'root'):
        raise SystemExit('连接目标不匹配已授权的测试服务器。')
    directory = values.get('OA_TEST_REMOTE_DIR', '')
    if not directory.startswith('/') or any(c in directory for c in '\n\r\x00'):
        raise SystemExit('请先核实并配置服务器上的绝对 OA 部署目录。')
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--digest', required=True, help='Already-pushed sha256 image digest')
    parser.add_argument('--check', action='store_true', help='Verify configuration, current image and health without deploying')
    args = parser.parse_args()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.digest):
        raise SystemExit('镜像摘要须为 sha256 加 64 位小写十六进制字符。')
    if sys.platform != 'darwin':
        raise SystemExit('请在配置了 macOS 钥匙串的本机运行。')
    directory = config()
    digest = hashlib.sha256((ROOT / 'deploy.sh').read_bytes()).hexdigest()
    command = 'bash -s -- ' + ' '.join(shlex.quote(value) for value in (directory, args.digest, 'check' if args.check else 'deploy', digest))
    env = dict(os.environ, LC_ALL='C', LANG='C', DISPLAY='codex', SSH_ASKPASS_REQUIRE='force',
               SSH_ASKPASS=str(ROOT / 'scripts/ssh-askpass-test-server.sh'))
    result = subprocess.run(['ssh','-T','-o','BatchMode=no','-o','PreferredAuthentications=password',
                             '-o','NumberOfPasswordPrompts=1','-o','StrictHostKeyChecking=yes',
                             '-o','ConnectTimeout=15','-o','ServerAliveInterval=15',
                             '-o','ServerAliveCountMax=2','-p','22','root@49.232.4.107',command],
                            input=REMOTE, text=True, env=env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
