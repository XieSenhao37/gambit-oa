# 数据模型

模型定义在 `backend/app/models.py`，映射到与小程序后端 `GambitServer` 共用的业务数据库。修改表结构、字段语义、金额单位、手机号加密方式前，必须同步核对 Go 后端。

## users

模型：`User`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 用户表 ID，自增。 |
| `open_id` | String(60), index | 小程序 `open_id`，也是与订单关联的业务用户标识。 |
| `user_type` | Integer | 用户类型，当前注释为 `0-微信小程序用户`。 |
| `role` | Integer | 用户身份，`0-普通用户`、`1-店员`、`2-兼职`、`126-管理员`、`127-超级管理员`。 |
| `nick_name` | String(60) | 昵称。 |
| `avatar` | String(255) | 头像。 |
| `gender` | Integer | 性别，`0-未知`、`1-男性`、`2-女性`。 |
| `phone_number` | String(50) | 加密手机号。后台列表会解密返回明文。 |
| `month_card_id` | Integer | 月卡 ID。 |
| `partner_id` | Integer | 搭子 ID。 |
| `month_card_expire` | DateTime | 月卡过期时间。 |
| `created_at` | DateTime | 创建时间。 |
| `updated_at` | DateTime | 更新时间。 |
| `deleted_at` | DateTime | 删除时间，非空表示软删除。 |
| `birthday` | DateTime | 生日。 |
| `phone_number_change_time` | DateTime | 下次可修改手机号时间。 |

关系：

- `User.play_orders` 通过 `User.open_id == PlayOrder.open_id` 关联，并过滤 `PlayOrder.deleted_at is null`。

## play_orders

模型：`PlayOrder`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 游玩订单 ID，自增。 |
| `created_at` | DateTime | 创建时间。 |
| `updated_at` | DateTime | 更新时间。 |
| `deleted_at` | DateTime | 删除时间，非空表示软删除。 |
| `open_id` | String(60), not null | 用户 `open_id`。 |
| `in_time` | DateTime, not null | 入场时间。 |
| `out_time` | DateTime | 出场时间。 |
| `play_time` | Integer | 游玩时长，单位小时。 |
| `amount` | Integer | 订单金额，模型注释为单位分。 |
| `settle_status` | Integer | 结算状态，`0-待结算`、`1-已结算`。 |
| `comment` | Text | 备注。 |
| `unit_price` | Integer | 游玩单价，单位分。 |

注意：

- 订单列表用 `PlayOrder.open_id` 外连 `User.open_id` 补充用户昵称和手机号。
- 线下结算接口将传入 `Amount` 乘以 100 后写入 `play_orders.amount`。

## board_games

模型：`BoardGame`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 桌游 ID，自增。 |
| `name` | String(255), not null | 名称。 |
| `gstone_score` | Numeric(3,1), not null | 集石评分。 |
| `gstone_rank` | Integer, not null | 集石排名。 |
| `supported_players` | JSON, not null | 支持人数列表。 |
| `recommended_players` | JSON, not null | 推荐人数列表。 |
| `cover_url` | String(500), not null | 封面图 URL。 |
| `complexity` | Integer, not null | 上手难度，1-10 级。 |
| `play_time` | Integer, not null | 人均时长，单位分钟。 |
| `setup_time` | String(50), not null | 设置时长。 |
| `language_level` | String(50), not null | 语言要求。 |
| `description` | Text, not null | 游戏简介。 |
| `picture_list` | JSON | 图片列表。 |
| `designer` | JSON, not null | 设计师列表。 |
| `publisher` | JSON, not null | 出版商列表。 |
| `publish_language` | JSON, not null | 出版语言列表。 |
| `publish_year` | SmallInteger, not null | 出版年份。 |
| `categories` | JSON, not null | 游戏类别列表。 |
| `modes` | JSON, not null | 游戏模式列表。 |
| `mechanisms` | JSON | 游戏机制列表。 |
| `themes` | JSON | 游戏主题列表。 |
| `table_requirement` | String(50) | 桌面要求。 |
| `portability` | String(50) | 便携程度。 |
| `suitable_age` | String(50) | 适合年龄。 |
| `rule_list` | JSON | 规则信息列表。当前列表接口没有返回该字段。 |
| `count` | Integer, not null | 店内数量，默认 1。 |
| `storage_location` | String(255) | 存放位置。 |
| `created_at` | DateTime, not null | 创建时间，默认 `datetime.utcnow`。 |
| `updated_at` | DateTime, not null | 修改时间，默认并自动更新为 `datetime.utcnow`。 |
| `deleted_at` | DateTime | 删除时间，非空表示软删除。 |

## pay_orders

