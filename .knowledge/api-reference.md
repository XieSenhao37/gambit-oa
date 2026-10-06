# API 参考

后端 API 总前缀为 `/admin_api`，健康检查例外。除特别说明外，响应通常为 `Code`、`Message`、`Data`。

## 健康检查

| 方法 | 路径 | Token | 行为 |
| --- | --- | --- | --- |
| GET | `/health` | 否 | 返回服务健康状态：`status=healthy`、`message=Service is running`。 |

## Auth

基础路径：`/admin_api/auth/v1`

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| POST | `/login` | 否 | JSON：`username`、`password` | 仅接受硬编码账号 `admin` / `<OA_ADMIN_PASSWORD: 从环境变量配置>`。成功返回 `Data.token` 和 `Data.role=9999`；失败返回 HTTP 401。 |
| POST | `/logout` | 是 | 无 | 校验 token 后返回成功；不做服务端 token 吊销。 |

登录成功响应示例：

```json
{
  "Code": 0,
  "Message": "success",
  "Data": {
    "token": "...",
    "role": 9999
  }
}
```

## User

基础路径：`/admin_api/user/v1`

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/list` | 是 | Query：`Current`、`PageSize`、`Id`、`OpenId`、`Role`、`UserType`、`NickName`、`PhoneNumber`、`IsMonthCardUser`、`SortField`、`SortOrder` | 分页查询未删除用户。手机号查询会先加密再比对库值；响应会解密返回 `PhoneNumber`。 |
| PUT | `/<user_id>` | 是 | JSON：`Role` | 更新用户角色，并刷新 `updated_at`。 |

`GET /list` 参数说明：

- `Current`：页码，默认 1。
- `PageSize`：每页条数，默认 10。
- `Id`：用户表 ID。
- `OpenId`：小程序 open_id。
- `Role`：角色。
- `UserType`：用户类型。
- `NickName`：昵称模糊匹配。
- `PhoneNumber`：明文手机号，后端加密后精确匹配。
- `IsMonthCardUser`：`1` 表示有 `month_card_expire`，`0` 表示无。
- `SortField`：可选，仅允许 `PointBalance`、`WalletBalance` 或 `TotalConsumptionAmount`。
- `SortOrder`：可选，`asc` 或 `desc`；未提供或非法参数时按用户 ID 升序。指标值相同时按用户 ID 升序保证分页稳定。

返回用户字段：

- `Id`
- `OpenId`
- `UserType`
- `Role`
- `NickName`
- `Gender`
- `PhoneNumber`
- `MonthCardExpire`
- `PointBalance`：积分余额，整数积分，只读。
- `WalletBalance`：储值余额，单位分，只读。
- `TotalConsumptionAmount`：累计已支付游玩与餐饮消费，单位分，只读；不含储值充值、月卡、未支付和已退款订单。
- `CreatedAt`
- `UpdatedAt`

## Order

基础路径：`/admin_api/order/v1`

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/list` | 是 | Query：`current`、`pageSize`、`OpenId`、`UserId`、`SettleStatus`、`InTimeStart`、`InTimeEnd`、`OutTimeStart`、`OutTimeEnd`、`StartTime`、`EndTime` | 只读分页查询未删除游玩订单，按创建时间倒序，关联用户并返回昵称和解密手机号。 |

`GET /list` 参数说明：

- `current`：页码，默认 1。
- `pageSize`：每页条数，默认 10。
- `OpenId`：按订单 `open_id` 精确筛选。
- `UserId`：通过 `users.id` 筛选。
- `SettleStatus`：`0` 待结算，`1` 已结算。
- `InTimeStart`、`InTimeEnd`：入场时间范围，格式 `%Y-%m-%d %H:%M:%S`。
- `OutTimeStart`、`OutTimeEnd`：出场时间范围，格式 `%Y-%m-%d %H:%M:%S`。
- `StartTime`、`EndTime`：订单创建时间范围，格式 `%Y-%m-%d %H:%M:%S`。前端页面当前没有传这两个字段。

返回订单字段：

- `Id`
- `StoreId`
- `OpenId`
- `InTime`
- `OutTime`
- `PlayTime`
- `Amount`
- `SettleStatus`
- `Comment`
- `UnitPrice`
- `CreatedAt`
- `UpdatedAt`
- `User.Id`
- `User.OpenId`
- `User.NickName`
- `User.Phone`

订单中心不提供游玩订单写接口。手动/快速离场统一从工作台进入，并由 OA 代理 GambitServer 完成。

## Catering History

