#!/bin/bash
set -e

# Local credentials are excluded from Git and the Docker build context.
DEPLOY_CONFIG="${DEPLOY_CONFIG:-$(dirname "$0")/.env.deploy.local}"
if [ -f "$DEPLOY_CONFIG" ]; then
  set -a
  . "$DEPLOY_CONFIG"
  set +a
fi
: "${PHONE_CRYPTO_KEY:?请配置原有手机号加密密钥 PHONE_CRYPTO_KEY}"
if [ "${OA_LOGIN_MODE:-password}" = "password" ]; then
  : "${OA_ADMIN_PASSWORD:?请配置 OA_ADMIN_PASSWORD}"
elif [ "$OA_LOGIN_MODE" = "sms" ]; then
  : "${OA_AUTH_SECRET:?请配置 OA_AUTH_SECRET}"
  [ "${#OA_AUTH_SECRET}" -ge 32 ] || { echo 'OA_AUTH_SECRET 至少需要32个字符' >&2; exit 1; }
  : "${TENCENT_SMS_SECRET_ID:?请配置 TENCENT_SMS_SECRET_ID}"
  : "${TENCENT_SMS_SECRET_KEY:?请配置 TENCENT_SMS_SECRET_KEY}"
  : "${TENCENT_SMS_APP_ID:?请配置 TENCENT_SMS_APP_ID}"
  : "${TENCENT_SMS_SIGN_NAME:?请配置 TENCENT_SMS_SIGN_NAME}"
  : "${TENCENT_SMS_TEMPLATE_ID:?请配置 TENCENT_SMS_TEMPLATE_ID}"
else
  echo 'OA_LOGIN_MODE 仅支持 password 或 sms' >&2
  exit 1
fi

IMAGE="${DEPLOY_IMAGE:-ccr.ccs.tencentyun.com/gambit/gambit_oa:latest}"
DEPLOY_ENV="${1:-${DEPLOY_ENV:-test}}"
CONTAINER_PORT="8080"
: "${JWT_SECRET:?请配置 JWT_SECRET}"
SECRET_KEY="${SECRET_KEY:-gambit-oa-flask-secret}"
: "${GAMBIT_INTERNAL_TOKEN:?请配置 GAMBIT_INTERNAL_TOKEN}"

case "$DEPLOY_ENV" in
  test|testing)
    DEPLOY_ENV="test"
    DEFAULT_STORE_SETTLEMENT_ENABLED="true"
    DB_HOST="gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com:21085"
    DEFAULT_GAMBIT_SERVER_BASE_URL="https://test-golang-137415-10-1301993689.sh.run.tcloudbase.com"
    DEFAULT_CONTAINER="gambit-oa-test"
    DEFAULT_HOST_PORT="18080"
    ;;
  prod|production)
    DEPLOY_ENV="prod"
    DEFAULT_STORE_SETTLEMENT_ENABLED="false"
    DB_HOST="sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com:22120"
    DEFAULT_GAMBIT_SERVER_BASE_URL="https://golang-mfne-137415-10-1301993689.sh.run.tcloudbase.com"
    DEFAULT_CONTAINER="gambit-oa"
    DEFAULT_HOST_PORT="8080"
    ;;
  *)
    echo "❌ 未知部署环境：$DEPLOY_ENV"
    echo "用法：./deploy.sh test | ./deploy.sh prod"
    echo "也可以：DEPLOY_ENV=test ./deploy.sh"
    exit 1
    ;;
esac

CONTAINER="${CONTAINER:-$DEFAULT_CONTAINER}"
HOST_PORT="${HOST_PORT:-$DEFAULT_HOST_PORT}"
STORE_SETTLEMENT_ENABLED="${STORE_SETTLEMENT_ENABLED:-$DEFAULT_STORE_SETTLEMENT_ENABLED}"

GAMBIT_SERVER_BASE_URL="${GAMBIT_SERVER_BASE_URL:-$DEFAULT_GAMBIT_SERVER_BASE_URL}"

DB_USER="${DB_USER:-root}"
if [ -z "${DATABASE_URL:-}" ]; then
  : "${DB_PASSWORD_ENCODED:?请配置 DB_PASSWORD_ENCODED 或 DATABASE_URL}"
fi
DB_NAME="${DB_NAME:-gambit}"
DATABASE_URL="${DATABASE_URL:-mysql+pymysql://${DB_USER}:${DB_PASSWORD_ENCODED}@${DB_HOST}/${DB_NAME}}"

echo ">>> 部署环境：$DEPLOY_ENV"
echo ">>> 容器名：$CONTAINER"
echo ">>> 宿主机端口：$HOST_PORT -> 容器端口：$CONTAINER_PORT"
echo ">>> 数据库地址：$DB_HOST/$DB_NAME"
echo ">>> GambitServer 地址：$GAMBIT_SERVER_BASE_URL"
echo ">>> 门店结算开关：$STORE_SETTLEMENT_ENABLED"

echo ">>> 拉取最新镜像：$IMAGE"
docker pull "$IMAGE"

echo ">>> 停止并删除旧容器：$CONTAINER"
docker rm -f "$CONTAINER" 2>/dev/null || true

echo ">>> 启动新容器：http://<服务器公网IP>:$HOST_PORT"
docker run -d --name "$CONTAINER" \
  --restart unless-stopped \
  -p "$HOST_PORT:$CONTAINER_PORT" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e JWT_SECRET="$JWT_SECRET" \
  -e SECRET_KEY="$SECRET_KEY" \
  -e GAMBIT_SERVER_BASE_URL="$GAMBIT_SERVER_BASE_URL" \
  -e GAMBIT_INTERNAL_TOKEN="$GAMBIT_INTERNAL_TOKEN" \
  -e PHONE_CRYPTO_KEY="$PHONE_CRYPTO_KEY" \
  -e OA_ADMIN_PASSWORD="${OA_ADMIN_PASSWORD:-}" \
  -e COS_SECRET_ID="${COS_SECRET_ID:-}" \
  -e COS_SECRET_KEY="${COS_SECRET_KEY:-}" \
  -e OA_LOGIN_MODE="${OA_LOGIN_MODE:-password}" \
  -e OA_AUTH_SECRET="${OA_AUTH_SECRET:-}" \
  -e TENCENT_SMS_SECRET_ID="${TENCENT_SMS_SECRET_ID:-}" \
  -e TENCENT_SMS_SECRET_KEY="${TENCENT_SMS_SECRET_KEY:-}" \
  -e TENCENT_SMS_APP_ID="${TENCENT_SMS_APP_ID:-}" \
  -e TENCENT_SMS_SIGN_NAME="${TENCENT_SMS_SIGN_NAME:-}" \
  -e TENCENT_SMS_TEMPLATE_ID="${TENCENT_SMS_TEMPLATE_ID:-}" \
  -e TENCENT_SMS_REGION="${TENCENT_SMS_REGION:-ap-guangzhou}" \
  -e STORE_SETTLEMENT_ENABLED="$STORE_SETTLEMENT_ENABLED" \
  "$IMAGE"

echo ">>> 部署完成！"
docker ps --filter name="$CONTAINER"