模型：`PayOrder`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 支付订单 ID，自增。 |
| `created_at` | DateTime | 创建时间。 |
| `updated_at` | DateTime | 更新时间。 |
| `deleted_at` | DateTime | 删除时间，非空表示软删除。 |
| `open_id` | String(60), not null | 用户 `open_id`。 |
| `play_order_id` | Integer FK | 游玩订单 ID，外键到 `play_orders.id`。 |
| `month_card_order_id` | Integer | 月卡订单 ID。 |
| `group_activity_participant_id` | Integer | 组局报名记录 ID，关联 `group_activity_participants.id`。 |
| `prepay_id` | String(255) | 预支付订单 ID。 |
| `pay_id` | String(255) | 支付订单 ID。 |
| `amount` | Integer, not null | 支付金额，模型注释为单位分。 |
| `refund_amount` | Integer | 退款金额，单位分。 |
| `pay_status` | Integer | 支付状态，`0-待支付`、`1-已支付`、`2-已关闭`、`3-已退款`。 |
| `pay_type` | Integer | 支付类型，模型注释为 `0-游玩支付`、`1-月卡支付`、`2-其他支付`。 |
| `description` | Text | 支付描述信息。 |
| `expire_time` | DateTime | 订单过期时间。 |
| `pay_end_time` | DateTime | 支付完成时间。 |

注意：

- 线下结算会新增 `PayOrder`，写入 `pay_status=1`、`pay_type=1`。
- `pay_type=1` 在模型注释中是月卡支付，但结算代码注释为线下支付，需要确认真实枚举来源。
- `PayOrder.amount` 在线下结算中直接使用前端传入 `Amount`，没有像 `PlayOrder.amount` 一样乘以 100。

## group_activities

模型：`GroupActivity`。OA 为组局意向金退款只读映射活动主数据，核心字段包括 `id`、`store_id`、`title`、`start_time`、`intent_deposit_enabled`、`intent_deposit_amount`、`status` 及软删除/时间字段。

关系：

- `GroupActivity.store` 关联 `stores.id`，用于退款列表展示门店名称。
- `GroupActivity.participants` 关联 `group_activity_participants.activity_id`。

## group_activity_participants

模型：`GroupActivityParticipant`。组局报名记录。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 报名记录 ID，也是 organization 退款的 `refund_requests.order_id`。 |
| `activity_id` | Integer | 关联 `group_activities.id`。 |
| `open_id` | String(60) | 报名用户 OpenID。 |
| `status` | SmallInteger | `0-待支付`、`1-已报名`、`2-已取消`。 |
| `pay_order_id` | Integer | 报名支付订单。 |
| `wallet_recharge_order_id` | Integer | 历史/兼容的意向金储值订单关联。 |
| `registered_at` / `cancelled_at` | DateTime | 报名成功/取消时间。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳与软删除。 |

关系：`activity` 关联活动；`user` 按 `open_id` 只读关联 `users`，供 OA 返回昵称和解密手机号。

## refund_requests

组局意向金支付成功后由 GambitServer 自动创建：`order_type='organization'`、`order_id=group_activity_participants.id`、`pay_order_id` 精确关联支付单、初始 `status='pending_review'`。OA 只读该表并通过 GambitServer 内部接口执行审核、退款和对账，不直接写资金状态。

## wallet_recharge_tiers

模型：`WalletRechargeTier`（与 GambitServer 的 `model.WalletRechargeTier` 共用同一张表）

用途：储值充值档位配置（充多少送多少）。OA 维护，小程序通过 GambitServer `GET /wallet/v1/recharge/tiers` 读取展示，下单时由 GambitServer 按金额匹配计算赠送额。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 档位 ID，自增。 |
| `amount` | Integer, not null | 充值金额，单位分。 |
| `bonus_amount` | Integer, not null, default 0 | 赠送金额，单位分；`0` 表示无赠送。 |
| `label` | String(64) | 档位展示文案，可空。 |
| `sort` | Integer, not null, default 0 | 排序，越小越靠前。 |
| `enabled` | SmallInteger, not null, default 1 | `0` 停用，`1` 启用。 |
| `created_at` | DateTime | 创建时间。 |
| `updated_at` | DateTime | 更新时间。 |
| `deleted_at` | DateTime | 删除时间，非空表示软删除。 |

## configs

模型：`Config`（与 GambitServer 的 `model.Config` 共用同一张表）

用途：通用 JSON 配置。积分模块使用 `config_key='PointConfig'`，`config_value` 形如 `{"EarnThresholdAmount":1000,"EarnPoints":1,"MaxWithdrawPerTime":0}`（消费门槛单位分）。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 配置 ID。 |
| `config_key` | String(30), unique | 配置键。 |
| `config_value` | JSON, not null | 配置值。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳。 |

