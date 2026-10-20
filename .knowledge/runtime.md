# 运行与部署

### 2026-10-21 OA 新版本检测与主动刷新提示

- 全局 `VersionUpdate` 包含登录页：页面可见时每60秒检测，切回页面／获得焦点／恢复联网时立即检测；并发及短时间重复事件合并。相同新版只提醒一次，选择“稍后”后保留“发现新版本”小入口；不同新版重新提示，服务器回滚到当前页面版本则撤销提示。
- 提示“新版本已准备好”，用户点“立即刷新”后先确认正在编辑的内容已保存，再重载当前地址。所有刷新均经过保存确认，不猜测各业务表单是否已保存、不自动保存草稿；取消保持输入。不清除登录token或门店偏好，不自动强制刷新。
- `pnpm build` 在HTML写入随机 `oa-build-version` 元标识，`scripts/write-version.cjs` 从同一份HTML生成 `dist/version.json`；两者必须一致，缺失标识则构建失败。前端读取页面已载入的标识，与公开的 `/version.json` 比较。每次前端构建自动生成，不需要人工改版本号；后端单独更新且复用同一前端构建时无需提示浏览器刷新。
- 版本请求使用原生fetch、no-store、10秒超时，不进入业务接口的登录过期及错误提示处理；旧环境无版本文件、断网和解析失败静默等待下一次检查。Flask版本文件返回 `no-store, no-cache, max-age=0`，不返回304；文件不存在返回404，不回退为SPA网页。HTML原有重新验证及带hash资源长缓存策略保持。
- 首次接入前已打开的旧页面需刷新一次才能加载检测器。本次已刷新用户当前测试页，原手机号总部管理员会话保留，员工与权限页读取正常。
- 验证：版本监控专项 `node frontend/tests/versionMonitor.cjs` 覆盖识别、重复抑制、隐藏暂停、恢复、回滚、离线、超时、卸载及构建标识；4项静态资源／版本缓存测试在本机和禁网amd64镜像通过；TypeScript及前端构建通过。本机真实构建资源配合只读SQLite服务模拟发布，已检查提示、稍后入口、取消后输入保留、确认才刷新、新版不再提示，以及375px窄屏；模拟服务已关闭，无共享业务写入。
- linux/amd64镜像 `sha256:eaba63c6e33c2d9875cb61c137c92e76eba56afa23fd43ae820997bdce2f1f8a` 已推送并实际部署到 `gambit-oa-test`，健康通过，生产容器不变。测试公网构建标识 `fcdaa4a70fb1ab66c93eb5a35b7e4494` 与HTML一致，缓存头、条件请求仍返回200、短信登录及已有会话保留均核验通过。未修改Go、小程序、权限或共享业务数据。

### 2026-10-21 测试环境启用手机号验证码登录

- 用户明确授权将 OA 测试环境切换为手机号验证码登录，并确保尾号 8170 的现有账号为最高权限管理员。已核验该账号原本即为 enabled=true、headquarters=true、user.role=126，无需新增账号或修改其他员工；总部权限可管理全部有效门店和所有注册页面。
- `gambit-oa-test` 已设置 `OA_LOGIN_MODE=sms`；公网 `/admin_api/auth/v1/status` 返回 SmsReady=true，旧 admin 密码入口返回400，旧临时管理员会话按既有守卫失效。正式容器 ID、镜像及启动时间与操作前完全一致，未变更生产配置。
- 短信使用云 API 3.0／v20210111，复用测试服务现有 COS 云 API 凭据（已验证短信权限），无需旧版 AppKey。SdkAppId=`1401200063`，签名 ID=`724208`、发送时使用已审核的签名内容，模板 ID=`2741113`。模板两个参数依次为六位验证码及有效分钟数；短信文案与服务端校验统一5分钟。SDK请求超时10秒。
- 测试部署配置保存在服务器 `/root/gambit-oa-codex-test/.env.deploy.local`，权限600；凭据仅在服务器内复制至短信配置，`OA_AUTH_SECRET` 在服务器生成，不写前端、仓库、镜像或聊天。部署脚本完整传递短信变量并在替换容器前校验必填配置；切换前配置和部署脚本备份于同目录 `sms-login-backup-*`。
- 已构建并推送 linux/amd64 镜像，实际部署摘要 `sha256:e7fc1234f2e6093b891c7d711cb4bbad7d8e0927b01a15cf6816467495471950`。`scripts/deploy-test-server.py` 核验指定摘要、健康及生产容器未变通过。无 Go 或小程序修改，无数据库迁移、库存、资金或其他业务数据变更。
- 本地与实际amd64镜像中28项短信适配／员工权限／登录模式测试通过（SQLite、模拟发送；镜像测试禁网）。实际浏览器通过测试OA页面获取验证码，重发倒计时正常，使用用户提供的验证码成功进入工作台并打开总部专属员工与权限页，账号显示“启用／总部·全部门店”。验证码、会话token和密钥不记录到文档。

### 2026-10-12 月卡独立发布正式环境

- 用户明确授权只发布月卡，并随后要求先把正式已有的桌游计价与加载优化提交主分支。隔离分支基于 origin/master 拆分为 `3880897`（补回已上线基线）及 `822af6a`（总部独立多选开卡页），均已推送 master；原 dev_rex 和租借开发改动保留，没有提交或发布租借代码。
- 基线后端51个Python/JSON文件与原正式逐文件SHA256一致，最终后端仅月卡接口及页面权限目录不同。包含时间整秒精度修复，防止MySQL时间舍入导致首次响应与重试相差一秒。
- 本机后端217项中157项通过、60项按环境跳过；专用本机MySQL并发5项通过，TypeScript/前端构建通过。最终amd64镜像内52项禁网SQLite测试通过。
- 镜像标签 `month-card-822af6a` 和 `latest` 已推送，摘要 `sha256:b0a6eea087433023f34bccc58cba5a4c4ad4876a9ef95bc699a74d3735bfc130`。BuildKit直接推送遇令牌错误，沿用build.sh的先load再docker push方式完成。
- 正式容器 `gambit-oa` 已更新，实际内容ID `sha256:c78cda8528c6f8f7c69fb3925e685163d636088f2ccc1803895e0ff49457666e`，健康状态healthy。正式数据库/Go地址、原环境变量、登录及结算开关完全保留。先用127.0.0.1:28080候选验收再切换；月卡资源gzip/缓存、计价入口、登录守卫、用户列表只读查询通过。无迁移、无真实开卡或支付。
- OA正式入口 `http://49.232.4.107:8080/month-card-open`，公网HTML及新脚本HTTP200、脚本Content-Type和gzip正确。无端口80入口属于独立IMS容器gambit，未改动。原正式容器保留为 `gambit-oa-rollback-822af6a`；测试容器ID、镜像及启动时间保持不变。

