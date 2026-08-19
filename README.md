# 上岸书房 · 考公学习云平台（V1.0）

一个私密的考公 PDF 资料在线阅读网站：管理员统一维护资料库，每位受邀用户拥有**完全隔离**的批注/书签/阅读进度，并支持 PDF 全文检索、一键直达对应页。

## 功能总览

- **账号**：邀请码注册（防陌生人混入）、登录/登出、改资料/改密码、管理员可禁用账号/重置密码
- **资料库**：管理员创建多级文件夹、批量上传 PDF、替换文件（保留历史版本可回滚）、回收站
- **在线阅读**：PDF.js 渲染，目录大纲、缩放、全屏、快捷键翻页、自动记忆阅读进度（续读）
- **批注（仅本人可见）**：高亮 / 下划线 / 波浪线 / 文字笔记 / 星标 / 书签，永久保存，换设备不丢，可导出 Markdown
- **检索**：文件名 + PDF 全文 + 自己的笔记，命中结果一键跳到对应页并高亮
- **管理后台**：资料管理、用户管理、邀请码管理、数据统计

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus + PDF.js |
| 后端 | Python FastAPI + SQLAlchemy 2.0 + PostgreSQL 16（pg_trgm 中文检索）|
| 部署 | Docker Compose + Nginx（文件直出带 Range）|

## 目录结构

```
├─ backend/            FastAPI 后端
│  ├─ app/             应用代码（models/schemas/api/services）
│  └─ Dockerfile
├─ web/                Vue3 前端
│  ├─ src/             页面与组件
│  ├─ Dockerfile       多阶段构建（node 构建 → nginx 运行）
│  └─ nginx.conf       静态资源 + API 反代 + PDF 直出
├─ docker-compose.yml  一键编排（db + backend + web）
├─ .env.example        环境变量模板
└─ deploy.sh           一键部署脚本
```

## 一键部署（云服务器）

### 服务器要求

- Linux（Ubuntu/Debian/CentOS 均可），2 核 4G 起步，磁盘按资料量 100G 起
- 已安装 Docker（≥24）与 Docker Compose v2：`docker compose version` 可执行
- 防火墙/安全组开放 **80 端口**（如用 HTTPS 再开 443）
- 国内服务器无需域名、无需备案（直接 IP 访问）

### 部署步骤

```bash
# 1. 上传代码到服务器（或 git clone）
#    打包上传请用 ./scripts/package.sh（自动排除 node_modules/.venv 等依赖目录）
#    Windows 下等效命令见下方「常见问题」
# 2. 进入项目目录
cd shangan

# 3. 生成配置（首次会自动生成 .env 模板）
./deploy.sh
#    → 按提示编辑 .env：SECRET_KEY / INIT_ADMIN_PASSWORD / POSTGRES_PASSWORD
#    → 重新执行 ./deploy.sh

# 4. 完成 ✅ 访问 http://<服务器公网IP>
```

> 💡 若 `docker compose up` 时拉镜像报错（`failed to resolve reference ... no such host`），说明 Docker 镜像源失效，
> 先执行 `sudo ./scripts/fix-docker-mirror.sh`（改用 1ms.run 等可用镜像源并重启 Docker），再重新 `docker compose pull && ./deploy.sh`。

等价手动方式：

```bash
cp .env.example .env
vi .env                 # 修改三个必填项
docker compose up -d --build
docker compose exec backend python -m app.cli ensure-admin
```

### 首次使用流程

1. 浏览器打开 `http://<IP>`，用管理员账号（`.env` 中的 `INIT_ADMIN_USERNAME/PASSWORD`）登录
2. 「管理后台 → 邀请码」生成邀请码（可设有效期/次数）
3. 把邀请码发给朋友 → 他们在 `http://<IP>/register` 注册
4. 「管理后台 → 资料」创建文件夹、上传 PDF（上传后自动提取全文索引，几分钟内可检索）

## 配置说明（.env）

| 变量 | 说明 |
|---|---|
| `POSTGRES_DB/USER/PASSWORD` | 数据库配置，建议改强密码 |
| `SECRET_KEY` | JWT 与签名密钥，**必填**，≥32 位随机（`openssl rand -hex 32`）|
| `INIT_ADMIN_USERNAME/PASSWORD/EMAIL` | 初始管理员账号，容器启动自动创建 |

## HTTPS 建议（可选）

直接 IP 访问默认走 HTTP（密码为密文加密存储，但传输明文）。推荐两种免费加固方式：

