# 前端说明

## 架构

前端位于 `frontend/`，技术栈为 Umi Max 4、React 18、Ant Design 5、Ant Design Pro Components、TypeScript，包管理器为 pnpm。

核心文件：

- `frontend/.umirc.ts`：Umi 配置、路由、layout、代理、request 配置。
- `frontend/src/app.ts`：运行时 layout、全局请求拦截、401 处理。
- `frontend/src/wrappers/auth.tsx`：路由登录态守卫。
- `frontend/src/access.ts`：Umi 模板权限示例，不是实际后台权限体系。
- `frontend/src/pages/*`：页面。
- `frontend/src/services/*`：请求封装。
- `frontend/src/services/typings.d.ts`：API 类型声明。

## 路由

`.umirc.ts` 当前注册：

- `/login`：登录页，关闭 layout。
- `/`：重定向到 `/dashboard`，包裹 `@/wrappers/auth`。
- `/dashboard`：运营分析大盘，包裹 `@/wrappers/auth`。
- `/orders`：历史游玩订单，只读，包裹 `@/wrappers/auth`。
- `/catering-orders`：历史餐饮订单，只读，包裹 `@/wrappers/auth`。
- `/refunds`：退款管理，包裹 `@/wrappers/auth`。
- `/catering`：饮品制作台，包裹 `@/wrappers/auth`。
- `/dishes`：门店菜单，包裹 `@/wrappers/auth`。
- `/dish-library`：餐品信息库，包裹 `@/wrappers/auth`。
- `/games`：桌游管理，包裹 `@/wrappers/auth`。
- `/users`：用户管理，包裹 `@/wrappers/auth`。
- `/wallet-tiers`：充值档位管理，包裹 `@/wrappers/auth`。
- `/point-products`：积分商品管理（`PointProducts`，ProTable + Drawer + Upload + 抢购控制 + 快速上下架 + 删除）。
- `/point-categories`：积分商品一级分类管理（`PointCategories`，轻量 CRUD）。
- `/point-withdraws`：积分提取审计（`PointWithdraws`，只读 ProTable + 用户/状态筛选）。
- `/point-redeem-orders`：积分兑换明细（`PointRedeemOrders`，只读 ProTable + 订单/用户/商品关键词和状态筛选）。
- `/point-config`：消费得积分规则配置（`PointConfig`，每满 X 元得 Y 积分、单次提取上限）。

> 积分相关服务封装在 `src/services/point.ts`，类型在 `src/services/typings.d.ts`。

> 注：本路由列表以 `.umirc.ts` 为准，菜单展示由 `src/config/menu.ts` 补充控制。

`Home`、`Table`、`Access` 等目录仍存在，但属于 Umi 模板/演示页，当前没有注册到路由中。

## 认证与状态

登录页 `src/pages/Login/index.tsx`：

- 调用 `src/services/auth.ts` 的 `login()`。
- 成功时检查 `res.Code === 0`。
- 将 `res.Data.token` 存为 `localStorage.token`。
- 将 `res.Data.role` 存为 `localStorage.role`。
- 跳转 `/`，再重定向到 `/dashboard`。

`src/app.ts` 请求拦截：

- 每次请求前从 `localStorage.token` 读取 token。
- 存在 token 时注入 `Authorization: Bearer <token>`。
- 响应状态为 401 时清除 `token`、`role`，提示“登录已过期，请重新登录”，并跳转 `/login`。

门店上下文：

- `src/utils/pageStores.ts` 在当前标签页内存中维护请求门店，避免多个标签页互相串店；`sessionStorage` 按用户和页面分别记忆门店选择。授权容器先确认当前页面可用门店，再挂载业务页面。
- `src/app.ts` 仍会给请求注入 `X-Store-ID`，但侧边栏不再展示全局门店切换。
- 门店切换只在需要门店上下文的页面或标签局部展示，例如桌游库存、饮品制作台、Dashboard 的门店型统计标签。
- 依据页面目录的 `scope` 展示门店控件：`store` 页面仅列出有该页面权限的门店，单店显示固定名称；`global` 页面显示全品牌共享提示；`admin` 授权管理在表单中选择门店。Dashboard 保留按统计标签显示控件。
- 侧栏菜单取所有授权门店的页面并集，保持一级分组；退出登录独立在侧栏底部。后端仍按请求门店校验该门店的页面权限，不能通过菜单并集跨店越权。