## 积分系统（与 GambitServer 共用表）

积分系统的表由 GambitServer `sql/20260531_create_point_system.sql` 创建，OA 通过 SQLAlchemy 模型读写。积分为整数（非分），`OriginalPrice`、`EarnThresholdAmount` 为分。

### point_product_categories

模型：`PointProductCategory`。一级分类。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 分类 ID。 |
| `name` | String(60), not null | 分类名称。 |
| `sort` | Integer, default 0 | 排序，越小越靠前。 |
| `status` | SmallInteger, default 1 | `0` 停用，`1` 启用。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳。 |

### point_products

模型：`PointProduct`。积分商城商品。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 商品 ID。 |
| `name` | String(120), not null | 商品名称。 |
| `category_id` | Integer | 关联 `point_product_categories.id`，可空。 |
| `description` | String(255) | 描述。 |
| `points_price` | Integer, not null | 兑换所需积分。 |
| `original_price` | Integer | 市场参考价，单位分，可空。 |
| `image_url` | String(255) | 图片（COS）。 |
| `stock` | Integer, default -1 | 库存，`-1` 不限。 |
| `sort` | Integer, default 0 | 排序。 |
| `status` | SmallInteger, default 1 | `0` 下架，`1` 上架。 |
| `redeem_start_at` | DateTime(3), nullable | 开兑时间，按 `Asia/Shanghai` 写入无时区时间；`NULL` 表示立即开兑。 |
| `max_redeem_per_user` | Integer, not null, default -1 | 每位玩家累计限兑数量；`-1` 不限，有限值必须大于等于 `1`。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳。 |

抢购控制字段由 GambitServer 迁移
`sql/20260915_add_point_product_redeem_controls.sql` 定义。OA 新建商品默认下架，
但显式传入的 `status` 会被保留。

### point_withdraw_records

模型：`PointWithdrawRecord`。积分提取/发放审计表（OA 只读）。通过 `user`/`issuer` 关系按 `open_id` 关联 `users` 展示昵称。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 记录 ID。 |
| `open_id` | String(60), not null | 申请用户。 |
| `points` | Integer, not null | 提取积分数。 |
| `status` | SmallInteger, default 0 | `0` 待发放，`1` 已发放，`2` 已过期，`3` 已取消。 |
| `issuer_open_id` | String(60) | 发放员工。 |
| `issued_at` | DateTime | 发放时间。 |
| `expire_at` | DateTime, not null | 过期时间。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳。 |

### point_redeem_orders

模型：`PointRedeemOrder`。积分兑换订单（OA 只读）。通过 `user`/`verifier` 关系按 `open_id` 关联 `users` 展示昵称。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | Integer PK | 兑换订单 ID。 |
| `order_no` | String(64), unique | 兑换订单号。 |
| `request_key` | String(64), nullable | 客户端兑换请求幂等键；与 `open_id` 组成唯一索引，历史订单可空。 |
| `open_id` | String(60), not null | 兑换用户。 |
| `product_id` | Integer | 关联 `point_products.id`。 |
| `product_name` / `product_image_url` / `points_price` | String/Integer | 兑换时商品快照。 |
| `quantity` | Integer | 兑换数量。 |
| `total_points` | Integer | 总消耗积分。 |
| `status` | SmallInteger, default 0 | `0` 待领取，`1` 已完成，`2` 已取消（预留）。 |
| `verifier_open_id` | String(60) | 核销员工。 |
| `verified_at` | DateTime | 核销完成时间。 |
| `created_at` / `updated_at` / `deleted_at` | DateTime | 时间戳。 |

> 账户 `point_accounts`、流水 `point_transactions` 由 GambitServer 写入（OA 也有同名模型），OA 当前不直接维护。积分兑换基础表来自 `sql/20260601_create_point_redeem_orders.sql`，请求幂等字段与索引来自 `sql/20260915_add_point_product_redeem_controls.sql`。

## 游玩工作台数据口径

- 工作台不新增业务表；订单来自 `play_orders`，实际结算金额只累计 `pay_orders.pay_status=1` 的 `amount`。
- 支付中状态由关联 `pay_orders.pay_status=0` 判断，存在时禁用 OA 离场操作。
- 近 5 分钟锚点使用 `pay_orders.pay_end_time`；理论金额按 `play_orders.in_time` 至当前时间或 `out_time` 的门店标准价计算，不使用优惠后金额。
- `20260905_add_play_workbench_indexes.sql` 增加 `play_orders(store_id,in_time)` 与 `pay_orders(pay_status,pay_end_time,play_order_id)` 索引。
