# Gambit OA 知识库

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
- 前端登录后仅将 `token` 存入 `localStorage`，权限从 `/auth/v1/me` 获取，后续请求由 `src/app.ts` 自动注入 Authorization。当前临时账号登录与后续短信切换见 [`runtime.md`](./runtime.md) 的「2026-09-27 临时固定账号登录」。
- 前端路由注册 `/login`、`/orders`、`/catering`、`/refunds`、`/games`、`/users`；`Home`、`Table`、`Access` 多为 Umi 模板/演示页，当前不在路由中。
- 手机号在库中是 AES-CBC 加密值，后台列表会解密后返回明文手机号。
- 金额字段在模型注释中通常以“分”为单位，但线下结算代码里存在元/分混用风险。
- 退款审核页读取 `refund_requests`，审核通过时经 OA 后端调用 `GambitServer` 内部接口 `/microapp_api/admin/refund/v1/approve` 发起微信退款；拒绝时调用 `/microapp_api/admin/refund/v1/reject` 写入审核备注。


## 门店资产结算

储值、月卡、积分批次账、OA 核对与期初迁移见 [`settlement.md`](./settlement.md)。这不是普通微信营业收款的完整月结报表；上线必须完成期初并同时启用 Go/OA。