1. **Cloudflare Tunnel（推荐）**：无需域名、无需备案，免费 HTTPS 并隐藏服务器 IP
   ```bash
   # 服务器上（cloudflared 单二进制）
   cloudflared tunnel --url http://localhost:80
   # 得到 https://xxxx.trycloudflare.com 即可用，再把 80 改为仅本机监听
   ```
2. **自备域名**：域名解析到 IP 后，用 certbot 签 Let's Encrypt 证书，Nginx 加 443 配置

## 备份与恢复

```bash
# 每日备份（建议 crontab）：
# 数据库
docker compose exec -T db pg_dump -U study study | gzip > backup/db_$(date +%F).sql.gz
# PDF 文件目录
tar czf backup/pdf_$(date +%F).tar.gz -C /var/lib/docker/volumes/shangan_pdfdata/_data .
```
恢复：`gunzip < db_xxx.sql.gz | docker compose exec -T db psql -U study study`；PDF 目录解包回卷目录。

## 本地开发（可选）

```bash
# 后端（需 Python 3.12）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db SECRET_KEY=dev-secret INIT_ADMIN_PASSWORD=admin123 \
  USE_X_ACCEL=false python -m uvicorn app.main:app --port 8000 --reload

# 前端
cd web
npm install
npm run dev        # http://localhost:5173（/api 已代理到 8000）
```

## 常见问题

- **`SECRET_KEY` 未配置报错**：编辑 `.env` 后重新 `docker compose up -d`（无需重新 build）
- **拉取镜像失败（`failed to resolve reference` / `no such host`）**：Docker 镜像源（如 hub-mirror.c.163.com）已失效。执行 `sudo ./scripts/fix-docker-mirror.sh` 改用 `docker.1ms.run` 等可用源并重启 Docker，然后 `docker compose pull && ./deploy.sh`
- **构建时基础镜像报 `unexpected EOF` / `failed to resolve source metadata`**：镜像源瞬时抖动，属偶发网络问题。先执行 `./scripts/pull-images.sh`（自动重试把 4 个基础镜像全部拉齐），再 `./deploy.sh`；若仍失败可多跑一次或换镜像源
- **打开 PDF 报 `Setting up fake worker failed: Failed to fetch dynamically imported module: ...pdf.worker.min-xxx.mjs`**：nginx 未把 `.mjs` 映射为 JS 类型（`Content-Type: application/octet-stream`），浏览器拒绝加载 worker 模块。修复：`web/nginx.conf` 已含 `.mjs` 专用路由（强制 `text/javascript`），同步该文件后执行 `docker compose up -d --build web`，并用 `curl -sI http://IP/assets/pdf.worker.min-*.mjs` 确认返回 `Content-Type: text/javascript`
- **打开 PDF 报 `Cannot read private member #s from an object whose class did not declare it`**：esbuild 压缩会重命名 pdf.js 的私有字段导致类结构冲突（仅生产构建出现，本地开发不可见）。已修复：改用 terser 压缩 + `isEvalSupported: false` + `dedupe` 锁定单实例；更新代码后 `./scripts/update.sh` 重建即可
- **打包上传太大（带了 node_modules/.venv）**：用 `./scripts/package.sh` 自动排除依赖目录；Windows 下等效命令（在项目目录执行）：
  ```powershell
  tar -czf ..\shangan-deploy.tar.gz --exclude=".git" --exclude=".env" --exclude=".venv" --exclude=".tools" --exclude="node_modules" --exclude="web/.npm-cache" --exclude="web/dist" --exclude="__pycache__" --exclude="*.db" .
  ```
- **端口 80 被占用**：改 `docker-compose.yml` 中 `web.ports` 为 `8080:80`，访问 `http://IP:8080`
- **PDF 无法检索**：扫描版（图片型）PDF 无法提取文字，上传后状态显示 failed；纯文字 PDF 正常。OCR 支持在 V2 规划中
- **上传失败**：单文件默认上限 500M（Nginx `client_max_body_size`），超大文件请压缩或拆分
- **如何看日志**：`docker compose logs -f backend` / `docker compose logs -f web`

## 安全清单

- ✅ 邀请码一次性注册，登录接口限流防爆破
- ✅ 密码 argon2 加密存储，JWT 短时效 + refresh 轮换
- ✅ 批注/书签/进度按账号隔离，后端强制归属校验（防越权）
- ✅ 文件经签名 URL 访问，路径不暴露
- ⚠️ 纯 HTTP 下建议强密码；有条件请启用 HTTPS（Cloudflare Tunnel）

## 路线图

- V1.1：文件版本管理完善、笔记导出优化、回收站自动清理、移动端适配
- V2.0：OCR 扫描件检索、文件夹级可见性、阅读统计、PWA
- V3.0：AI 问资料（RAG 引用页码作答）、AI 划重点
