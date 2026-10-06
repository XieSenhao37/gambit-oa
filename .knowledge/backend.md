# 后端说明

## 架构入口

后端位于 `backend/`。入口 `run.py` 创建全局 `app = create_app()`，本地直接运行时监听 `0.0.0.0:8080`。

`app.create_app()` 位于 `backend/app/__init__.py`：

- 创建 Flask app。
- 从 `app.config.Config` 加载配置。
- 初始化 `Flask-SQLAlchemy`。
- 执行 `CORS(app)`，当前没有接入 `Config.CORS_ORIGINS`。
- 注册 `main` 和 `api_v1` 蓝图。
- 启动时尝试 `SELECT 1` 测试数据库连接。

## 路由组织

`backend/app/routes.py` 定义两个蓝图：

- `main`：基础路由，包含 `GET /health`。
- `api_v1`：总前缀 `/admin_api`。

API 模块注册：

- `/admin_api/auth/v1` -> `backend/app/api/v1/auth.py`
- `/admin_api/user/v1` -> `backend/app/api/v1/user.py`
- `/admin_api/order/v1` -> `backend/app/api/v1/order.py`
- `/admin_api/game/v1` -> `backend/app/api/v1/game.py`
- `/admin_api/catering/v1` -> `backend/app/api/v1/catering.py`
- `/admin_api/refund/v1` -> `backend/app/api/v1/refund.py`
- `/admin_api/dish/v1` -> `backend/app/api/v1/dish.py`
- `/admin_api/stats/v1` -> `backend/app/api/v1/stats.py`
- `/admin_api/wallet/v1` -> `backend/app/api/v1/wallet.py`（充值档位 CRUD，直连共享表 `wallet_recharge_tiers`）
- `/admin_api/month-card/v1` -> `backend/app/api/v1/month_card.py`（OA 手动开通/月卡订单查询）

## 认证与门店授权（2026-09-26）

- `OA_LOGIN_MODE=password`（当前默认）只接受用户指定的一组固定账号密码，后端 `security/login_mode.py` 校验。`OA_LOGIN_MODE=sms` 切回完整手机号验证码流程，两种入口互斥，不接受旧 JWT。
- 临时管理员是 OA 专用虚拟身份 `user_id=0, account_version=0`，拥有总部权限；不创建或修改小程序用户和员工授权。会话与操作审计保留 `actor_id=0`，跨服务游玩操作标识为 `OA#0`。切换模式后另一模式的会话不可继续使用。
- `security/models.py` 映射共享 `staff_accounts`、`staff_store_grants`，独立手机号登录绑定关联现有 `users.id`。普通资料修改不改变 OA 登录凭据。
- `security/pages.json` 是页面目录唯一来源。前端 `scripts/sync-pages.cjs` 在 setup/dev/build 时生成菜单及路由输入；新增页必须使用稳定 id，改标题不改 id。
- `staff_role_pages` 保存 worker/manager 对页面的覆盖规则。manager 默认允许新业务页，worker 默认仅工作台、历史订单；`scope=admin` 页永不开放给门店角色。
- 接口使用 `@login_required('page-id')`；共用只读接口可以列出多个允许页面。未归类接口由总蓝图默认拒绝。不能仅凭请求 Referer 判断页面权限。
- 每个请求重新加载员工状态、门店角色和页面权限。身份为 `users.id`，门店授权按 `(user_id, store_id, role)` 配对，不能把角色与门店分别取合集。
- `X-Store-ID` 与 body/query 门店值必须一致。ORM 门店表通过 `security/scope.py` 统一限制，原生 SQL 必须显式加入门店条件。代理退款、出餐、结算前检查真实目标所属店。
- 全品牌配置允许店长操作，页面明确提示影响全品牌。全品牌余额、邀请汇总等无法可靠归店的统计，对非总部返回 null 并注明不可用，不能补成 0。
- 会话为数据库中 SHA256 摘要索引的随机 token（15 天，固定有效期）。账号版本变更、停用及注销撤销登录；旧 JWT 不被接受。
- 验证码由安全随机数生成，HMAC 保存，5 分钟/最多 5 次错误/一次性消费。手机号、IP、全局限流存数据库，多 worker 共用。只对有效员工发短信；验证时再次校验资格。
- 腾讯 SMS 适配器在 `security/sms.py`。短信模式下配置缺失时关闭登录且返回明确提示，不记录验证码、不返回给前端、不使用测试万能码；临时密码模式不依赖短信配置并拒绝发码请求。
- 授权修改记录前后快照；业务写请求记录操作者、路径、必要金额/备注、开始及结果。不记录登录凭据和完整请求体。
- `security/scope.py` 的 `global_reference_check` 仅用于跨店唯一性/引用检查，不能用于返回跨店流水。