`src/wrappers/auth.tsx`：

- 检查登录身份和当前页面的门店权限；每 30 秒及窗口聚焦时更新身份。门店授权失效后重新选择可用门店，无可访问页面显示 403。

`src/access.ts`：

- 只保留 Umi 模板级 `canSeeAdmin` 示例。
- 当前业务页面没有依赖它做权限控制。

## 页面

### Login

路径：`src/pages/Login/index.tsx`

员工手机号验证码登录，具体短信及临时测试入口配置见 runtime.md；登录会话有效期 15 天。

### Orders

路径：`src/pages/Orders/index.tsx`

能力：

- 使用 ProTable 展示游玩订单。
- 支持按用户 ID、OpenId、结算状态、入场时间范围、出场时间范围筛选。
- 展示用户昵称、解密手机号、OpenID、入离场时间、时长、金额、状态、备注和创建/更新时间。
- 页面无操作列、弹窗或写请求；离场与结算只允许从工作台执行。
- 门店订单页面由授权容器展示当前门店，并通过 `X-Store-ID` 请求对应门店数据。

### CateringOrders

路径：`src/pages/CateringOrders/index.tsx`

- 当前门店全部餐饮订单的只读 ProTable，支持关键字、制作状态、支付状态和下单时间筛选。
- 主表展示订单、玩家、金额、制作/支付状态、取餐方式和时间。
- 展开行展示 OpenID、桌台、餐品规格、支付流水、商户订单号、支付描述和备注。
- 页面不提供制作、取餐、结算或其他写操作。

### Refunds

路径：`src/pages/Refunds/index.tsx`

能力：

- 复用同一页面管理玩乐、吃喝和组局意向金退款；侧边栏“订单中心 > 退款管理”进入 `/refunds`。
- 组局意向金行展示活动标题、门店、活动时间和报名状态；已报名的 `pending_review` 显示“待到店退款”，已取消报名显示“已取消 / 待处理”，`rejected` 显示“不退款”。
- 行内操作使用短文案“退款 / 不退款 / 重试”；完整风险说明保留在二次确认弹窗，“不退款”仍要求填写备注。
- 仅 `organization + pending_review + RegistrationStatus=1` 的已报名待到店记录可勾选。工具栏展示“批量退款 N”，确认时汇总人数和总金额，最多 3 笔并发复用单笔 approve 接口，结束后汇总成功/失败并清空选择。
- 页面每 10 秒自动刷新列表，使微信异步回调落库后无需离开页面即可从“退款中”更新为“已退款”；批量处理期间暂停定时刷新。
- 未识别的订单类型使用兜底标签，不直接索引类型元数据导致页面崩溃。

### Catering

路径：`src/pages/Catering/index.tsx`

能力：

- 展示饮品制作台订单，支持状态、关键词、只看今日和自动刷新。
- 通过局部 `StoreSwitcher` 切换“制作门店”，切换后重新加载当前门店订单。
- 后端 `GET /admin_api/catering/v1/orders` 会读取 `X-Store-ID` 按门店过滤。

### Dish（门店菜单）

路径：`src/pages/Dish/index.tsx`

能力：

- 展示当前门店菜单项，基础资料来自全局餐品信息库，门店字段只包括售价、上下架和排序。
- 工具栏局部显示“当前菜单门店”，切换门店会关闭当前 Drawer 并重新加载列表。
- 支持从全局餐品信息库选择餐品添加到当前门店菜单。
- 支持编辑当前门店售价、排序和上下架状态。
- 支持从当前门店菜单移除餐品，不删除全局餐品信息。

注意：

