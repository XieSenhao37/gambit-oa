# 集成说明

## 前后端联动

前端所有业务服务都请求 `/admin_api/**`：

- 登录：`/admin_api/auth/v1/login`
- 订单：`/admin_api/order/v1/**`
- 用户：`/admin_api/user/v1/**`
- 桌游：`/admin_api/game/v1/**`

开发环境由 `frontend/.umirc.ts` 代理到：

```text
http://127.0.0.1:8080
```

后端在本地开发时由 `backend/run.py` 监听：

```text
0.0.0.0:8080
```

因此本地联调路径是：

```text
浏览器 -> Umi dev server -> /admin_api proxy -> Flask :8080
```

生产环境需要网关或静态站点服务器把 `/admin_api` 转发到 Flask 服务；源码中没有发现独立的生产域名配置。

## 登录 token 流程

1. 登录页提交 `username`、`password` 到 `/admin_api/auth/v1/login`。
2. 后端仅校验硬编码账号 `admin` / `<OA_ADMIN_PASSWORD: 从环境变量配置>`。
3. 后端签发 JWT，payload 包含 `user_id=1`、`role=9999`、`exp`。
4. 前端保存：
   - `localStorage.token`
   - `localStorage.role`
5. `src/app.ts` 请求拦截器为后续请求注入：

```text
Authorization: Bearer <token>
```

6. 后端 `@login_required` 只验证 token 是否可解码且未过期，不做角色鉴权。
7. HTTP 401 时前端清除本地 token/role 并跳转 `/login`。

登出只是前端清理本地状态加后端语义接口，服务端没有 token 黑名单或会话吊销。

## 前端路由与后端 API 路径区别

前端页面路径：

- `/login`
- `/orders`
- `/games`
- `/users`

后端 API 路径：

- `/admin_api/auth/v1/**`
- `/admin_api/order/v1/**`
- `/admin_api/game/v1/**`
- `/admin_api/user/v1/**`

健康检查路径是后端根路径：

- `/health`

部署时不要把前端路由和 API 路由混淆。前端路由应回退到前端入口，`/admin_api` 和 `/health` 应转发到后端。

## 手机号加解密

手机号存储在 `users.phone_number`，不是明文。后台使用 `backend/app/utils/crypto.py`：

- AES-CBC
- key：`<PHONE_CRYPTO_KEY: 从环境变量配置>`
- 加密结果为 base64，格式为 `IV + ciphertext`
- 查询手机号时，后台把输入明文手机号加密后与库值比较。
- 返回用户列表/订单列表时，后台会解密并返回明文手机号。

该逻辑需要和小程序 Go 后端保持一致。特别要注意：

- 当前 Python 加密用于查询时使用全零 IV，确保同一个手机号得到同一密文。
- 解密时读取密文前 16 字节作为 IV，因此需要兼容 Go 后端写入格式。
- 一旦改密钥、填充方式或 IV 策略，历史手机号查询和解密都会受影响。

## 与 GambitServer 的关系

`gambit-oa` 管理后台和小程序后端 `GambitServer` 共用核心业务数据库表：

- `users`
- `play_orders`
- `board_games`
- `pay_orders`
- `refund_requests`
- `group_activities`
- `group_activity_participants`
- `stores`

后台不是独立业务域，它直接管理小程序产生的数据。例如：

- 用户列表读取小程序用户，并可修改 `users.role`。
- 订单中心只读查询小程序游玩与餐饮订单。
- 桌游列表读取库存/内容数据，并可软删除。
- 手机号加解密必须保持和 Go 后端一致。

因此跨项目联动时要优先确认：

- Go 后端是否也使用同一字段含义。
- 金额单位是否一致。
- 支付类型枚举是否一致。
- 软删除字段是否被两端共同过滤。
- 管理后台写入是否会破坏小程序端假设。

游玩工作台采用服务端收口模式：

1. OA 前端只请求 `/admin_api/order/v1/workbench*`，并由全局请求拦截器附带当前门店。
2. OA 后端通过 `X-GAMBIT-INTERNAL-TOKEN` 调用 `/microapp_api/admin/play/v1/workbench*`。
3. GambitServer 统一计算当前/离场参考时间下的理论金额，读取支付成功金额并聚合近 5 分钟批次。
4. 手动和快速离场由 GambitServer 锁定 `play_orders`，拒绝跨门店、已结算或已有待支付流水的请求，再创建线下支付完成记录。
5. OA 原订单管理直写接口已移除；订单中心只读，手动/快速离场只能从工作台代理到 GambitServer。

历史餐饮订单使用独立 `/admin_api/catering/v1/history` 查询全部支付状态，并按当前 `X-Store-ID` 隔离门店；制作台 `/list` 仍只读取已支付订单。两个页面都不提供写操作。

## 组局意向金退款链路

1. GambitServer 在组局意向金支付成功后创建 `refund_requests`，`order_type=organization`，并通过 `pay_order_id` 精确关联支付单。
2. GambitServer 后台任务每分钟补偿已取消活动遗留的待退款任务，并主动对账陈旧 `refunding`；内部 `/microapp_api/admin/refund/v1/reconcile` 保留给运维手工触发。
3. OA `GET /admin_api/refund/v1/list` 直接从共享库关联报名、活动、门店和用户，仅用于列表展示与检索，不直接更改 `pay_orders` 或 `refund_requests` 的资金状态。
4. 单笔“退款”和 `refund_failed` 重试调用 GambitServer `approve`；“不退款”调用 `reject`。批量退款只允许勾选已报名、待到店退款的组局记录，并以最多 3 个并发逐笔复用 approve，不存在批量资金旁路。
5. 微信终态回调由 GambitServer 结合 `queryrefund` 交易证据和本地支付/退款数据严格校验后落库；OA 页面每 10 秒刷新共享库状态，到账后自动显示“已退款”。
6. 当前不做门店隔离或 OA 个人操作人审计，所有有效 OA 登录用户都可操作；风险控制依赖 UI 二次确认和 GambitServer 的状态机/幂等校验。

## 部署路径建议

源码中明确的路径约定是：

- 管理后台前端：SPA 页面路径，如 `/orders`。
- 管理后台后端 API：统一挂在 `/admin_api` 下。
- 后端健康检查：`/health`。
- 小程序后端：不在本仓库内，实际域名与路径需到 `GambitServer` 和部署配置中核对。

建议网关规则：

- `/admin_api/*` -> `gambit-oa/backend`
- `/health` -> `gambit-oa/backend`
- 其他管理后台页面路径 -> `gambit-oa/frontend` 静态资源/SPA fallback


## 门店积分赛（2026-09-19）

新增 `/events` 页面与 `/admin_api/event/v1` API。统一配置项目、按项目配置卡组；赛事列表按 ID 聚合，详情记录签到玩家、卡牌 ID 快照及名次/卡组。看板按项目、门店、月份筛选，MAU 为参赛人次，连续 UU 为相邻月去重交集；提供人数排名、活跃玩家、待召回名单、去重人数、新玩家、回归率、人均场次和卡组分布。空赛事不计入场次，月份按首次成功签到时间归属。

积分入账只由 Go 后端完成；OA 管理配置与比赛结果，不直接增加积分。依赖 GambitServer/sql/20260919_create_store_events.sql。上线前需要业务库迁移和测试云联调，当前仅隔离 MySQL 测试通过。
