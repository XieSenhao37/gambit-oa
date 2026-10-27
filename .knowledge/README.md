# Gambit OA 知识库

## 餐品分类管理（2026-10-27）

- 餐饮管理新增 `/dish-categories`，页面权限 `dish-categories`、`admin` 范围，仅总部管理共用分类；门店菜单／餐品资料库仍可读取分类。功能搜索兼容“菜品分类／饮品分类／分类管理”。
- API `/admin_api/dish/v1/categories` GET/POST、`/<id>` PUT/DELETE，复用 `dish_categories`，无需迁移。支持名称（去首尾空白、最多60字、有效分类不重名）、非负整数排序和软删除；数值越小越靠前，同序按ID。小程序沿用既有 Go 菜单读取，无需修改小程序或Go。
- 编辑／删除须携带列表返回的 `Revision`，过期返回409并保留前端草稿，需重新打开编辑获取新版本。删除锁定分类后，以当前锁定读取检查全部门店的未删除餐品资料库和旧 `dishes`（含下架餐品），有引用则拒绝；不自动移除餐品分类。OA餐品保存校验并锁定有效分类，禁止引用已删除或不存在的分类。
- 分类页复用 AdaptiveTable 与 `oa-operation-modal`，无改动直接关闭，有草稿关闭前确认，保存中防重复提交。隔离验证：在backend目录执行 `.venv/bin/python -m unittest discover -s tests -p test_dish_categories.py`，覆盖总部权限、跨店／下架引用、软删除、排序、重名、冲突与餐品分类校验。

## OA 页面规范与导航（2026-10-21）

- 菜单唯一来源为 `backend/app/security/pages.json`，构建时 `frontend/scripts/sync-pages.cjs` 同步。工作台、订单中心、桌游管理、餐饮管理、会员与积分、活动与展示、经营与财务、系统设置共八个入口；原页面 ID、URL、门店范围及角色授权不随分组调整改变。
- 所有订单入口统一在订单中心；工作台提供收银、制作及租售待办。到店游玩计费与桌游租赁价格明确区分。导航顶部固定展示实际门店／共享范围，门店授权仍按页面校验；当前门店在同一账号和浏览器标签页内全局共享，不把跨店权限合并成全局角色。
- `FunctionSearch` 从真实注册页面和当前权限筛选结果，常用说法集中维护于 `frontend/src/config/navigation.ts`；不以搜索绕过页面权限。布局及视觉变量集中在 `frontend/src/styles/operations.less`，使用 Ant Design 图标与组件；黑灰主操作、蓝色链接和选中态，危险操作保留红色语义。
- 工作台和页头待办共用 `models/gameTodos.ts`：一份数据、一个轮询，页面不可见时暂停请求，操作后更新。待办为需处理的订单数，不伪装成未读消息；列表只展示最近项时，不用局部结果推算各类别总数。
- 租售订单使用紧凑状态筛选、统一 AdaptiveTable、单行主操作；财务汇总按需打开。筛选、搜索、分页写入 URL，待办链接保留订单所属门店；异步旧响应不能覆盖新条件，操作前重新核对订单状态。
- 订单详情按状态与动作、商品履约、费用、记录分组；押金不作为收入，历史通用配送不擅自改为顺丰。确认订单仍允许选填说明，拒单等必须说明的操作保留校验；退款与资金权限、幂等编号、自动退押金流程继续由服务端保护。
- 库存编辑按数量、出租、出售分组；日租金、押金、售价和品相独立于上架开关，关闭出租／出售时仍可查看、编辑和保存，不随改价自动上架。租后购买仍需同时开启出租和出售。总量／共享对外数量／留店数量同处一组，已占用数据只读。批量编辑使用表格，品相、配件和租后购买按行展开；所有变更一起保存，失败保留草稿，未保存关闭前确认。
- 相关检查：`node frontend/tests/menu.cjs`、`node frontend/tests/pageStores.cjs`、`node frontend/tests/operations.cjs`、AdaptiveTable 与请求编号专项，以及 OA 身份权限／桌游代理隔离测试。浏览器检查使用本机禁止业务写入的预览和测试环境，只读验收不创建订单、不操作真实支付退款、不改共享库存。

## 当前门店同步（2026-10-26）