### 2026-10-12 月卡金额展示隐藏已部署测试

- 按截图隐藏开卡页每期价格、每人承担金额、总部承担总额及常驻重新读取；确认弹窗与成功提示也不显示金额。后台仍读取并校验配置价，原开卡/总部结算逻辑不变，读取失败保留错误区重试。
- TypeScript与前端构建通过，本机SQLite虚构用户验证选择2人、2期、无金额确认及成功到期结果，无脚本错误；本机临时服务已清理，没有共享用户权益写入。
- linux/amd64 镜像 `sha256:2e5ed649fe1dfa9ce88be0b0eea6b3b9c62959af7a8de7083824c37e77cda430` 已推送并部署 gambit-oa-test。实际镜像、health=healthy、生产容器保持不变核验通过；测试页和新资源HTTP200，线上月卡页面资源已核验不含指定金额字段及重新读取入口。

### 2026-10-12 开通月卡独立页与多选已部署测试

- 入口改为基础管理下“开通月卡”，仅总部可见；用户列表不再显示逐行开卡操作。弹窗支持用户ID/昵称/完整手机号搜索、跨页多选最多100人，统一期数和总部配置价。
- 批量事务、防重和整批失败回滚；页面保存待确认请求，响应丢失后刷新仍用原编号重试。无需迁移、无Go变更，未修改共享用户权益。
- 57项SQLite相关回归、5项本机MySQL并发测试、TypeScript与前端构建通过。25位本机虚构用户浏览器验证跨页/搜索选择、金额联动、批量成功和响应丢失后刷新重试；隔离服务器/临时MySQL已清理。
- 最终 linux/amd64 镜像 `sha256:d7372ab614a1b9d65b52cf3e4af94fd08f321d5fb4e2d212a72a19d38da4c92a` 已推送并自动部署 gambit-oa-test；实际镜像及health=healthy、生产容器保持不变核验通过。测试 /month-card-open 和新异步页面资源HTTP200，未登录批量开通HTTP401。测试入口 http://49.232.4.107:18080/month-card-open。

### 2026-10-12 用户列表 MySQL 排序规则冲突修复

- 截图 ErrorId `8f326476110d` 已匹配 gambit-oa-test 脱敏日志，异常 OperationalError/database_code=1267；同一容器另一编号 c13de17df80f 同类失败。只读元数据确认 users/point_accounts/pay_orders/play_orders/caterings.open_id 为 utf8mb4_0900_ai_ci，wallet_accounts.open_id 为 utf8mb4_unicode_ci。
- 用户列表直接关联 User.open_id 与 WalletAccount.open_id 时出现非法混合排序规则；测试库只读对比确认旧关联1267、显式 COLLATE 后成功。`backend/app/api/v1/user.py` 仅在 MySQL 查询中将用户侧表达式 COLLATE utf8mb4_unicode_ci，保留钱包列原样供索引查找；SQLite不使用MySQL专用规则。无共享表结构/数据修改，不通过吞异常或将余额置零掩盖失败。
- 新增 `backend/tests/test_user_list_mysql.py`，仅允许 USER_LIST_TEST_URL 指向127.0.0.1:33319/gambit_user_list_test；4项通过，覆盖旧查询1267复现、余额/消费金额、排序分页、门店隔离与软删除账户。另22项用户列表及月卡回归通过。此前SQLite同规则测试未覆盖历史MySQL表混合规则，不能再以SQLite通过代替该专项。
- linux/amd64 镜像 `sha256:54c5750d6985a310bf76aa127a5504e8fadc233d03d7cb811b1b03cdc37df178` 已构建推送并自动部署 gambit-oa-test；实际镜像、health=healthy、生产容器保持不变核验通过。部署后在测试库只读事务调用实际列表业务查询，默认列表/储值余额排序/积分余额排序均 HTTP200/Code0，未输出顾客信息或创建登录记录。本机一次性MySQL已清理。
- 只读排障范围限已授权测试容器；生产容器日志读取被自动审批拒绝，未重试读取生产日志。没有读取或输出顾客明细及密钥。

### 2026-10-12 用户随后授权正式环境只读检查

- 用户明确要求检查正式环境是否有同类问题，该授权覆盖正式OA日志、列排序规则元数据和只读查询，不包括生产部署/表结构/业务数据修改。此次获授权后才读取 gambit-oa，前条审批拒绝并未绕过。
- 再次 `deploy-test-server.py --digest sha256:54c5750d6985a310bf76aa127a5504e8fadc233d03d7cb811b1b03cdc37df178 --check`，测试容器实际镜像及health=healthy通过。
- 正式目标核对为上海正式库 gambit:22120。users、wallet_accounts、point_accounts、pay_orders、play_orders、caterings 的open_id均为 utf8mb4_0900_ai_ci；正式当前代码未包含本轮显式COLLATE修复，但不存在测试库的混合规则。
- 正式只读事务、单条查询5秒上限下，运行部署版本的实际用户列表业务查询，默认/储值余额排序/积分余额排序均HTTP200、Code0、响应结构正确；不输出用户行、不创建登录记录。现存近7天日志没有user_list_failed记录，不能据此宣称所有生产功能无故障。
- 正式容器仍运行原镜像 sha256:88d519ce0eeb01af116922884830a3a3878c70704b74a020a3e8a0dee0f3e41a，启动时间2026-10-07T11:07:24.343112553Z；本次不部署、不改表、不改业务数据。