基础路径：`/admin_api/catering/v1`

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/history` | 是 | Query：`current`、`pageSize`、`Keyword`、`Status`、`PayStatus`、`StartTime`、`EndTime` | 按 `X-Store-ID` 只读分页查询全部餐饮订单，包含未支付、已支付、已关闭、已退款和无支付流水订单。 |

- `PayStatus` 支持 `0` 待支付、`1` 已支付、`2` 已关闭、`3` 已退款、`none` 无支付流水。
- 一个餐饮订单存在多条支付尝试时，仅关联最新未删除支付流水，避免分页重复。
- 返回订单、玩家、解密手机号、桌台、餐品/规格、备注、制作状态以及支付金额、方式、状态和时间等详情。
- 制作台继续使用 `/list`，原成功支付与制作状态口径不变。

## Refund

基础路径：`/admin_api/refund/v1`。OA 只读共享数据库中的退款申请，资金状态变更统一代理到 GambitServer 内部接口。

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/list` | 是 | Query：`current`、`pageSize`、`Status`、`OrderType=play\|catering\|organization`、`Keyword` | 直接读取共享库 `refund_requests`；退款补偿与对账由 GambitServer 后台任务执行，避免列表请求被外部微信查询阻塞。 |
| POST | `/approve/<refund_request_id>` | 是 | 无 | 代理 GambitServer `approve` 发起微信原路退款；`refund_failed` 重试也使用此接口。 |
| POST | `/reject/<refund_request_id>` | 是 | JSON：`Remark` | 代理 GambitServer `reject`；组局意向金场景表示“标记不退款”。 |

批量退款不新增后端资金接口。OA 前端仅允许选择 `organization + pending_review + RegistrationStatus=1` 的已报名待到店记录，以最多 3 个并发逐笔复用 `/approve/<refund_request_id>`；GambitServer 的单笔状态机和稳定退款单号继续承担幂等防线。

`OrderType=organization` 时：

- `OrderId` 对应 `group_activity_participants.id`，`PayOrderId` 是精确关联的支付单。
- `OrderSnapshot` 返回 `ActivityId`、`ActivityTitle`、`StoreId`、`StoreName`、`ActivityStartTime`、`RegistrationStatus`，并保留通用 `Title`、`StatusText`、`Amount`。
- `User` 优先通过报名记录的 `open_id` 关联，返回报名用户昵称和解密手机号。
- `Keyword` 支持活动标题、用户昵称、OpenID；手机号按现有确定性 AES 密文做明文输入后的精确匹配，不支持手机号模糊匹配。

## Game

基础路径：`/admin_api/game/v1`

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/list` | 否 | Query：`PageNum`、`PageSize`、`Keyword` | 分页查询未删除桌游，按 ID 倒序；关键词匹配 `name` 或 `description`。当前没有 `@login_required`。 |
| DELETE | `/<game_id>` | 是 | 无 | 将 `board_games.deleted_at` 写为当前 UTC 时间，实现软删除。 |

`GET /list` 参数说明：

- `PageNum`：页码，默认 1。
- `PageSize`：每页条数，默认 10。
- `Keyword`：按桌游名称或简介模糊搜索。

返回桌游字段：

- `Id`
- `Name`
- `GstoneScore`
- `GstoneRank`
- `SupportedPlayers`
- `RecommendedPlayers`
- `CoverUrl`
- `Complexity`
- `PlayTime`
- `SetupTime`
- `LanguageLevel`
- `Description`
- `PictureList`
- `Designer`
- `Publisher`
- `PublishLanguage`
- `PublishYear`
- `Categories`
- `Modes`
- `Mechanisms`
- `Themes`
- `TableRequirement`
- `Portability`
- `SuitableAge`
- `Count`
- `StorageLocation`
- `CreatedAt`
- `UpdatedAt`

删除响应当前为小写字段：

```json
{
  "code": 0,
  "msg": "success"
}
```

## Wallet 充值档位

基础路径：`/admin_api/wallet/v1`

维护 `wallet_recharge_tiers`（与 GambitServer 共用表，小程序据此展示「充多少送多少」）。金额、赠送金额单位均为分；前端按元录入、提交时换算。

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/tiers` | 是 | Query：`current`、`pageSize` | 分页查询未删除档位，按 `sort`、`amount` 升序。 |
| POST | `/tiers` | 是 | JSON：`Amount`、`BonusAmount`、`Label`、`Sort`、`Enabled` | 新建档位。`Amount` 限 100-500000 分；`BonusAmount>=0`。 |
| PUT | `/tiers/<tier_id>` | 是 | 同上 | 更新档位。 |
| PATCH | `/tiers/<tier_id>/status` | 是 | JSON：`Enabled`（0/1） | 启用/停用档位。 |
| DELETE | `/tiers/<tier_id>` | 是 | 无 | 软删除档位（写 `deleted_at`）。 |