- `utils/pageStores.ts` 使用账号级 `oa_current_store:<UserId>` 会话偏好，各模块共用；`hooks/usePreferredStore.ts` 订阅更新，旧的逐模块偏好不再参与选择。
- StoreSwitcher 不刷新浏览器文档。auth 包装器保留页头及导航，只在业务内容挂载前设置有效请求门店并重挂载该内容，清除旧门店的表单和弹窗。当前模块无所选门店权限时回退到可访问门店并同步全局，禁止用全局选择绕过逐页授权。
- 待办跳转先同步订单门店，再用前端路由进入订单模块；全局/总部页面继续使用各自授权范围，不作为可切换的门店模块。
- 检查：`node frontend/tests/pageStores.cjs`、`node frontend/tests/storeSwitching.cjs`，覆盖跨模块同步、重复选择、账号隔离、权限回退、业务首个请求门店与待办导航。

## 项目定位

`gambit-oa` 是 Gambit 桌游店网页端管理后台 monorepo，包含：

- `backend/`：Flask 管理后台 API，读写与小程序后端共用的核心业务库表。
- `frontend/`：Umi Max + React + Ant Design Pro 管理后台页面。

当前功能集中在后台登录、游玩订单管理、餐饮制作台、退款审核、用户角色管理、桌游列表与软删除。项目与小程序后端 `GambitServer` 共享 `users`、`play_orders`、`board_games`、`pay_orders`、`refund_requests` 等业务表，因此任何数据结构、金额单位、手机号加解密变更都需要同时考虑 Go 后端兼容性。

## 目录结构

```text
gambit-oa/
  backend/
    run.py
    Dockerfile
    uwsgi.ini
    requirements.txt
    app/
      __init__.py
      config.py
      routes.py
      models.py
      api/v1/
      middlewares/
      utils/
  frontend/
    package.json
    .umirc.ts
    src/
      app.ts
      access.ts
      wrappers/auth.tsx
      pages/
      services/
      services/typings.d.ts
  .knowledge/
```

## 技术栈

- 后端：Python、Flask 3、Flask-SQLAlchemy、Flask-CORS、PyJWT、PyMySQL、pycryptodome、python-dotenv。
- 前端：Umi Max 4、React 18、Ant Design 5、Ant Design Pro Components、TypeScript、pnpm。
- 部署：后端 Dockerfile 基于 `tiangolo/uwsgi-nginx-flask:python3.9`，`uwsgi.ini` 指向 `run:app`。

## 建议阅读顺序

1. `backend/run.py`、`backend/app/__init__.py`：理解 Flask app 创建、扩展初始化、健康检查和 DB 连接测试。
2. `backend/app/config.py`、`backend/app/routes.py`：确认环境变量、总路由前缀和模块蓝图。
3. `backend/app/api/v1/*.py`：逐个接口核对业务行为。
4. `backend/app/models.py`、`backend/app/utils/crypto.py`：理解共库表模型、金额单位和手机号加解密。
5. `frontend/.umirc.ts`、`frontend/src/app.ts`、`frontend/src/wrappers/auth.tsx`：理解路由、代理、请求拦截和登录态。
6. `frontend/src/pages/*`、`frontend/src/services/*`、`frontend/src/services/typings.d.ts`：理解页面与接口字段映射。

## 核心约定

- 后端 API 总前缀是 `/admin_api`，健康检查 `GET /health` 不带该前缀。
- 后端多数响应使用 `Code`、`Message`、`Data`，但存在少数不一致响应。
- 需要登录的接口通过 `Authorization: Bearer <token>` 传数据库会话 token（15 天），不接受旧 JWT。
- 前端登录后仅将 `token` 存入 `localStorage`，权限从 `/auth/v1/me` 获取，后续请求由 `src/app.ts` 自动注入 Authorization。测试环境已启用手机号验证码登录，见 [`runtime.md`](./runtime.md) 的「2026-10-21 测试环境启用手机号验证码登录」；历史临时账号机制见同文2026-09-27章节，生产登录配置未随本次切换修改。
- OA新版本检测、刷新确认及构建标识见 [`runtime.md`](./runtime.md) 的「2026-10-21 OA 新版本检测与主动刷新提示」。检测器全局注册一次，版本失败静默重试；首次接入需先刷新旧页面。
- 前端路由注册 `/login`、`/orders`、`/catering`、`/refunds`、`/games`、`/users`；`Home`、`Table`、`Access` 多为 Umi 模板/演示页，当前不在路由中。
- 手机号在库中是 AES-CBC 加密值，后台列表会解密后返回明文手机号。
- 金额字段在模型注释中通常以“分”为单位，但线下结算代码里存在元/分混用风险。
- 退款审核页读取 `refund_requests`，审核通过时经 OA 后端调用 `GambitServer` 内部接口 `/microapp_api/admin/refund/v1/approve` 发起微信退款；拒绝时调用 `/microapp_api/admin/refund/v1/reject` 写入审核备注。