2026-10-12 总部月卡兜底开通已部署 OA 测试容器：linux/amd64 镜像 `sha256:3ba11dfaa6d5fd7cee1dd3eacbfb8179ad3d87eb247c9b65564d942fac8bdd63`，实际镜像及 health=healthy 核验通过，生产容器保持不变。用户列表总部可用“开通月卡”，费用按配置价由总部承担，不伪造现金收款；无需原因/凭证，保留自动基础审计。40项相关隔离测试、TypeScript及生产构建通过，本机虚构用户页面交互通过；无迁移、无Go变更、无共享业务数据写入。详见 settlement.md 对应日期章节。

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

- Codex 在 OA 根目录执行 `bash build.sh`，构建并推送 `ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`；Codex 经用户授权自动更新 OA 测试容器并检查镜像与健康状态，详见下方长期连接约定。不要将镜像推送完成记作容器更新完成。
- 小程序后端测试发布：将 GambitServer 代码提交并推送到 `dev_rex` 分支，触发自动部署。


### 长期自动发布授权（2026-10-07）

用户明确要求：后续相关改动完成实现和必要验证后，自动执行以下发布准备，无需逐次询问。

- OA 有改动：构建 linux/amd64 镜像并推送到 `ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`，允许上传本项目镜像并更新该标签；完成 SSH 凭据配置后，由 Codex 自动更新已授权的测试环境 OA 容器并检查健康状态。
- Go 后端有改动：将本次改动提交并推送到 `GambitServer` 的 `origin/dev_rex`，触发测试环境自动部署。核对分支并保留已有无关改动，不制造空提交。
- 同时涉及 OA 与 Go 时，完成两项流程，不在仅本地实现或构建后停止。报告镜像摘要、Go 提交及可核验的部署状态；推送成功不代表容器已部署成功。
- 本授权不包含生产容器部署、共享/生产数据库迁移或数据写入、真实支付退款，以及新增付费调用。

### OA 测试服务器长期连接（2026-10-07）

- 用户授权后续直接连接 `root@49.232.4.107:22`，执行 OA 测试部署。当前采用密码登录，密码保存在用户本机 macOS 钥匙串，不写聊天、Git、Docker 镜像或明文配置。
- 用户在本机运行 `python3 scripts/setup-test-server-access.py` 隐藏录入一次；钥匙串 Service 为 `codex.gambit-oa.test.ssh`，Account 为 `root@49.232.4.107:22`。用户录入后后续直接复用，除非凭据失效或授权被撤销。不要自行删除持久钥匙串项。
- `scripts/ssh-askpass-test-server.sh` 只能作为 `SSH_ASKPASS` 使用，不可直接执行并打印密码。SSH 使用 `SSH_ASKPASS_REQUIRE=force`、`DISPLAY=codex`、`PreferredAuthentications=password`、`NumberOfPasswordPrompts=1`、`StrictHostKeyChecking=yes`；不使用会跳过密码认证的 `BatchMode=yes`。输入重定向 `/dev/null`，不打开密码日志或 `set -x`。
- `.env.remote-test.local` 仅保存连接元数据和待核实的 OA 目录；该文件被 Git 和 Docker 忽略。接入已完成：独立测试部署目录为 `/root/gambit-oa-codex-test`，测试容器 `gambit-oa-test`，端口 18080，广州测试库 `gambit:21085`，Go URL 为 test-golang。服务器原 `/root/deploy.sh` 与配置保留。自动部署目录的配置直接在服务器内继承现有配置，不传回本机。
- OA 镜像推送成功后，执行 `python3 scripts/deploy-test-server.py --digest sha256:实际推送摘要`，自动 SSH、校验部署脚本和有效配置、拉取指定摘要镜像、更新测试容器、验证镜像及 `/health`。`--check` 仅检查。按摘要部署避免 `latest` 标签变动；相同镜像内容且容器运行时跳过重启并验证健康。
- `deploy.sh` 支持 `DEPLOY_IMAGE` 指定摘要；自动部署仅允许该服务器、测试容器、18080 端口和已核实测试库/Go 目标，拒绝不匹配配置。核对生产容器 ID、镜像及启动时间不变，不打印配置秘密。远程部署脚本与本地哈希不一致时停止，保留已有文件，先核对并同步测试目录的脚本再继续。
- 只允许 OA 测试部署，不包含生产部署、数据库迁移或业务数据修改。本机临时密码文件在钥匙串录入完成后清理。

## 手机登录与权限切换部署（2026-09-26）

以下保留短信模式的部署准备步骤；当前测试环境状态以文首「2026-10-21 测试环境启用手机号验证码登录」为准，历史临时账号机制见「2026-09-27 临时固定账号登录」。

1. 在明确批准的目标库执行 `backend/migrations/20260926_staff_access.sql`，这是新增表迁移，不会自动给旧员工授权。先备份并核对目标环境。
2. 在服务器安全配置 `OA_AUTH_SECRET`（至少 32 位随机值）及 `.env.example` 中的 `TENCENT_SMS_*`。当前已审核短信模板为两个参数：六位验证码、有效分钟数（5）；服务端有效期同为5分钟。资质审核后还需完成签名和模板审核。
3. 使用显式 `DATABASE_URL` 执行 `python scripts/bootstrap_staff.py --user-id <已核实用户ID>`，隐藏输入经人工核实的登录手机号。已有员工账号则拒绝重复初始化。此脚本不调用短信、不执行迁移、不合并顾客资产。
4. 首位总部管理员完成短信登录后，逐一确认其他员工的真实用户、登录手机号和门店角色。不要从旧全局 role 推断所有门店授权。
5. Go 服务和小程序同步上线共享授权。迁移前的旧员工不会自动获得新员工权限，必须先完成分店授权再切换；停用不影响顾客资产。
6. 验证 A 店店员/B 店店长、跨店订单ID访问、停用撤权、验证码重放、门店切换、页面撤权、退出会话。真实短信联调和生产发布须明确授权。