- 图片、名称、分类、规格选项、描述、标签等全局字段在 `DishLibrary` 页面维护；编辑会同步影响所有门店引用。
- 为兼容小程序下单，OA 门店菜单操作会由后端同步维护旧 `dishes` 行。

### DishLibrary（餐品信息库）

路径：`src/pages/DishLibrary/index.tsx`

能力：

- 管理全局餐品资料 `dish_library_items`，包括名称、默认价格、图片、分类、规格选项、描述和标签。
- 支持新增、编辑、删除餐品资料。
- 图片通过本地文件选择上传，后端写入 COS 后保存 URL。
- 删除全局餐品前，后端会检查是否仍被门店菜单引用；存在引用时拒绝删除。

### Users

路径：`src/pages/Users/index.tsx`

能力：

- 展示用户列表。
- 支持按用户 ID、OpenId、角色、昵称、手机号、是否月卡用户等条件筛选。
- 展示只读的积分余额、储值余额和累计消费金额；储值与消费金额按分返回、按元展示。
- 支持按积分余额、储值余额和累计消费金额进行服务端升序或降序排序。
- 编辑用户角色，实际只提交 `Role`。
- 支持在用户行操作中手动开通/续期月卡，覆盖美团核销、寄存赠送、手动调整和其他运营来源；弹窗展示当前到期时间，填写开通月数、来源、实收金额、外部凭证号和备注。

注意：

- 用户角色展示以小程序服务端 `constant/user/user.go` 为准：`0` 普通用户、`1` 店员、`2` 兼职、`126` 管理员、`127` 超级管理员；编辑下拉展示全部角色，但禁用管理员和超级管理员，避免在 OA 中直接提权。
- 积分余额、储值余额和累计消费金额不会写入用户编辑表单，也不会随角色更新请求提交。

### Games（桌游库存）

路径：`src/pages/Games/index.tsx`

能力：

- 展示当前门店桌游库存。
- 支持按名称映射为后端 `Keyword` 搜索。
- 列表只展示 ID、封面、名称、数量。
- 支持从全局「桌游信息库」选择桌游添加到当前门店库存。
- 支持修改当前门店库存数量。
- 支持从当前门店库存移除桌游，不删除全局桌游资料。
- 支持打开详情抽屉，从全局桌游信息库读取完整资料。
- 工具栏局部显示“当前库存门店”，切换后仅重载库存列表。

注意：

- 存放位置已从 UI 移除，数据库字段暂时保留不用。
- 门店库存增删改都基于当前局部门店选择，侧边栏不再承担门店切换。

### GameLibrary（桌游信息库）

路径：`src/pages/GameLibrary/index.tsx`

能力：

- 管理全局桌游资料 `board_games`。
- 支持新增、编辑、删除桌游资料。
- 编辑会影响所有门店和小程序展示。
- 删除全局资料前，后端会检查是否仍存在门店库存；存在库存时拒绝删除。
- 表单维护名称、封面图、详情图片、评分、排名、人数、难度、时长、类别、模式、机制、主题、简介等全局字段。
- 封面图和详情图片通过本地文件选择上传，后端写入 COS 后保存 URL；编辑时不重新上传封面则保留旧封面。

### WalletTiers

路径：`src/pages/WalletTiers/index.tsx`

能力：

- 使用 ProTable 展示储值充值档位（`wallet_recharge_tiers`）。
- Drawer + Form 新建/编辑档位，金额、赠送金额按元录入、提交时换算成分。
- Switch 启用/停用档位，Popconfirm 软删除档位。

注意：

- 充值金额限 1-5000 元；赠送金额 `0` 表示该档无赠送。
- 该档位仅供小程序展示与后端按金额匹配赠送，赠送形式为固定档位，自定义金额不参与赠送。

### PointProducts

路径：`src/pages/PointProducts/index.tsx`

能力：