## 门店资产结算

储值、月卡、积分批次账、OA 核对与期初迁移见 [`settlement.md`](./settlement.md)。这不是普通微信营业收款的完整月结报表；上线必须完成期初并同时启用 Go/OA。

2026-10-12 恢复仅总部可用的“基础管理 → 开通月卡”独立兜底页面（弹窗搜索、多选用户），无需原因/凭证；每期30天，配置价快照由总部承担，沿用赠卡补贴及免手续费口径，不计现金收入。重试防重、失败回滚，无新增迁移；详情见 settlement.md 的对应日期章节。

## 桌游计价管理

- OA 页面 `/play-pricing`（页面权限 `play-pricing`、按门店授权）；API `/admin_api/play-pricing/v1` GET/PUT，`/preview` POST。
- 共用 `configs.PlayConfig`，金额均以分保存。每个 `StoreMap[门店ID]` 支持 `Common`、`Holiday`、`SpecialMap`、`DateTypes`、`TimeRules`、`UseAdjustedWorkdays`；保存只覆盖当前门店且校验全配置 Revision，避免并发覆盖。旧全局配置首次保存时复制所有有效门店的原价格，保留其他门店行为。
- 时间按北京时间和入场时间；优先级：指定日期独立价格 > 匹配入场时段 > 日期类型基础价。时段支持跨午夜、起止生效日期，结束时刻不包含；跨午夜范围按实际入场日期匹配，不按营业日回溯。相同日期类型的有效时段不能重叠。
- 自动读取内置 2026 年七类全国放假范围，全部按 Holiday 计价；调休补班默认按 Common，可关闭。HolidayWeekdays 指定每周使用 Holiday 的星期（0 为周日，默认 `[0,5,6]`，空数组仅匹配国家假期），Go 与 OA 必须保持一致。DateTypes 可手动指定某天使用 common/holiday。新年份的农历节日和补班安排须维护日历或在 OA 批量添加日期覆盖；不会调用外部日历服务。
- 表单使用“全天封顶”与“优惠时长后续时”，不显示基础价格段落或收费示例，使用独立价格试算；基础价格并列卡片，时段、日期调整、指定日期及节假日日历在标签页中编辑；标签页表单强制挂载并用 getFieldsValue(true) 读取完整草稿，防止保存遗漏未展示规则；常规规则按钮仅填入草稿：Common=28元/小时、78元全天封顶，Holiday=28元/小时、3小时78元、续时10元，适用周五至周日及假期。历史公式不等价的旧配置独立保留，不自动改价。前端转换验证：`node frontend/scripts/test-play-pricing.cjs`。
- `BundlePricing=true`：`min(min(Hours, MaxHour)*Price, MaxTotal) + max(0, Hours-MaxHour)*AdditionPrice`；默认优惠时长 3 小时。false/缺省保留旧公式。时长券使用与 Go 正常计价相同的公式。
- 已结算订单不修改；未结算订单仍在下一次试算读取当前配置。Go 与 OA 必须配套部署才能执行时段及新公式，无新增数据库表或列。
- 隔离验证：在 backend 执行 `.venv/bin/python -m unittest discover -s tests -p test_play_pricing.py`，SQLite 覆盖权限、并发版本、配置兼容及计价。日历文件 `backend/app/services/play_calendar_2026.json` 与 Go 的 `model/play_calendar_2026.json` 需同步维护。


### 桌游租售与社区（2026-10-08）

