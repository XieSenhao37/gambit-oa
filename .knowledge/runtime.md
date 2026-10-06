# 运行与部署

## 后端本地运行

后端入口是 `backend/run.py`：

```bash
cd backend
python run.py
```

开发模式监听 `0.0.0.0:8080`，Flask app 由 `app.create_app()` 创建。创建时会：

- 加载 `app.config.Config`。
- 初始化 `SQLAlchemy`。
- 执行裸 `CORS(app)`。
- 注册 `main` 与 `/admin_api` API 蓝图。
- 在非 Werkzeug reloader 子进程场景下执行一次 `SELECT 1` 测试数据库连接。

## 后端环境变量

`backend/app/config.py` 通过 `python-dotenv` 读取 `backend/app/.env` 路径派生出的 `.env` 文件。当前 `BASE_DIR = backend/app` 的上级，即 `backend/`，所以期望文件是：

```text
backend/.env
```

关键变量：

- `DATABASE_URL`：SQLAlchemy 数据库连接串，通常为 MySQL/PyMySQL URL。
- `JWT_SECRET`：配置类中存在，但当前实际 JWT 工具没有使用它。
- `SECRET_KEY`：Flask `SECRET_KEY`，未配置时默认 `dev`。

注意：`backend/app/utils/jwt.py` 里硬编码 `JWT_SECRET = '<JWT_SECRET: 从环境变量配置>"”'`，实际签发与校验 JWT 都使用该硬编码值，而不是 `Config.JWT_SECRET`。

## 后端依赖

`backend/requirements.txt` 固定/声明：

- `Flask==3.0.0`
- `Flask-SQLAlchemy==3.1.1`
- `Flask-CORS==4.0.0`
- `PyJWT==2.8.0`
- `PyMySQL==1.1.0`
- `cryptography==41.0.7`
- `python-dotenv==1.0.0`
- `pycryptodome`

## 一键 Docker 部署

现在推荐使用仓库根目录的单镜像部署方式，与 `gambit_ims` 的部署思路一致：

```text
浏览器 -> http://服务器公网IP:8080 -> gambit-oa 容器
```

根目录新增：

- `Dockerfile`：多阶段构建，先构建前端，再把 `frontend/dist` 拷贝到后端镜像 `/app/static`。
- `build.sh`：构建并推送镜像到 `ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`。
- `deploy.sh`：拉取镜像、删除旧容器、启动新容器，默认暴露 `8080:8080`。
- `.env.example`：服务器环境变量模板。

镜像构建：

```bash
bash build.sh
```

服务器部署：

```bash
bash deploy.sh
```

默认访问地址：

```text
http://<服务器公网IP>:8080
```

部署脚本默认读取：

```text
/opt/gambit-oa/.env
```

可覆盖：

```bash
ENV_FILE=/path/to/.env HOST_PORT=18080 bash deploy.sh
```

## 新 Dockerfile 结构

根目录 `Dockerfile`：

- `node:20-alpine` 阶段：
  - 启用 `pnpm@9.15.9`
  - `pnpm install --frozen-lockfile`
  - `pnpm build`
- `python:3.11-slim` 阶段：
  - 安装 `backend/requirements.txt`
  - 复制 `backend/app` 和 `backend/run.py`
  - 复制前端构建产物到 `/app/static`
  - 使用 `gunicorn -w 4 -b 0.0.0.0:8080 run:app`

Flask 在生产镜像中同时负责：

- `/admin_api/*`：管理后台 API
- `/login`、`/orders`、`/games`、`/users`：SPA fallback 到 `index.html`
- `/umi.js`、`/umi.css`、`/favicon.ico`、`/static/*`：前端静态资源

## 历史后端 Docker 与 uWSGI

`backend/Dockerfile` 是历史后端单独部署方式：

- 基础镜像：`tiangolo/uwsgi-nginx-flask:python3.9`
- 工作目录：`/app`
- 环境变量：`FLASK_APP=run.py`、`FLASK_ENV=production`、`PYTHONUNBUFFERED=1`、`PYTHONPATH=/app`
- 安装 `requirements.txt`
- 复制 `uwsgi.ini`
- `EXPOSE 8080`
- 启动命令：`uwsgi --ini /app/uwsgi.ini`

`backend/uwsgi.ini`：