返回档位字段：`Id`、`Amount`、`BonusAmount`、`Label`、`Sort`、`Enabled`、`CreatedAt`、`UpdatedAt`。

## Point 积分系统

基础路径：`/admin_api/point/v1`

维护积分商品分类/商品（与 GambitServer 共用表，小程序据此展示积分商城）、积分提取审计（只读）、消费得积分规则。商品图片复用 `cos_service.upload_file_to_cos`（`folder='point-products'`）。`OriginalPrice`、`EarnThresholdAmount` 单位为分，前端按元录入、提交时换算。

积分商品分类（`point_product_categories`）：

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/categories` | 是 | 无 | 查询未删除分类，按 `sort`、`id` 升序。 |
| POST | `/categories` | 是 | JSON：`Name`、`Sort`、`Status` | 新建分类。 |
| PUT | `/categories/<id>` | 是 | 同上 | 更新分类。 |
| PATCH | `/categories/<id>/status` | 是 | JSON：`Status`（0/1） | 启用/停用分类。 |
| DELETE | `/categories/<id>` | 是 | 无 | 软删除分类；分类下仍有未删除商品时禁止删除。 |

积分商品（`point_products`）：

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/products` | 是 | Query：`current`、`pageSize`、`Keyword`、`CategoryId` | 分页查询未删除商品，按 `sort` 升序；同时返回 `Categories` 供下拉。 |
| POST | `/products` | 是 | FormData：`Name`、`CategoryId`、`Description`、`PointsPrice`、`OriginalPrice`、`Stock`、`Sort`、`Status`、`RedeemStartAt`、`MaxRedeemPerUser`、`Image` | 新建商品（需上传图片）；未传 `Status` 时默认下架。 |
| PUT | `/products/<id>` | 是 | 同上（图片可选） | 更新商品；未传抢购控制字段时保留原值。 |
| PATCH | `/products/<id>/status` | 是 | JSON：`Status`（0/1） | 上架/下架商品。 |
| DELETE | `/products/<id>` | 是 | 无 | 软删除商品。 |

抢购控制字段：

- `Status`：`0` 下架、`1` 上架；新建时尊重显式值，否则默认 `0`。
- `RedeemStartAt`：空值表示立即开兑；定时开兑时提交 13 位 epoch 毫秒，后端按 `Asia/Shanghai` 转成数据库无时区时间，且必须晚于当前时间。
- `MaxRedeemPerUser`：`-1` 表示不限；有限额时必须为大于等于 `1` 的整数。
- 商品响应新增同名 `RedeemStartAt`、`MaxRedeemPerUser` 字段；开兑时间按 `YYYY-MM-DD HH:mm:ss` 返回。

积分提取审计（`point_withdraw_records`，只读）：

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/withdraws` | 是 | Query：`current`、`pageSize`、`Keyword`（OpenID）、`Status`（0-3） | 分页查询提取记录，含申请人/积分/状态/发放员工/时间。 |

积分兑换明细（`point_redeem_orders`，只读）：

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/redeem-orders` | 是 | Query：`current`、`pageSize`、`Keyword`（订单号/OpenID/昵称/商品名）、`Status`（0-2） | 分页查询积分兑换订单，含商品快照、消耗积分、用户、核销员工、兑换/核销时间。 |

积分规则（`configs.PointConfig`）：

| 方法 | 路径 | Token | 参数 | 行为 |
| --- | --- | --- | --- | --- |
| GET | `/config` | 是 | 无 | 读取规则，未配置返回默认 `{1000,1,0}`。 |
| PUT | `/config` | 是 | JSON：`EarnThresholdAmount`（分）、`EarnPoints`、`MaxWithdrawPerTime` | 写入规则；门槛与每档积分需 >=1，提取上限 >=0（0 不限）。 |

## 游玩订单工作台

基础路径：`/admin_api/order/v1/workbench`，均需 OA 登录，并从 `X-Store-ID` 读取当前门店。

- `GET /workbench`：代理 GambitServer，返回今日订单、权威理论计价、支付中状态和近 5 分钟结算批次。
- `POST /workbench/settle/{orderId}`：Body 为 `Amount`（元，最多两位小数）和可选 `Comment`；OA 使用 Decimal 转为分后代理手动线下结算。
- `POST /workbench/quick-settle/{orderId}`：固定以 0 分执行快速离场。
- 写操作附带当前 OA 操作人；门店、并发支付和订单终态由 GambitServer 再校验。