## 模型

模型定义在 `backend/app/models.py`，映射与小程序后端共用的核心业务表：

- `User` -> `users`
- `PlayOrder` -> `play_orders`
- `BoardGame` -> `board_games`
- `BoardGameStoreInventory` -> `board_game_store_inventories`
- `PayOrder` -> `pay_orders`
- `GroupActivity` -> `group_activities`
- `GroupActivityParticipant` -> `group_activity_participants`
- 统计只读补充模型：`CouponPromotion`、`CouponRecord`、`ReferralRecord`、`MonthCardOrder`、`WalletAccount`、`WalletRechargeOrder`、`WalletTransaction` 等共享业务表；`MonthCardOrder` 同时被 OA 手动开通月卡接口写入来源、操作人、外部凭证、门店、备注和生效时间。
- 餐品管理模型：`DishLibraryItem` 映射全局餐品信息库，`DishStoreItem` 映射门店菜单项，旧 `Dish` 继续作为小程序菜单和下单兼容表。

`User.play_orders` 通过 `User.open_id == PlayOrder.open_id` 关联，并过滤 `PlayOrder.deleted_at is null`。这不是普通外键关系，而是基于小程序用户 `open_id` 的业务关联。

## 手机号加解密

`backend/app/utils/crypto.py` 使用 AES-CBC：

- 密钥：`<PHONE_CRYPTO_KEY: 从环境变量配置>`
- 解密：输入是 base64，前 16 字节作为 IV，其余作为密文。
- 加密：当前使用全零 IV，以便按手机号精确查询。
- padding 使用零字节填充/去除。

该逻辑必须和 Go 小程序后端保持一致。用户列表和订单列表会解密手机号并返回明文字段。

## 响应格式

多数接口返回：

```json
{
  "Code": 0,
  "Message": "success",
  "Data": {}
}
```

分页接口的 `Data` 通常为：

```json
{
  "Total": 100,
  "CurrentPage": 1,
  "PageSize": 10,
  "Items": []
}
```

已发现不一致：

- 前端 `API.Response` 类型声明为 `Code`、`Msg`、`Data`，但后端多数返回 `Message`。
- 前端 `.umirc.ts` 配置 `request.dataField = 'data'`，但后端字段是大写 `Data`；实际页面代码仍按完整响应 `response.Code`/`response.Data` 使用。

## 模块注意事项

- `/admin_api/order/v1/list` 仅提供历史游玩订单读取；旧 OA 直写结算接口已移除，结算统一走工作台代理与 GambitServer 事务。
- `/admin_api/catering/v1/history` 按门店只读查询全部餐饮订单，并通过每个 `catering_id` 最大支付单 ID 关联最新未删除支付流水；不会改变制作台 `/list` 的已支付口径。
- 历史餐饮查询支持制作状态、支付状态（含无支付流水）、关键字和创建时间筛选，返回餐品、桌台、用户及支付详情。
- 多个接口直接使用 `get_or_404`，错误响应会走 Flask 默认 404 格式，不一定符合统一 JSON 格式。
- CORS 当前是裸 `CORS(app)`，即便 `Config.CORS_ORIGINS = ['*']`，也没有显式按配置收敛来源。

## 退款管理

`backend/app/api/v1/refund.py` 读取共享库 `refund_requests`，但不直接改支付或退款资金状态：

- `GET /admin_api/refund/v1/list` 支持 `play`、`catering`、`organization`，直接读取共享数据库；退款补偿和微信状态对账由 GambitServer 每分钟后台任务处理，避免 OA 列表请求超过前端超时。
- 组局退款的 `refund_requests.order_id` 指向 `group_activity_participants.id`。OA 批量加载报名、活动、门店和用户关系，生成活动标题、门店、开始时间、报名状态快照。
- 关键词支持 OpenID、昵称、活动标题；手机号使用现有确定性 AES 加密后做精确密文匹配。
- 审核通过和失败重试都代理 GambitServer `approve`；不退款代理 `reject`。两者均使用 `X-GAMBIT-INTERNAL-TOKEN`。
- OA 批量退款仍逐笔调用现有 approve 代理，不新增批量资金状态旁路；服务端单笔幂等规则保持不变。
- 所有已登录 OA 用户可操作，不做门店隔离或个人操作人审计；前端保留二次确认。

