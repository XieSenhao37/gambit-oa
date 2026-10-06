# 已知问题与技术债

## 高风险

- 管理员账号密码硬编码：`POST /admin_api/auth/v1/login` 只接受 `admin` / `<OA_ADMIN_PASSWORD: 从环境变量配置>`，没有接入真实用户体系、密码哈希、限流或审计。
- JWT 密钥硬编码且配置脱节：`backend/app/config.py` 读取 `JWT_SECRET`，但 `backend/app/utils/jwt.py` 实际使用硬编码 `<JWT_SECRET: 从环境变量配置>"”`。
- 任意有效 token 都可访问敏感接口：`@login_required` 只校验 token，不校验角色；修改用户角色、结算订单、删除桌游都没有细粒度授权。
- `/admin_api/game/v1/list` 未加 `@login_required`：桌游列表可匿名访问。
- AES 手机号密钥硬编码：`<PHONE_CRYPTO_KEY: 从环境变量配置>` 写在源码中，泄露后可解密用户手机号。
- 用户列表和订单列表返回明文手机号：后台会解密并返回 `PhoneNumber` / `User.Phone`，若后台账号或 token 泄露会暴露敏感信息。
- CORS 未收敛：`CORS(app)` 裸调用，`Config.CORS_ORIGINS` 没有接线，生产环境可能允许过宽跨域访问。

## 中风险

- 积分系统依赖 GambitServer 的 `sql/20260531_create_point_system.sql`：部署前必须先在共享 MySQL 执行该 SQL（建 `point_*` 表 + `PointConfig` 初始行），否则 `/admin_api/point/*` 与小程序积分接口会因缺表失败。积分兑换闭环还依赖 `sql/20260601_create_point_redeem_orders.sql`（新增兑换订单表与流水关联字段）。积分商品图片走 COS（`folder='point-products'`），需保证 COS 配置可用。
- 退款管理依赖 GambitServer 内部接口和共享库迁移：需先部署 `pay_orders.group_activity_participant_id`、组局表及 `approve/reject/reconcile` 契约；内部地址或 token 缺失时列表仍可读，但 OA 资金操作不可用。退款补偿和对账由 GambitServer 后台任务承担。
- 组局退款没有门店隔离或个人操作人审计：所有有效 OA 登录用户都能确认退款/标记不退款，目前仅依赖前端二次确认和服务端退款状态机。
- 手机号关键词只能精确匹配：手机号以确定性 AES 密文保存，退款列表无法安全执行手机号模糊搜索。
- 登出没有服务端吊销：`logout` 只是返回成功，旧 token 在过期前仍可使用。
- 响应格式不统一：多数接口返回 `Code/Message/Data`，`DELETE game` 返回 `code/msg`；前端类型声明使用 `Msg` 而不是 `Message`。
- 前端认证 wrapper 只看 `localStorage.token`：不会校验 token 有效性，也不检查 role。
- Umi `access.ts` 是模板逻辑：`canSeeAdmin` 不等于实际后台权限体系，容易被误用。
- 用户角色枚举不一致：后端模型/登录使用 `9999` 表示管理员，用户页表格和编辑下拉出现 `127` 管理员。
- Docker/uWSGI 可访问性需验证：`uwsgi.ini` 使用 `socket=:8080`，不是 `http-socket`；容器暴露 8080 不代表外部能直接 HTTP 访问。
- 错误格式不统一：`get_or_404` 等 Flask 默认错误不一定返回项目约定 JSON，前端错误处理可能读不到 `Message`。

## 低风险

- 后端接口中存在调试打印：用户列表、订单列表会打印请求参数。
- `frontend/src/services/typings.d.ts` 中 `BoardGame` 接口重复声明，一处是小写简版字段，一处是大写完整字段。
- 前端 `.umirc.ts` 配置 `request.dataField='data'`，但后端返回大写 `Data`，约定容易误导后续开发。
- `backend/app/utils/jwt.py` 导入了 `current_app` 但未使用；`auth.py` 导入了 `User`、`check_password_hash` 但未使用。
- `Home`、`Table`、`Access` 等模板页面未注册路由但仍保留，可能干扰新人理解。
- `BoardGame.rule_list` 在模型中存在，但列表接口没有返回。