本地验证：`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests` 使用 SQLite 隔离数据；赛事 MySQL 专项默认跳过。`pnpm build` 仅前端本地构建，根目录 `build.sh` 含镜像推送，不是本地检查命令。

页面目录来源为 `backend/app/security/pages.json`；Docker 构建复制同一目录供前端构建使用。后端镜像同时包含初始化脚本和迁移文件。

验证记录（2026-09-26）：OA 前端 TypeScript 检查与生产构建通过；后端发现 43 个测试，38 个通过、5 个依赖环境的测试跳过。Go 员工中间件、授权规则与留言权限测试通过，全包编译通过（编译检查不执行测试）。小程序 TypeScript 及 3 组共 16 个相关测试通过。隔离页面已验证未配置短信状态、跨店角色展示、页面权限矩阵和退出登录。未进行真实短信、MySQL 并发及微信真机联调，未部署或变更线上数据。

腾讯云实现使用短信 v20210111 SendSms，参数规范：https://cloud.tencent.com/document/api/382/55981 。验证码模板需与当前两参数实现一致，不要把密钥写入前端或提交到仓库。

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

自动测试部署接入验证（2026-10-07）：钥匙串 SSH 登录、部署配置校验、摘要镜像拉取与容器版本核对、18080 `/health` 均通过。当前验证摘要 `sha256:98c7e2df2b194db3010dd8778683a0b21916aca0b28615afb20bb401486a6917`；相同镜像内容已运行，完整部署流程跳过重启。生产容器 ID、镜像及启动时间保持不变，未执行数据库迁移或业务数据写入。

2026-10-07 计价表单澄清：改为全天封顶／优惠时长后续时、常规价格草稿、实时收费示例及可选星期（缺省周五至周日）。Go 测试分支提交 `66c0d78` 已推送，云托管部署完成状态未独立核验。Go 计价测试与全仓编译、OA 9 项 SQLite 测试、前端转换验证/TypeScript/生产构建及隔离浏览器方案切换检查通过。OA 镜像摘要 `sha256:071eedaf1a951f416a408c69cc20bba6ca098cc247f3a55a0d1f70292c499126` 已自动部署 `gambit-oa-test`，版本与 `/health` healthy 核对通过，生产容器保持不变。未修改 MySQL 表结构或共享库价格。

2026-10-07 计价管理 UI 优化：按用户要求移除基础价格的说明段落和 1/2/3/4/6 小时示例；基础价格并列卡片、星期选项与补班开关、灵活定价四个标签页、独立试算、未保存状态及底部保存条统一样式。日期字段改为日期选择器，保留 API 的 YYYY-MM-DD 字符串格式。所有编辑标签页 forceRender，保存读取完整草稿；试算请求失效校验避免改价后显示过期结果。类型检查、前端构建、既有价格转换验证、隔离浏览器新增时段/日期批量调整/指定日期优先试算/跨标签页保存均通过。镜像 `sha256:a5a2f7fa0debc7e234e649aecf58c6ed31ec87a00fba75304b6074835c1d62f6` 已自动部署至测试服务器的 gambit-oa-test；版本与 health=healthy 验证通过，生产容器保持不变，未写共享库价格。

### 2026-10-07 OA 首次加载与刷新优化

- 已核实旧测试环境：`/umi.js` 3,516,634 字节，无 Content-Encoding，Cache-Control=no-cache；本机到测试服务器下载 14.578 秒，HTML 首字节约 0.113 秒。此前生产构建的 dynamic-import-node 插件关闭路由拆包，导致登录/计价页面也包含全部业务页面和图表库。
- `.umirc.ts` 移除该插件，开启 hash 和 granularChunks，恢复按路由加载。后续保留拆包，避免再次引入将 import() 转为同步导入的插件。
- `pnpm build` 最后执行 `scripts/precompress.cjs`，为 JS/CSS 生成 gzip 文件；Flask 根据 Accept-Encoding 返回 gzip，带 Vary 和正确 MIME。不压缩 API，不变更计费算法。哈希 JS/CSS 缓存一年且 immutable；HTML 仍需重新验证，让新部署引用新文件；缺失脚本/样式返回 404，避免返回 HTML 造成脚本解析错误。
- 本地隔离浏览器冷加载：登录页 JS/CSS 301,663 字节，计价页 574,531 字节，分别比原总包 3,534,021 字节减少 91.5% 和 83.7%；计价页不加载 Dashboard 图表代码，正常刷新没有再次请求 JS/CSS。此为静态资源传输量，不能描述为完整页面交互耗时。
- 前端 TypeScript/生产构建、3 项隔离静态资源测试、真实 Flask 静态服务的隔离浏览器登录/计价直接导航与刷新检查通过。测试覆盖 gzip 协商/禁用/无 sidecar 回退、版本缓存、ETag/304、gzip 与原始文件分离、HTML 重新验证及资源缺失 404。没有访问真实业务数据库或保存价格。
- 镜像 `sha256:5d25f0a0214297170c17d31d9bbbe2e1d9ae8deccd25a9890687d856c26c6b77` 已自动推送并部署 gambit-oa-test，health=healthy、实际镜像匹配、生产容器保持不变。部署后从本机实测 HTML 0.143 秒；入口 JS/CSS 3 文件压缩后合计 228,011 字节，并行下载 0.634 秒，主 umi.js 单文件 0.629 秒（旧主文件 14.578 秒）。此数值不含页面后续动态资源、鉴权和业务 API，不能当作整页可交互时间。已验证线上 gzip、immutable/Vary、ETag 304 及登录页浏览器显示和无脚本错误。

