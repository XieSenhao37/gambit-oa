#!/bin/bash
set -e

IMAGE="ccr.ccs.tencentyun.com/gambit/gambit_oa:latest"

# 分开构建与推送，避开当前 BuildKit 推送时的令牌认证异常。
docker buildx build --platform linux/amd64 -t "$IMAGE" --load .
docker push "$IMAGE"

echo ">>> 构建并推送完成：$IMAGE"
