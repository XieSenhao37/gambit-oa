"""Settlement is exclusively manual. Do not start financial workers on server startup."""

# 桌游图片先同步上传 COS；避免默认 30 秒杀掉仍在保存的 worker。
# 前端上传等待 120 秒，worker 留出响应与清理余量。
timeout = 150