2026-10-07 计价页页头精简：按钮改为“恢复默认价格”，提示同步改为默认价格草稿、保存后生效；移除页头“门店运营”和简介，只保留单行“桌游计价管理”，字号 22px、收紧留白。TypeScript、前端构建和隔离浏览器显示/恢复按钮检查通过，无脚本错误。镜像 `sha256:478fba73a011d3daf0cb68a111acdaa222986a2577932feb1e17d922015432b4` 已推送并自动部署 OA 测试容器，实际镜像与健康检查通过；没有保存真实价格，生产容器保持不变。

### 2026-10-07 正式 OA 保存计价误报“已停用”

用户授权只读检查正式库。只读事务确认 configs 中存在两个 PlayConfig：ID 2 的 deleted_at=2026-08-02 13:46:47，ID 6 的 deleted_at 为 NULL，后者是有效配置，包含两店 StoreMap。旧库允许保留同键历史记录，与 SQLite 模型的唯一约束假设不同。OA GET 与 Go GORM 会过滤已删除记录；OA PUT 原先不加 deleted_at 过滤，误选 ID 2 并返回 409。无需 Go 环境变量、恢复旧记录或修改正式库。PUT 已改为首先锁定有效记录；只有不存在有效记录且确有历史停用记录时才返回已停用。新增隔离 SQLite 非唯一历史表场景，验证更新有效行、其他门店与旧记录不变，10 项计价测试通过。没有执行正式数据写入。

本次修复镜像 `sha256:a1bda69119d05d77d1d081b6166d8de84d73d2265ae7be005dd82648dfbc1e58` 已推送 latest，并自动部署 gambit-oa-test，镜像及 health=healthy 核对通过。正式容器保持不变，正式 OA 需另行部署该修复镜像。只读检查脚本位于本机临时目录，使用已有私有 backend/.env，不保存或打印连接密码。


### 2026-10-08 桌游服务发布准备

三端源码已实现，待明确批准广州共享测试库的7张 game_* 空表与 pay_orders.board_game_order_id 可空关联列。只读预检确认目标为测试环境，7表及列尚不存在；自动审批拒绝迁移，未修改共享库，未更新依赖新结构的 Go/OA 服务。OA 镜像按授权构建推送仅作准备，须在迁移与 Go capabilities Ready/version 核验后才能按摘要部署。真实微信支付、退款和 COS 上传未在微信环境实际执行，生产服务及数据未更改。


发布准备完成：OA linux/amd64 镜像已推送 `ccr.ccs.tencentyun.com/gambit/gambit_oa:latest`，摘要 `sha256:f772961516021bfe7cd4e3971e5ccea550602729bf83f78a9484b8c450df43fc`。未运行 deploy-test-server.py，本次新功能未部署。迁移明确授权后仍须先核对当前 SQL 摘要，再迁移、推送 Go、验证 capabilities，最后按上述摘要部署 OA；如果其后代码有变更须重建。验证：OA TypeScript和生产构建通过，Python共205项（150通过，55环境条件跳过），Go全仓及本地MySQL并发/退款验证、小程序66项、类型/构建/包限制检查通过。真实支付退款、真实 COS 上传及微信真机交互尚未验证。


Go 已保存本地 `dev_rex` 提交 `daf87a08fd179c26e35cd1644842526e1539005e`，尚未推送（避免在缺表时触发测试自动部署）。后续获迁移授权后以此提交及上述 OA 镜像摘要为待发布版本；不得把本地提交描述为测试服务已更新。新增接口还验证批量清单真实人数、服务开关、已停用门店隐藏，以及无身份/内部令牌/缺表的访问守卫。


### 2026-10-09 用户批准桌游服务测试迁移

用户明确要求执行此前列明的测试库增量迁移。`scripts/migrate-test-game-services.py --apply` 已核验广州测试目标，并完成7张新表及 pay_orders.board_game_order_id 可空列，SQL SHA256 `af35fae8292c7d51a42bf1e9d0bd3bab866c23c2e4b02894aa983fb2b060ece6`，无业务示例数据。Go `daf87a08fd179c26e35cd1644842526e1539005e` 已推送 `origin/dev_rex`，自动部署正在核验；在 capabilities 新版本/Ready 检查通过后部署 OA 已备镜像。此处具体迁移授权只覆盖测试结构，不扩展到生产、支付退款或业务配置写入。


2026-10-09 库存快照并发补强：OA require_unallocated_inventory 从普通聚合读取改为逐行 FOR UPDATE 当前读取；Go 库存池编辑也以锁定当前读取统计待检查归还，避免旧事务快照绕过数量保护。OA 206项测试（151通过、55环境跳过）及新增隔离 MySQL 快照回归通过，Go 专项隔离 MySQL及全仓通过。最终 OA 镜像 `sha256:b94bfce9a38d6279efe490dcb77be09878313ec333bfe56231ed64b522e2626e` 已部署 gambit-oa-test，实际镜像／health=healthy／生产容器不变核验通过；最终 Go `eb563114e7dee8efd09a17d75ca2d8431c08e192` 已推送 dev_rex，capabilities2026-10-09.1待核验。本次测试库7张表仍为空，服务默认关闭，不创建真实库存或订单，不调用支付退款。


2026-10-09 最终验收完成：Go capabilities新版本2026-10-09.1返回Code0/Ready=true；最终Go提交eb563114e7dee8efd09a17d75ca2d8431c08e192、OA摘要sha256:b94bfce9a38d6279efe490dcb77be09878313ec333bfe56231ed64b522e2626e。再次只读核验OA实际镜像、health=healthy和生产容器保持不变。测试库7张新表均0行、支付关联列nullable；Go policy/stock/orders/community内部连接通过，缺令牌拒绝；OA路由登录守卫及三个异步页面资源已核验。没有启用租售或设置真实库存；微信真机、真实支付/退款与真实COS上传不包含在本次隔离及只读验收中。历史“迁移受阻/镜像仅准备”记录已被本条完成状态取代。OA测试入口为 http://49.232.4.107:18080，桌游租售管理、出租与出售清单、桌游玩家社区使用既有登录与门店权限。

