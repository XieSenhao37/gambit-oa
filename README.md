# Gambit OA

Gambit 网页端管理后台，包含：

- `backend/`：Flask + SQLAlchemy API，接口前缀 `/admin_api`
- `frontend/`：Umi Max + Ant Design Pro 管理端页面

## 一键 Docker 部署

生产部署采用单镜像：先构建前端，再把 `frontend/dist` 打进 Flask 后端镜像，由 Flask 同时托管管理后台页面和 `/admin_api`。

镜像仓库：

```text
ccr.ccs.tencentyun.com/gambit/gambit_oa:latest
```

### 1. 准备服务器环境变量

在服务器创建：

```bash
sudo mkdir -p /opt/gambit-oa
sudo cp .env.example /opt/gambit-oa/.env.deploy.local
sudo vim /opt/gambit-oa/.env.deploy.local
```

至少填写：

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/database?charset=utf8mb4
JWT_SECRET=your-secret
SECRET_KEY=your-secret
GAMBIT_INTERNAL_TOKEN=your-internal-token
OA_ADMIN_PASSWORD=your-admin-password
PHONE_CRYPTO_KEY=existing-phone-encryption-key
COS_SECRET_ID=your-cos-secret-id
COS_SECRET_KEY=your-cos-secret-key
```

### 2. 构建并推送镜像

```bash
bash build.sh
```

### 3. 在服务器部署

```bash
bash deploy.sh prod
```

默认启动：

```text
http://<服务器公网IP>:8080
```

如需改端口：

```bash
HOST_PORT=18080 bash deploy.sh test prod
```

如需指定 env 文件：

```bash
DEPLOY_CONFIG=/path/to/.env.deploy.local bash deploy.sh prod
```

## 本地开发

后端：

```bash
cd backend
python run.py
```

前端：

```bash
cd frontend
pnpm install
pnpm dev
```

开发环境下，前端 `.umirc.ts` 会将 `/admin_api` 代理到 `http://127.0.0.1:8080`。

## 仓库与配置

统一仓库：https://github.com/XieSenhao37/gambit-oa。前端、后端、部署文件及说明均在此仓库管理。

真实凭据仅放在未纳入 Git 的 `.env.deploy.local`（权限 `600`），或通过环境变量注入。部署脚本默认加载同目录的该文件，可用 `DEPLOY_CONFIG` 指定路径；后端本地开发读取 `backend/.env`。手机号密钥须沿用现有值，否则无法读取既有加密手机号。密码登录必须配置 `OA_ADMIN_PASSWORD`，未配置时不能登录。

生产首次部署保持 `STORE_SETTLEMENT_ENABLED=false`，完成正式库迁移和期初初始化后再启用。旧前后端 Git 历史仅在本地 `.git/legacy/` 保留，不推送到新仓库。