- 新建/编辑商品时可选“暂不上架”“立即上架”“定时上架”；新建默认暂不上架。
- 定时上架必须选择未来的日期时间，提交为 13 位 epoch 毫秒；非定时模式提交空开兑时间。
- 每人限兑支持 `-1` 表示不限，有限值必须大于等于 `1`。
- 列表根据商品开关、开兑时间与库存派生展示“下架”“待开抢”“上架中”“已兑完”，并展示开兑时间和每人限额。
- 行内 Switch 继续提供快速上下架；重新上架不会清除已配置的定时开兑时间。

### Dashboard

路径：`src/pages/Dashboard/index.tsx`

能力：

- 使用 `PageContainer` + `Tabs` + `Card` + `Statistic` + Recharts + Ant Design `Table` 展示运营大盘。
- 全局筛选支持今日、近 7 天、近 30 天、自定义日期，以及日/周/月粒度。
- 顶部经营总览展示桌游/饮品营收、订单数、新增用户、活跃用户、储值充值和积分消耗。
- 「促销与老带新」展示券活动领取/核销/核销率/带动订单/带动金额/优惠金额，以及老带新绑定、首单和奖励发放趋势。
- 「用户洞察」展示新增用户、付费用户、新付费用户、复购/老客、注册来源门店和用户聚合明细。
- 「饮品分析」保留原餐饮统计能力：饮品营收、订单、出杯数、趋势、热销餐品、时段、品类和支付方式。
- 「桌游分析」展示桌游营收、游玩订单、游玩用户、时长、计费模式和支付方式。
- 「月卡/储值/积分」展示月卡开通、月卡来源分布、储值充值/消费/余额沉淀、积分发放/消耗/兑换排行。
- 门店切换只在「经营总览」「促销与老带新」「饮品分析」「桌游分析」标签展示，切换后重新拉取统计数据。

注意：

- Dashboard 并行请求 `src/services/stats.ts` 中的多个 `/admin_api/stats/v1/*` 接口。
- 当前统计以交易结果数据为主；曝光、点击、支付取消、入群转化等过程型漏斗需后续小程序埋点支持。
- 门店型统计依赖请求头 `X-Store-ID`，但门店选择入口只在相关标签局部展示。

## 服务层

- `src/services/auth.ts`
  - `POST /admin_api/auth/v1/login`
  - `POST /admin_api/auth/v1/logout`
- `src/services/users.ts`
  - `GET /admin_api/user/v1/list`
  - `PUT /admin_api/user/v1/{userId}`
- `src/services/monthCard.ts`
  - `POST /admin_api/month-card/v1/manual-open`
  - `GET /admin_api/month-card/v1/orders`
- `src/services/orders.ts`
  - `GET /admin_api/order/v1/list`
  - `GET /admin_api/order/v1/workbench`
  - `POST /admin_api/order/v1/workbench/settle/{orderId}`
  - `POST /admin_api/order/v1/workbench/quick-settle/{orderId}`
- `src/services/catering.ts`
  - `GET /admin_api/catering/v1/history`
- `src/services/refund.ts`
  - `GET /admin_api/refund/v1/list`
  - `POST /admin_api/refund/v1/approve/{refundRequestId}`
  - `POST /admin_api/refund/v1/reject/{refundRequestId}`
- `src/services/games.ts`
  - `GET /admin_api/game/v1/inventory/list`
  - `POST /admin_api/game/v1/inventory`
  - `PUT /admin_api/game/v1/inventory/{id}`
  - `DELETE /admin_api/game/v1/inventory/{id}`
  - `GET /admin_api/game/v1/library/list`
  - `GET /admin_api/game/v1/library/{id}`
  - `POST /admin_api/game/v1/library`
  - `PUT /admin_api/game/v1/library/{id}`
  - `DELETE /admin_api/game/v1/library/{id}`