2026-10-09 OA 库存批量与表单简化已部署测试：Go 提交 `dc9fead24aed596839c5981f5a3e885781d4a295` 已推送 dev_rex，capabilities 2026-10-09.2/Ready=true 已核验；OA linux/amd64 镜像 `sha256:9c1e0648af9909a85d72ed786500274033c1d51aa267fb25481d194f705056c1` 已部署 gambit-oa-test，实际镜像、health=healthy、生产容器不变检查通过。内部查询、批量空请求事务前拒绝及 OA 批量登录权限已验收；测试模块7表仍为空，未启用租售或配置真实库存，不新增数据库迁移。

验证：Go 全仓含本机隔离 MySQL；批量并发、重试、原子回滚、跨店、占用保护与同款库存重新分配回归通过。OA 207项测试（151通过，56环境跳过）、TypeScript、生产构建及 HTTP 请求编号兼容检查通过；本机内存数据页面验证多选、单项表单、自定义品相及逐款售价，未通过浏览器修改共享库存。批量最多100项，数量设置为每项绝对总量；售价逐款填写，租售总开关仍在服务规则页控制。


## 共享租售测试迁移与部署完成（2026-10-17）

用户明确确认本次测试迁移、旧配置转换以及 Go 开发分支推送。该授权覆盖 `20261017_shared_game_inventory.sql` 的2张表、13列、2个父订单索引，以及现有20条旧报价到共享额度的转换；不扩展到生产、真实支付退款或其他业务配置修改。

- 广州测试库迁移已执行并核验；SQL SHA256：`3d15ec9f6d815a0e2085e510c3af9f8ffd0a6771050336e7f6dc8bcc8864d55f`。
- 新 Go 就绪后转换成功：20组共享额度，20条旧报价保留，额度合计一致，无遗漏组；原价格与实物总数不变，租转购开关全部关闭。验收时在途订单及新退款分配记录均为0。
- Go 提交 `52823c2`、`5b7bb8cb178a31a924ab7d2e62c40b12025bcd1b` 已推送 `origin/dev_rex`。实际测试接口返回 Version=`2026-10-17.1`、Ready=true；现有配置门店的库存、订单、规则接口只读验证通过。
- OA 镜像 `sha256:59ffd4de1e5d45b8a7e48cbc03bfdd3bdd74a3c978d34936b1f809beece578f4` 已部署到 `gambit-oa-test`（18080），实际镜像和health=healthy通过；未登录访问新接口被拒绝；生产容器ID、镜像及启动时间均未变。
- 未执行真实下单、支付、退款或生产部署。小程序原有dist未改动；先前独立生产构建不能视作生产后端已配套上线。

### 2026-10-18 租售订单先确认后付款（测试部署）
- OA 订单页支持 pending_confirm，待办/汇总包含待确认订单；店员确认后留货15分钟并等待玩家付款，付款前不提供交付操作。旧 pending_accept 继续兼容。
- Go `60626b2` 已推送 origin/dev_rex；测试 capabilities `2026-10-18.1`、Ready=true 已核验。无新增迁移。
- OA linux/amd64 镜像摘要 `sha256:a4f80f909235980e03e58d5e80708f73811b9c02f0b9a85a918318fbc78a96fd` 已部署 gambit-oa-test，镜像匹配、health=healthy、生产容器不变核验通过。前端 TypeScript、镜像内构建通过。
- Go 全仓测试及隔离 MySQL 订单/退款/控制器回归通过；未在共享环境创建订单、修改库存或调用真实支付退款。


### 2026-10-18 确认后24小时付款与订阅提醒（发布准备）
- OA 订单确认提示24小时，订单详情展示真实 PaymentExpiresAt，“实付”改为“订单金额”避免未付款歧义；TypeScript及镜像内前端构建通过。
- linux/amd64 镜像已推送：`sha256:f476585a7ed2230856649a588f5e7a6c05c0ddd99468141f708b0754a93dccf1`。尚未更新测试容器，避免前后端付款期限不一致。
- Go本地dev_rex提交 `5de6c0c`，尚未推送；全仓及隔离MySQL验证通过。小程序27项相关测试、TypeScript、测试环境构建及包限制通过。
- 新提醒表SQL在相邻Go `docs/sql/20261018_game_confirmation_notifications.sql`；本机隔离库重复执行通过。`scripts/migrate-test-game-notifications.py`默认只读，目标严格限定广州测试gambit:21085。预检通过且新表不存在，SQL SHA256 `38d65a2f463eccee4b2cfe107ea0324c03cf43624c56906d2487b65f70872bdf`。已向用户请求这一张空表的迁移授权，未执行共享库DDL。
- 获授权后执行迁移、推送Go dev_rex核验2026-10-18.2/Ready，再按上方摘要部署OA。模板ID已配置，实际微信字段及枚举尚待部署后只读验证；未发送真实消息或调用支付退款。


2026-10-18 本次通知表迁移已获用户明确授权并执行完成：广州测试gambit:21085，新增game_confirmation_notifications及订单唯一索引、调度索引；既有业务数据未修改，SQL摘要与预检一致。Go功能提交5de6c0c及只读模板诊断提交418ed24已推送origin/dev_rex，正核验云端部署；模板诊断受既有内部令牌保护，不会发送通知。此前“未授权／未推送”状态由本条取代。