```ini
[uwsgi]
module = run:app
master = true
processes = 4
socket = :8080
chmod-socket = 660
vacuum = true
die-on-term = true
```

风险点：这里使用 `socket = :8080`，这是 uWSGI 协议 socket，不是普通 HTTP socket。新的根目录 Dockerfile 已改用 gunicorn 直接提供 HTTP 服务，部署时优先使用根目录 Dockerfile。

## 前端本地运行

前端使用 pnpm，`frontend/package.json` 脚本：

```bash
cd frontend
pnpm install
pnpm dev
```

脚本含义：

- `dev`: `max dev`
- `build`: `max build`
- `postinstall`: `max setup`
- `setup`: `max setup`
- `start`: `npm run dev`

## 前端代理与构建

`frontend/.umirc.ts` 配置：

- layout 标题：`Gambit后台管理系统`
- 路由：`/login`、`/` 重定向 `/orders`、`/orders`、`/games`、`/users`
- 业务路由统一使用 `@/wrappers/auth`
- `proxy['/admin_api'].target = 'http://127.0.0.1:8080'`
- `mock = false`
- `request.dataField = 'data'`
- `npmClient = 'pnpm'`

开发环境下前端请求 `/admin_api/**` 会代理到本地后端 `127.0.0.1:8080`。生产构建由 `pnpm build` 调用 `max build`，最终部署时需要让同源或网关路径能转发 `/admin_api` 到 Flask 服务。


## 用户确认的发布分工（2026-09-19）

- Codex 在 OA 根目录执行 `bash build.sh`，构建并推送 `ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`；用户登录服务器更新容器镜像。不要将镜像推送完成记作线上容器更新完成。
- 小程序后端测试发布：将 GambitServer 代码提交并推送到 `dev_rex` 分支，触发自动部署。


## 手机登录与权限切换部署（2026-09-26）

本地实现不等于已部署。以下为短信模式部署步骤；当前临时账号入口以文末「2026-09-27 临时固定账号登录」为准。

1. 在明确批准的目标库执行 `backend/migrations/20260926_staff_access.sql`，这是新增表迁移，不会自动给旧员工授权。先备份并核对目标环境。
2. 在服务器安全配置 `OA_AUTH_SECRET`（至少 32 位随机值）及 `.env.example` 中的 `TENCENT_SMS_*`。短信模板固定有效期 5 分钟，仅一个参数：六位验证码。资质审核后还需完成签名和模板审核。
3. 使用显式 `DATABASE_URL` 执行 `python scripts/bootstrap_staff.py --user-id <已核实用户ID>`，隐藏输入经人工核实的登录手机号。已有员工账号则拒绝重复初始化。此脚本不调用短信、不执行迁移、不合并顾客资产。
4. 首位总部管理员完成短信登录后，逐一确认其他员工的真实用户、登录手机号和门店角色。不要从旧全局 role 推断所有门店授权。
5. Go 服务和小程序同步上线共享授权。迁移前的旧员工不会自动获得新员工权限，必须先完成分店授权再切换；停用不影响顾客资产。
6. 验证 A 店店员/B 店店长、跨店订单ID访问、停用撤权、验证码重放、门店切换、页面撤权、退出会话。真实短信联调和生产发布须明确授权。