## 桌游管理

`backend/app/api/v1/game.py` 按“全局资料库 + 门店库存库”拆分：

- `board_games` 是全局桌游信息库，保存名称、封面、评分、人数、难度、时长、分类、简介等资料。
- `board_game_store_inventories` 是门店库存库，保存 `store_id`、`board_game_id` 和 `count`。
- `storage_location` 字段已从 `board_games` 和 `board_game_store_inventories` 清理，OA 不再展示或写入。
- 全局桌游资料的封面图和详情图通过 multipart 文件上传到 COS，保存时写回 `cover_url` 和 `picture_list`。

接口：

- `GET /admin_api/game/v1/library/list`：全局桌游信息库分页列表。
- `GET /admin_api/game/v1/library/{id}`：全局桌游详情。
- `POST /admin_api/game/v1/library`：新增全局桌游资料。
- `PUT /admin_api/game/v1/library/{id}`：编辑全局桌游资料，影响所有门店展示。
- `DELETE /admin_api/game/v1/library/{id}`：删除全局桌游资料；若仍存在门店库存则拒绝。
- `GET /admin_api/game/v1/inventory/list`：当前门店库存列表。
- `POST /admin_api/game/v1/inventory`：从信息库添加桌游到当前门店库存。
- `PUT /admin_api/game/v1/inventory/{id}`：更新当前门店某桌游数量。
- `DELETE /admin_api/game/v1/inventory/{id}`：从当前门店库存移除桌游。
- `GET /admin_api/game/v1/list`：兼容旧路径，等价于当前门店库存列表。

## 餐品管理

`backend/app/api/v1/dish.py` 按“全局餐品信息库 + 门店菜单库”拆分，并保留旧路径兼容：

- `dish_library_items` 是全局餐品信息库，保存名称、默认价格、图片、分类、规格选项、描述和标签。
- `dish_store_items` 是门店菜单库，保存 `store_id`、`dish_library_item_id`、门店售价、上下架和排序；分类和规格选项不在门店添加流程里重复配置。
- `dishes` 继续保留，新增 `library_item_id`；OA 新增/编辑/移除门店菜单时会同步维护对应 `dishes` 行，保证小程序当前菜单接口和下单校验不被一次性破坏。
- 分类 `dish_categories` 和规格 `options` 为全局元数据，不再带 `store_id`。
- 全局餐品图片通过 multipart 文件上传到 COS。

接口：

- `GET /admin_api/dish/v1/list`：当前门店菜单列表，读取 `X-Store-ID`，返回门店菜单项并附带分类/选项元数据用于展示。
- `POST /admin_api/dish/v1/create`：兼容旧新增路径，会同时创建全局餐品资料和当前门店菜单项。
- `GET /admin_api/dish/v1/library/list`：全局餐品信息库分页列表。
- `GET /admin_api/dish/v1/library/{id}`：全局餐品详情。
- `POST /admin_api/dish/v1/library`：新增全局餐品资料。
- `PUT /admin_api/dish/v1/library/{id}`：编辑全局餐品资料，并同步所有引用门店的旧 `dishes` 基础字段。
- `DELETE /admin_api/dish/v1/library/{id}`：删除全局餐品资料；若仍存在门店菜单引用则拒绝。
- `POST /admin_api/dish/v1/store-items`：从信息库添加餐品到当前门店菜单，并创建兼容 `dishes` 行。
- `PUT /admin_api/dish/v1/store-items/{id}`：编辑当前门店菜单项的售价、上下架和排序。
- `DELETE /admin_api/dish/v1/store-items/{id}`：从当前门店菜单软删除，并同步软删除兼容 `dishes` 行。
- `PATCH /admin_api/dish/v1/store-items/{id}/status`：当前门店菜单项上下架；旧 `/{id}/status` 路径兼容同一逻辑。