2026-10-18 本次部署完成：Go最终提交 `a5a51f7` 已推送dev_rex，实际capabilities=2026-10-18.3、Ready=true；内部confirmation-subscription诊断返回Code0、Ready=true。微信模板实际字段：服务名称thing1、服务项目thing2、服务阶段thing4、订单号character_string7，无备注；仅发送实际字段，截止时间由订单页展示。OA镜像 `sha256:f476585a7ed2230856649a588f5e7a6c05c0ddd99468141f708b0754a93dccf1` 已部署gambit-oa-test，health=healthy且生产容器保持不变。此前本次“待授权／待推送／待部署／待字段核验”状态均由此条取代。已验证结构、部署和模板配置；没有用真实用户执行订阅消息发送、下单、支付或退款验收。

### 2026-10-19 分享免审核

玩家分享发布/编辑后直接公开，旧 pending 按公开读取。社区页改为“玩家分享”，移除公开审批和不予公开入口；仅对已隐藏内容提供恢复展示，公开内容提供隐藏/优质评选。既有 review API 用作事后管理，权限与一次性积分规则不变。无数据库迁移。

- 2026-10-19 分享免审核测试部署已完成：Go `72b8dc6` 已推送 origin/dev_rex，实际 capabilities `2026-10-19.1`、Ready=true；其他访问者只读查询得到现有1条公开分享，状态/列表/计数一致。OA 镜像 `sha256:12ceb62a96a859e02ae96549e92ab8769c3f7b0c6c4671a38855d086eeecb805` 已部署 gambit-oa-test，实际镜像与 health=healthy 核验通过，生产容器未变。小程序42项回归、两端TypeScript、Go隔离MySQL专项和相关路由测试、两端构建通过，小程序主包2000.3 KiB。未批量改库、未创建真实测试分享、未发积分或发布生产；开发者工具点击未能进入目标页面，本轮截图验收未完成。

### 2026-10-19 社区列表汇总及视觉整理

社区页隐藏顶部门店选择，Tab 为“想玩列表”“玩家分享列表”。想玩表新增想玩门店，分享改为紧凑图文行（玩家、桌游名称、门店、日期、正文/缩略图、右侧操作），支持独立关键词/状态筛选、分页、长文展开及图片预览。移除蓝色说明横幅和重复公开标签。

GET community 使用登录会话校验，在服务器从有效门店授权计算 StoreIDs，覆盖浏览器传入的门店范围；Go统一分页。隐藏/恢复/评优和社区设置通过请求级 X-Store-ID 使用记录/配置所属门店，仍分别校验 game-community 和 game-services 权限，不改其他页面全局门店。社区设置内单独选配置门店。请求序号/清理避免旧搜索及旧设置响应覆盖新页面。

- 本次测试部署已完成：Go `ad16ec7` 已推送 `origin/dev_rex`，实际 capabilities `2026-10-19.2`、Ready=true；OA linux/amd64 镜像 `sha256:e603d2cda3a94db4e36d6dd91309b27095d17c0b8462a74f2895efcccfd4b5f4` 已部署 `gambit-oa-test:18080`，镜像匹配、health=healthy，生产容器保持不变。
- 两端相关验证通过：OA TypeScript、25项后端权限/代理测试、镜像内前端构建；Go隔离MySQL社区范围/搜索/分页/状态回归及桌游服务、控制器、路由测试。测试接口只读核验1条分享具备真实桌游/门店名；线上页面资源包含两个新Tab与“想玩门店”列。无共享库迁移、业务写入或积分发放。
- 视觉验收限制：原生Arc窗口先返回旧页面，强制刷新后截图停在布局外壳，无法通过当前自动化窗口完成分享列表及空状态的实际截图检查；不能将构建/接口通过等同于视觉验收。需要浏览器实际打开新版页面核对。


### 2026-10-19 分享爱心点赞表

用户明确授权广州测试库 gambit:21085 新增 game_share_likes 空表。`scripts/migrate-test-game-share-likes.py --apply` 已执行并核验3列（share_id、open_id、created_at）及联合主键（share_id、open_id），不改既有业务数据。SQL SHA256 `ff8ef718169fcfc4ee8f19c6aa48f80a2b4e92e5bc3b6a070914be1a2734ec6a`。对应 Go 提交 `383f988` 已推送 origin/dev_rex，等待 capabilities 2026-10-19.3/Ready 核验；本轮 OA 无业务/界面改动，无需重建镜像。

- Go测试部署现已核验完成：`383f988`、capabilities `2026-10-19.3`、Ready=true；列表/详情只读正常，现有1条分享返回资料与LikeCount/Liked，无手机号/OpenID泄露。未执行真实点赞、发奖、业务数据改写或生产发布。

### 2026-10-19 OA 订单待办
- 全局顶部待办入口显示未处理订单数（不是已读／未读消息数），Popover 展示门店、订单号、事项和桌游，点击保存该页门店上下文并重载进入指定订单详情；处理后刷新数量，前台每60秒/回到页面时刷新，失败显示未更新而非0条。
- GET /admin_api/game-service/v1/todos 由服务端当前账号授权聚合有效门店，通过既有 Go todo 过滤读取，忽略浏览器 StoreID；输出最多30条简要通知，不含玩家联系方式或标识。无需新表，无共享数据写入。
- 用户后续确认：确认订单 accept 保留“操作说明（选填）”，提示“不填也可确认订单”；拒绝／取消／实物检查等需说明动作保持必填校验。
- 本次27项OA权限/网关隔离测试及TypeScript通过；部署结果另记录。
- 已部署最终镜像 sha256:05aeeaa54943e54051dba20d8577450333425a0dfcc157dafdc3d3d7c6f2ff7c，gambit-oa-test health=healthy，生产容器元数据保持不变。容器内严格限定广州21085/gambit只读事务核验todos业务函数正常（当前0条待办）、匿名访问401；未新增登录会话或业务数据。订单#3仍awaiting_payment，原签名凭证关联匹配且在复用时窗内。Go 5203f2d 已在测试服务实际运行，capabilities 2026-10-19.5 / Ready=true。
- 视觉验收未完成：原生工具可以读取部分截图，但模拟器点击未进入目标页面，OA刷新后也未取得有效新版截图；自动化测试/构建不等同视觉通过。