本地验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests` 使用 SQLite 隔离数据；赛事 MySQL 专项默认跳过。`pnpm build` 仅前端本地构建，根目录 `build.sh` 含镜像推送，不是本地检查命令。

页面目录来源为 `backend/app/security/pages.json`；Docker 构建复制同一目录供前端构建使用。后端镜像同时包含初始化脚本和迁移文件。

验证记录（2026-09-26）：OA 前端 TypeScript 检查与生产构建通过；后端发现 43 个测试，38 个通过、5 个依赖环境的测试跳过。Go 员工中间件、授权规则与留言权限测试通过，全包编译通过（编译检查不执行测试）。小程序 TypeScript 及 3 组共 16 个相关测试通过。隔离页面已验证未配置短信状态、跨店角色展示、页面权限矩阵和退出登录。未进行真实短信、MySQL 并发及微信真机联调，未部署或变更线上数据。

腾讯云实现使用短信 v20210111 SendSms，参数规范：https://cloud.tencent.com/document/api/382/55981 。验证码模板需与单参数实现一致，不要把密钥写入前端或提交到仓库。

## 2026-09-26 测试阶段补充

用户授权广州测试库新增授权表，并把手机号 13380938170 对应的现有小程序用户设为总部管理员。执行入口：`backend/.venv/bin/python backend/scripts/migrate_staff_test.py --env-file /安全路径/test.env`。凭据文件仅需 DATABASE_URL；入口固定校验测试主机、端口和库名，先保存结构，手机号非唯一匹配即停止，建表后验证字段再初始化管理员。不修改用户余额等资产。

历史方案（2026-09-27 已移除，不再使用）：测试部署设置 `OA_ENV=test`、`OA_TEST_LOGIN_ENABLED=1`、`OA_TEST_LOGIN_PHONE=13380938170`、`OA_TEST_LOGIN_UNTIL=<UTC 无时区后缀的 ISO 到期时间>`，并配置随机 `OA_AUTH_SECRET`。免验证码只允许该已启用总部账号；正式数据库或关闭开关时始终拒绝。审核完成后关闭开关并启用短信配置。登录会话固定 15 天；过期或失效返回 401，前端清理 token、明确提示并回登录页，成功登录后清除提醒。

测试库连接信息的已有记忆位于 `GambitServer/.knowledge/runtime.md` 的数据库环境章节：广州测试主机、21085、root、gambit 已保存。密码按既有约定由终端隐藏输入，不要求用户重新提供整套配置。员工迁移脚本不传 `--env-file` 即使用这套固定测试地址并提示密码；临时密码不持久化。

## 2026-09-26 员工授权测试库迁移结果

用户执行 `migrate_staff_test.py` 成功；已核验本地 `gambit-staff-test-migration-5dovg6r0/status.json`：`status=completed`、`environment=test`，7 张授权/登录表已完成，指定手机号绑定 `admin_user_id=1`，`admin_changed=true`。日志中的 ORM 关系及 utcnow 弃用警告不影响本次成功状态。结构及记录保存在 `/var/folders/tr/cdkzbb650zn6rycwddq9cnc80000gn/T/gambit-staff-test-migration-5dovg6r0`。

历史部署记录（旧免短信开关已失效）：部署本次镜像到测试环境时，DATABASE_URL 必须指向广州测试库，GAMBIT_SERVER_BASE_URL 及内部调用凭据必须匹配测试后端。设置 OA_ENV=test、OA_TEST_LOGIN_ENABLED=1、OA_TEST_LOGIN_PHONE=13380938170、OA_TEST_LOGIN_UNTIL=2026-10-11T15:59:59（UTC）以及至少 32 位随机 OA_AUTH_SECRET。不要改用正式库来绕过测试库约束。测试免短信到期后需要关闭开关接入短信，或明确延长测试窗口；已签发会话按 15 天到期。

OA 镜像于本轮经 `bash build.sh` 构建并推送成功：`ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`，仓库摘要 `sha256:f97c137f607867324a318c91b0877e8d6f1a9ec77433f44c4ee2ef7667db3526`。镜像内禁网 SQLite 测试完成（44 项，5 项跳过）；未操作服务器容器，用户负责部署。Dockerfile 已修复安装生命周期运行菜单同步脚本时所需文件的复制顺序。

2026-09-26 测试免短信入口补充（2026-09-27 已移除）：默认 OA_ENV=auto，在精确匹配广州测试主机、21085、gambit 时，允许手机号 13380938170 的已启用总部账号免短信登录，默认截止 UTC 2026-10-11T15:59:59。不再要求为此额外设置 OA_AUTH_SECRET（正常短信仍需）。显式 OA_ENV=production 或 OA_TEST_LOGIN_ENABLED=0 会关闭该入口；其他数据库默认关闭。既有容器若配置了禁用值，需删除禁用值或按上文设置测试开关。

恢复一级分组、更新 GAMBIT-01 标准 Logo 及用户确认业态/slogan 的 OA 镜像已构建推送：`ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`，摘要 `sha256:9dd89fe5cb1d2995974d88f5316173032fcd7c9d15c19a11603b3b655784be55`。已验证菜单权限过滤、浏览器分组展示、OA 类型/构建、小程序类型/构建及 14 项开屏测试；容器部署仍由用户完成。


## 2026-09-27 临时固定账号登录

- 用户要求短信审核期间只使用固定 `admin` 账号，密码仅在后端 `app/security/login_mode.py` 校验，不进入前端包或日志。默认 `OA_LOGIN_MODE=password`，`deploy.sh` 支持同名环境变量；旧 `OA_ENV` / `OA_TEST_LOGIN_*` 入口已移除。
- 不绑定顾客手机号，不写入共享员工角色，临时 OA 超级管理员保留身份 ID 0（小程序真实用户 ID 为正数）。使用现有 `oa_sessions`、限流和审计表，无新增数据库迁移。目标库仍需已有员工授权迁移表。
- 登录后可访问全部门店和所有页面，包括员工及门店授权管理。会话有效期固定 15 天，退出撤销会话；过期/失效明确提醒并跳转登录页。密码错误单独提示，不误报登录过期。
- 短信模式的资格校验、验证码摘要、限流、一次性验证、员工权限和门店隔离全部保留。审核完成后配置 `OA_AUTH_SECRET`、`TENCENT_SMS_*`，设 `OA_LOGIN_MODE=sms` 并重启服务；固定密码入口和已签发的临时管理员会话随即失效。配置不完整时明确提示，不回退到密码或免验证码入口。
- 本次未部署、未执行共享库迁移、未调用真实短信。构建命令 `pnpm build` 仅验证前端产物，根目录 `build.sh` 会推送镜像，需按发布范围单独执行。
- 本轮验证：后端 72 项（64 通过、8 项因外部/MySQL 环境要求跳过），前端 TypeScript 与生产构建通过；已核对前端产物不包含固定密码。本地隔离浏览器确认错误密码提示、登录后管理页权限、退出、过期跳转，以及切换到短信模式后的手机号验证码界面。


### 2026-10-02 桌游图片保存与用户列表排查

- 桌游新增/编辑包含同步 COS 上传，原前端 10 秒及 Gunicorn 默认 30 秒限制均过短：上传保存请求独立等待 120 秒，worker 超时 150 秒。
- 表单先校验再上传；单文件读取限 5MB+1；提交锁防止连续点击，保存期间禁用关闭和编辑；网络异常保留表单，不自动重发 POST，提示先核对列表。
- 用户列表本地隔离库及用户本地均不能复现线上 500，尚未确认原因；未猜测修改查询。页面改为明确失败提示及重试，删除查询参数 console 输出（含手机号筛选信息）。再次出现需服务端 Traceback。
- SQLite 回归 `tests.test_oa_loading_and_games` 不访问真实 COS/数据库，覆盖用户分页排序、门店隔离、字段校验先于上传、上传失败不建记录、封面/详情保存。


### 2026-10-02 桌游图片预上传优化

- GameLibrary 选择图片后浏览器压缩（最长边 1600px，JPEG quality 0.82，PNG/WebP 保持透明，GIF 不转换；输出变大则保留原文件），调用带 game-library 权限的 `POST /admin_api/game/v1/library/image`，单张仍限 5MB。
- 图片队列最多同时两张；显示 Upload 状态与进度；删除/关闭中断客户端请求。上传失败图片需移除重选，图片未全部上传成功前不能保存。
- 新表单只提交 CoverUrl/PictureList；保存不再重复传 CoverImage/PictureImages。后端保留旧文件提交兼容，无数据库迁移。提前上传的图片不创建桌游记录；放弃表单时不会新增桌游，也不自动删除 COS 文件。
- 验证：`node scripts/test-game-image.cjs` 覆盖尺寸、动画/透明、输出变大保留、并发上限及失败释放队列；`tests.test_oa_loading_and_games` 覆盖上传权限/格式、上传不建记录、URL 保存不再上传。


### 2026-10-02 用户列表日期兼容及故障定位

- users list 的月卡到期/创建/更新时间统一格式化，兼容 PyMySQL 将零日期/无效 DATETIME 返回字符串的情况；无效日期返回空值，不因一行旧数据使全页500，不修改数据库原值。
- 用户列表异常返回 ErrorId，并记录异常类型、数据库错误码及 traceback 文件/行/函数，不记录原始异常文本或SQL参数。前端保留失败提示，展示错误编号便于对应日志，不再重复弹英文通用错误。
- 本地隔离测试验证零日期与日志脱敏。截图里的线上500尚无服务器Traceback，不能据此认定根因就是零日期；仍须核验部署后的错误编号/日志。未构建或推送 Docker 镜像。