## 月卡运营

`backend/app/api/v1/month_card.py` 提供 OA 手动开通/续期月卡能力，用于美团核销、寄存赠送、手动调整等不经过小程序支付的场景：

- `POST /admin_api/month-card/v1/manual-open`：按 `UserId` 或 `OpenId` 锁定用户，校验来源和凭证，创建已支付 `month_card_orders`，并把 `users.month_card_expire` 从当前有效期或当前时间顺延指定月数。
- `GET /admin_api/month-card/v1/orders`：分页查询月卡订单，支持按用户、来源、外部凭证和日期筛选，方便对账。
- 前端金额按元录入，提交到后端时统一转为分；接口入参 `Amount` 单位为分。
- `source + external_no` 在接口层做重复核销检查；数据库只加普通索引，不加唯一约束以兼容历史空凭证。
- 月卡权益本身仍全局可用，`store_id` 仅记录 OA 当前门店用于运营归因。

## 运营统计

`backend/app/api/v1/stats.py` 提供 OA 运营分析接口，统一使用 `StartDate`、`EndDate`、`Granularity=day|week|month` 查询参数。门店型指标读取 `X-Store-ID`/`StoreID`，默认门店为 1；月卡、储值充值、积分账户余额等全局产品不会强行按门店归属。

当前接口：

- `GET /admin_api/stats/v1/ops/overview`：经营总览，包含桌游/饮品营收、订单数、新增用户、活跃用户、储值充值和积分消耗。
- `GET /admin_api/stats/v1/catering/overview`：饮品统计，已按当前门店过滤。
- `GET /admin_api/stats/v1/play/overview`：桌游游玩统计，包含营收、订单、时长、计费模式和支付方式。
- `GET /admin_api/stats/v1/user/overview`：用户增长、付费新客、复购/老客和注册来源门店。
- `GET /admin_api/stats/v1/coupon/overview`：优惠券/活动领取、核销、核销率、带动订单、带动金额和优惠金额。
- `GET /admin_api/stats/v1/referral/overview`：老带新绑定、新人券发放、首单完成、邀请人奖励和分享渠道排行。
- `GET /admin_api/stats/v1/membership/overview`：月卡收入、开通数、有效月卡用户、月卡用户消费行为，以及按来源拆分的小程序微信/美团/寄存赠送/手动调整统计。
- `GET /admin_api/stats/v1/wallet/overview`：储值充值、赠送、消费、余额沉淀和充值档位分布。
- `GET /admin_api/stats/v1/point/overview`：积分发放、消耗、余额沉淀、兑换订单和热门兑换商品。
- `GET /admin_api/stats/v1/user/insights`：用户洞察列表，按消费金额聚合游玩、饮品、储值、积分、用券和月卡标签。

统计口径说明：

- 金额字段在数据库中为分，stats API 统一返回元。
- 饮品统计以已支付 `caterings` + `pay_orders` 为准，按 `caterings.store_id` 过滤。
- 桌游统计以已支付 `play_orders` + `pay_orders` 为准，按 `play_orders.store_id` 过滤。
- 优惠券“带动订单”依赖 `pay_orders.coupon_id`，只统计已支付订单。
- 老带新当前基于 `referral_records` 状态机，只能分析绑定/发券/首单/奖励等结果口径。
- 小程序暂无统一埋点，因此曝光、点击、支付放弃、入群转化等过程型漏斗暂不在第一版统计中。

## 游玩工作台代理

`backend/app/api/v1/order.py` 的工作台接口不直接写共享数据库：

- 使用 `GAMBIT_SERVER_BASE_URL` 与 `GAMBIT_INTERNAL_TOKEN` 调用 GambitServer 内部游玩接口。
- 查询和写操作都透传当前 `X-Store-ID`。
- 手动离场接收前端元金额，使用 Decimal 严格校验最多两位小数并换算为整数分。
- 手动、快速离场均附带 OA 会话中的操作人标识；GambitServer 负责行锁、防重复支付和支付完成回调。
- GambitServer 的业务错误文案作为 OA `Code=1` 响应透传，前端可直接提示。


2026-09-27：旧的测试手机号免验证码入口已移除，`OA_ENV` / `OA_TEST_LOGIN_*` 不再控制登录。当前固定账号模式及短信切回步骤见 `runtime.md`。
