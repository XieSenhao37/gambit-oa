"""Settlement is exclusively manual. Do not start financial workers on server startup."""

# 桌游图片先同步上传 COS；避免默认 30 秒杀掉仍在保存的 worker。
# 前端上传等待 120 秒，worker 留出响应与清理余量。
timeout = 150

# 浏览器预连接／未完成请求不能独占同步 worker，拖住登录和静态资源。
# gthread 先用 selector 等待连接可读，再交给线程；有限线程也为慢请求留出并发余量。
worker_class = 'gthread'
threads = 8
keepalive = 5