- 新增桌游租售管理／出租与出售清单／桌游玩家社区，注册页面权限。共用门店切换，浏览器不可指定操作身份；Flask game_services 代理调用 Go 内部令牌 API，库存／资金状态始终由 Go 在事务中变更。
- game-services 为管理权限；game-service-orders 与 game-community 为普通店员权限。押金结算、遗失、售后退回及审核奖励需管理权限，退款发起另需 refunds 权限。
- 每店配置租售开关、租期与折扣、取货方式、条款及优质分享奖励（默认0）；池分配不能超过藏品数量，旧 inventory 编辑锁定原行并校验服务池数量。订单汇总独立显示累计净收入（含赔偿）、待退押金及待接单数，不把押金计收入。
- 邮寄手动履约：接单占用→发货→实际收回→检查→退押金；坏损不放回可用，整盒遗失管理登记。售后购买先支持全单收到／退全款／检查，不能仅付款退款便恢复库存。
- `backend/tests/test_game_services.py` 用 SQLite 覆盖身份门店代理、权限、超时重试及原库存守卫；真实 MySQL 库存/退款验证在 Go 隔离数据库进行。
- 2026-10-09 用户已明确授权并执行测试增量迁移，7表和支付可空列已核验，无业务种子。`scripts/migrate-test-game-services.py` 默认只读检查，`--apply` 只覆盖已有具体授权；严禁使用 backend/.env（本机是正式库）作为测试迁移连接。OA 调整藏品先锁父行，再以 FOR UPDATE 当前读取服务池，避免旧事务快照漏算并发分配；本地隔离 MySQL 回归覆盖这一边界。

- 2026-10-09 租售库存支持批量上架租赁/出售、跨分页选择已有库存后设置总量或日租价。出售上架逐款填售价；品相支持默认标签和自定义文字。调整备注选填，普通表单移除检查/保留量，待检查/维修只读，由履约流程维护。Go /stock/batch 原子提交，Flask 保留管理权限及服务端门店/操作人覆盖；重试复用同一内容的编号，改动内容生成新编号；超量或版本冲突显示桌游名，整批不提交。HTTP 浏览器 crypto.randomUUID 缺失时使用 getRandomValues/唯一编号回退，验证 node frontend/scripts/test-game-request-key.cjs。门店藏品分页读取完整，不截断第一批。

### 2026-10-17 桌游库存与租售合并

桌游库存 `Games` 集成唯一总数量、对外共享额度、出租／出售开关、价格和押金；`RentalEditor` 支持批量额度、开关、日价、押金，出售逐款定价。旧 GameServices 仅保留门店租售设置，社区奖励及联系文案移至 GameCommunity。GameServiceOrders 默认待办，提供快捷交付／完好归还与异常入口，电话等联系人信息限当前门店。

后端代理 GET/PUT game-service/v1/inventory，写入继续要求 game-services 管理权限，读取要求 games 权限；AutoRefund 由 OA 的退款权限决定并覆盖浏览器值。原数量编辑对共享额度进行保护并更新配置版本，防止另一编辑页覆盖改动。

迁移准备脚本 `scripts/migrate-test-shared-game-inventory.py` 默认只读，硬校验广州测试库和测试 Go 地址。`--apply` 添加2表、13列、2索引；新 Go 部署后，另获配置转换授权再加 `--convert-existing` 将旧分配合计转共享额度，保留原价、门店总数、订单关联，租转购默认关闭。没有新增授权前不执行结构／数据迁移，不重启依赖新结构的测试容器；可完成本地和镜像准备。

2026-10-19 用户简化完好归还：普通店员 return_complete 即自动原路退应退押金，不再依赖 refunds 页面权限；Go限定本单、完成实物检查、计算金额，提交事务后立即调度并保留持久化补偿。OA覆盖浏览器AutoRefund，自动任务显示“自动退款中”且不出现再次发起按钮。settle_deposit/遗失/售后等异常操作仍保留原管理、退款权限；历史未授权自动退的任务不批量转换。

2026-10-19 顺丰配送：门店租售设置增加 ShippingServices 多选档位（普快／特快／同城秒送），Shipping 为租赁与购买共用开关。订单详情显示加密 Contact 返回的档位，发货时有档位的新订单固定顺丰速运或顺丰同城；历史通用邮寄订单保持原行为。配置仍通过 Go policy 版本校验保存，不需要迁移，部署不自动修改门店配送开关。