- `src/services/dish.ts`
  - `GET /admin_api/dish/v1/list`：当前门店菜单列表。
  - `PATCH /admin_api/dish/v1/{id}/status`：当前门店菜单项上下架。
  - `GET /admin_api/dish/v1/library/list`：全局餐品信息库列表。
  - `POST /admin_api/dish/v1/library`：新增全局餐品资料。
  - `PUT /admin_api/dish/v1/library/{id}`：编辑全局餐品资料。
  - `DELETE /admin_api/dish/v1/library/{id}`：删除全局餐品资料，仍被门店引用时拒绝。
  - `POST /admin_api/dish/v1/store-items`：从信息库添加餐品到当前门店菜单。
  - `PUT /admin_api/dish/v1/store-items/{id}`：编辑当前门店菜单项配置。
  - `DELETE /admin_api/dish/v1/store-items/{id}`：从当前门店菜单移除餐品。
- `src/services/wallet.ts`
  - `GET /admin_api/wallet/v1/tiers`
  - `POST /admin_api/wallet/v1/tiers`
  - `PUT /admin_api/wallet/v1/tiers/{tierId}`
  - `PATCH /admin_api/wallet/v1/tiers/{tierId}/status`
  - `DELETE /admin_api/wallet/v1/tiers/{tierId}`
- `src/services/stats.ts`
  - `GET /admin_api/stats/v1/ops/overview`
  - `GET /admin_api/stats/v1/catering/overview`
  - `GET /admin_api/stats/v1/play/overview`
  - `GET /admin_api/stats/v1/user/overview`
  - `GET /admin_api/stats/v1/coupon/overview`
  - `GET /admin_api/stats/v1/referral/overview`
  - `GET /admin_api/stats/v1/membership/overview`
  - `GET /admin_api/stats/v1/wallet/overview`
  - `GET /admin_api/stats/v1/point/overview`
  - `GET /admin_api/stats/v1/user/insights`

## 类型声明注意事项

`src/services/typings.d.ts` 中存在几类不一致：

- `API.Response` 声明为 `Code`、`Msg`、`Data`，但后端多数返回 `Code`、`Message`、`Data`。
- `BoardGame` 接口被声明了两次，前一次是小写简版字段，后一次是大写完整字段。
- `PlayOrder.User` 类型没有声明 `Phone`，但订单页使用 `User.Phone` 展示手机号。
- 用户字段中存在 `createdAt`/`updatedAt` 小写声明，但后端返回 `CreatedAt`/`UpdatedAt` 大写字段。

## 双订单工作台

- 一级菜单首项 `/workbench` 使用 URL 参数 `tab=catering|play` 切换餐饮、游玩订单；旧 `/catering` 重定向到餐饮 Tab。
- 餐饮 Tab 复用 `CateringWorkbench`，保持原制作、取餐与 10 秒刷新逻辑；未激活 Tab 不挂载，不产生重复轮询。
- 游玩 Tab 默认显示当前门店今日订单，待结算优先且按入场时间升序；支持 10 秒自动刷新开关和手动刷新。
- 手动弹窗或离场请求期间暂停轮询；支付中订单禁用离场操作。
- 顶部近 5 分钟核账区按批次逐行横向滚动，金额差异同时用红色、警告图标和文字提示；批次中的待结算订单也可直接手动或快速离场，支付中/已结算订单按钮禁用。


开屏展示与首页弹窗统一推荐 1080 × 1440（3:4）。展示管理开屏预览支持短屏、标准屏、长屏，使用完整海报和底部品牌区；小程序自动展示标准 GAMBIT-01 Logo、一行业态（Board Games 桌游 / TCG 集换式卡牌 / Collectable Cards 收藏卡）和一行 It All Starts At The Table，无需运营在素材中预留品牌区。旧比例图片完整展示，可能留边。此修改不涉及数据库迁移。

2026-09-26：侧栏恢复订单中心、餐饮、卡牌、储值、积分、基础管理六个一级分组；工作台与数据仪表盘独立。分组信息维护在 backend/app/security/pages.json，前端先按叶子页面权限过滤，再生成分组；无可访问子页时隐藏整个分组，不能再直接把全部页面平铺。员工及门店授权位于基础管理，权限仍总部专属。验证：frontend/tests/menu.cjs。