- 2026-10-19 操作说明选填修正已部署：镜像 `sha256:58db183a61aa93067553ad69f85fb77320f1813298e8588e95507dbe6e369091`，gambit-oa-test health=healthy，生产容器未变。OA TypeScript与构建通过；本次无Go修改或数据库写入，未提交真实确认订单以测试表单。

### 2026-10-19 完好归还自动退款
- 用户要求确认全部完好归还后直接退应退押金，无第二次人工确认。普通店员 return_complete 的自动退款由服务端确定，金额由订单计算；异常结算及一般退款权限保持原规则。事务内保存自动任务，提交后立即定向异步发起，后台补偿兜底；历史 AutoApprove=false 任务不批量转换或补退。
- Go `7ae568f` 已推送 origin/dev_rex，实际 capabilities `2026-10-19.8`、Ready=true。OA 镜像 `sha256:c4a1f3f8d97b30357668fd6283ca87258a7a046b2894c070e5028365fa562f74` 已部署 gambit-oa-test，Health=healthy，生产容器未变。
- OA 12项隔离权限/代理测试、TypeScript和镜像构建通过；Go隔离MySQL支付、退款、任务调度、桌游服务、控制器及路由测试通过，覆盖重复确认、退款金额、自动任务与历史非自动任务隔离。无共享库迁移、历史资金任务写入或真实退款；未通过真实订单进行端到端资金验收。

### 2026-10-19 归还方式与门店收件配置
- 租售设置新增邮寄归还收件人、联系电话、详细地址，使用现有 policy JSON；三项同时填写或全部清空。小程序按订单所属门店读取，不能用全局浏览门店覆盖；OA归还待办显示到店／邮寄及已有物流。
- Go `65de36e` 已推送 origin/dev_rex，实际 capabilities `2026-10-19.6`、Ready=true；OA镜像 `sha256:5fff927fc8bc644143941bc30954196e80c4c6ecf9c34a9fc1ea777b6da125cf` 已部署 gambit-oa-test，health=healthy，生产容器未变。
- 按用户提供的具体信息执行 `scripts/configure-test-return-addresses.py --apply`，仅更新广州测试库南山店（1）、罗湖店（2）的 ReturnRecipient/ReturnPhone/ReturnAddress，通过既有Go policy接口保存、版本保护并回读验证；其他配置字段不变。脚本默认只读，拒绝覆盖不同的非空收件信息，限定测试数据库及Go目标。无DDL、订单、库存、支付或退款操作。
- 两端TypeScript、小程序13项专项测试、Go隔离MySQL桌游服务/控制器/支付/路由测试及构建通过。小程序测试包已重建（主包2015.0 KiB）。模拟器可打开订单但自动化点击归还按钮未打开弹层，本轮弹层实际截图及真机键盘验收未完成，不以单测代替视觉验收。

### 2026-10-19 门店导航与顺丰档位测试部署

- Go `4358353` 已推送 dev_rex，实际 capabilities `2026-10-19.9`、Ready=true；OA linux/amd64 镜像 `sha256:a153dd3d160916c7ad0162eaf7b3e1904ae985eebf714568db2a3c73579a0f20` 已部署 gambit-oa-test，health=healthy，生产容器不变。
- 用户明确授权开启罗湖店租赁及购买配送。`scripts/configure-test-shipping.py --apply` 限定测试环境/罗湖店ID2，仅更新 Shipping=true 与 ShippingServices 三档，其他原政策字段一致；南山店原已开启 Shipping。无迁移、价格/库存/历史订单改写、真实下单、付款或叫件。
- 小程序96项相关测试、两端TypeScript、Go隔离MySQL租售/控制器/路由回归及两端构建通过。开发者工具实际核验租赁和罗湖购买结算的自提/顺丰切换、档位选中、地址表单、底部安全区；南山地址成功打开微信位置页。尚未真机验证外部导航App唤起。
- 门店位置使用已有经纬度（当前两店仅两位小数）；精确到门口的导航落点需门店维护更准确的GCJ-02坐标，不按文案猜坐标。

## 2026-10-21 OA 导航与日常操作第一批优化

- 页面目录按八个业务入口重组，25 个原页面 ID、路径和权限范围保留；默认入口改为工作台。新增按权限过滤的功能搜索及常用别名，顶部统一显示当前门店／共享范围。工作台与页头待办共享单一模型及轮询，不从截断列表推算类别总数。
- 工作台新增紧凑租售待办与当前门店快捷筛选；租售订单精简重复统计，财务汇总按需打开，列表统一 AdaptiveTable，保留筛选和页码，详情按履约／费用／记录分组。库存编辑支持清晰数量分配、开关按需显示字段、批量表格及未保存提醒，价格、额度、资金权限和自动退款业务逻辑保留。
- 验证：TypeScript、前端构建、菜单／逐页门店／功能搜索与下一步动作／请求编号检查、AdaptiveTable 3 项测试通过；后端员工权限 16 项、桌游代理与待办隔离测试 12 项通过。浏览器在 1280px 桌面检查菜单、功能搜索、真实库存与已完成订单、单款和批量抽屉；本机禁止业务写入的隔离样例覆盖长名称、长地址、待确认／交付／归还／取消／租转购、确认说明选填、请求失败保留内容并禁用过时操作、未保存关闭提示。没有提交共享库存／业务订单，没有调用真实支付或退款；更窄屏幕及触屏设备尚未实际验收。
- 最终 linux/amd64 镜像已推送：`sha256:b51b1a718211527f6561063ad6243db723ad4531ea46b2b0b9f07dc1f6ef5b4e`，已通过 deploy-test-server.py 更新 `gambit-oa-test`（18080），实际镜像核对、health=healthy、生产容器保持不变检查通过。无数据库迁移、无 Go 改动，未发布生产。
