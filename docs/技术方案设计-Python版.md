# 上岸书房 · 技术方案设计（Python 技术栈 · 可开工级）

> 配套文档：《考公学习平台-产品设计文档》v1.1
> 本文给出可直接开工的实现方案：架构、建表 SQL、API 契约、批注协议、检索实现、部署与安全。

---

## 1. 已确认的需求输入

| # | 决策 | 落点 |
|---|---|---|
| 1 | 批注仅本人可见 | 批注/书签/进度表全部带 `user_id`，后端强制归属校验 |
| 2 | 管理员独占文件写权限，全员只读 | 文件写接口仅管理员可调；普通用户前端无入口 + 后端 403 |
| 3 | Python 技术栈 | 后端 FastAPI + SQLAlchemy + PostgreSQL |
| 4 | 自备服务器，公网 IP 直连，无域名/备案 | Docker Compose 单机部署，Nginx 直出 |

---

## 2. 总体架构

```
┌─────────────── 浏览器（Vue3 SPA + PDF.js） ───────────────┐
│  登录/注册 │ 资料库 │ 阅读器(批注叠加层) │ 检索 │ 管理后台 │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP / HTTPS
                       ▼
              Nginx（静态资源 + /api 反代 + 文件直出带 Range）
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
   FastAPI (API)   PostgreSQL 16     PDF 数据卷（磁盘）
   ├ auth/JWT         ├ 业务数据        ├ original/<file_key>.pdf
   ├ 上传/版本        ├ document_pages  └（每日备份脚本）
   ├ 检索 API         └ pg_trgm 索引
   └ 异步任务：PDF 文本提取（进程内队列 + 状态表，无需 Redis/MQ）
```

**两个关键设计决定**

1. **文件直出走 Nginx `X-Accel-Redirect` + 短时效签名 URL**：PDF.js 依赖 HTTP Range 分段加载，大文件才能秒开；同时文件路径不暴露给前端。
2. **中文全文检索用 PostgreSQL `pg_trgm`（起步）**：零额外服务，按字符三字组匹配中文子串，几十到几百个 PDF 的性能足够；体验不满意可平滑升级 pg_jieba 分词或 Meilisearch（只换 `services/search.py`，API 不变）。

---

## 3. 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn | 异步高性能、自动生成 OpenAPI 文档 |
| ORM/迁移 | SQLAlchemy 2.0 + Alembic | 类型化查询 + 版本化迁移 |
| 数据校验 | Pydantic v2 | 请求/响应模型 |
| 数据库 | PostgreSQL 16 + pg_trgm | 业务数据 + 中文检索 |
| 认证 | PyJWT + argon2-cffi | JWT access/refresh；密码 argon2 加盐哈希 |
| PDF 处理 | pypdf（页数/文本/大纲提取） | 前端渲染用 PDF.js |
| 限流 | slowapi | 登录/注册接口防爆破 |
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router + PDF.js | 桌面优先 |
| 部署 | Docker Compose + Nginx | 一条命令启动 |

---

## 4. 数据库设计（PostgreSQL DDL，可直接执行）

### 4.1 扩展

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 4.2 建表

```sql
-- 用户
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(32)  NOT NULL UNIQUE,
  email         VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(10)  NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
  status        VARCHAR(10)  NOT NULL DEFAULT 'normal' CHECK (status IN ('normal','disabled')),
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 邀请码（一次性、可过期、可作废）
CREATE TABLE invite_codes (
  id         BIGSERIAL PRIMARY KEY,
  code       VARCHAR(32)  NOT NULL UNIQUE,
  max_uses   INT          NOT NULL DEFAULT 1,
  used_count INT          NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ,
  revoked    BOOLEAN      NOT NULL DEFAULT FALSE,
  created_by BIGINT       NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 文件夹（多级树，仅管理员维护）
CREATE TABLE folders (
  id         BIGSERIAL PRIMARY KEY,
  name       VARCHAR(64) NOT NULL,
  parent_id  BIGINT REFERENCES folders(id) ON DELETE CASCADE,
  sort       INT NOT NULL DEFAULT 0,
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (parent_id, name)
);
CREATE INDEX idx_folders_parent ON folders(parent_id);

-- 资料文件（全站共享、全员只读）
CREATE TABLE documents (
  id                  BIGSERIAL PRIMARY KEY,
  folder_id           BIGINT REFERENCES folders(id) ON DELETE SET NULL,
  title               VARCHAR(255) NOT NULL,
  subject             VARCHAR(32),
  stage               VARCHAR(16),      -- 基础/强化/冲刺
  year                VARCHAR(16),
  source              VARCHAR(255),
  tags                TEXT[] DEFAULT '{}',
  file_key            VARCHAR(255) NOT NULL,   -- 磁盘相对路径
  file_size           BIGINT NOT NULL DEFAULT 0,
  page_count          INT,
  text_extract_status VARCHAR(16) NOT NULL DEFAULT 'pending'
                      CHECK (text_extract_status IN ('pending','processing','done','failed')),
  version             INT NOT NULL DEFAULT 1,
  created_by          BIGINT NOT NULL REFERENCES users(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at          TIMESTAMPTZ                -- 软删除 → 回收站
);
CREATE INDEX idx_documents_folder ON documents(folder_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_title ON documents USING gin (title gin_trgm_ops);
CREATE INDEX idx_documents_tags  ON documents USING gin (tags);

-- 文件版本（替换后旧版本归档，可回滚）
CREATE TABLE document_versions (
  id          BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  version_no  INT NOT NULL,
  file_key    VARCHAR(255) NOT NULL,
  file_hash   VARCHAR(64),
  note        VARCHAR(255),
  created_by  BIGINT NOT NULL REFERENCES users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, version_no)
);

-- 每页提取的文本（全文检索用）
CREATE TABLE document_pages (
  id          BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_no     INT NOT NULL,
  text        TEXT NOT NULL DEFAULT '',
  UNIQUE (document_id, page_no)
);
CREATE INDEX idx_pages_trgm ON document_pages USING gin (text gin_trgm_ops);

-- 批注（★ 账号隔离的根基：所有查询必须带 user_id）
CREATE TABLE annotations (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page        INT NOT NULL,
  type        VARCHAR(16) NOT NULL CHECK (type IN ('highlight','underline','wave','note','star')),
  color       VARCHAR(16) NOT NULL DEFAULT '#ffe14d',
  rect        JSONB,                      -- {"x1":..,"y1":..,"x2":..,"y2":..} 0~1 归一化
  content     TEXT,                       -- 笔记文字
  quoted_text TEXT,                       -- 被划词的原文
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_annotations_user_doc  ON annotations(user_id, document_id);
CREATE INDEX idx_annotations_user_page ON annotations(user_id, document_id, page);

-- 书签
CREATE TABLE bookmarks (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page        INT NOT NULL,
  label       VARCHAR(64),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, document_id, page)
);

-- 阅读进度（续读）
CREATE TABLE reading_progress (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page        INT NOT NULL DEFAULT 1,
  scroll_y    DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, document_id)
);

-- 自动更新 updated_at（可选，SQLAlchemy onupdate 亦可替代）
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;
```

**关键约束说明**

- 学习数据三表（annotations / bookmarks / reading_progress）均以 `user_id` 为第一隔离维度，业务层查询强制 `WHERE user_id = 当前用户`，管理员也无读取他人批注的接口。
- `documents` 不挂 user → 全站统一资料库；写权限靠 FastAPI 的 `require_admin` 依赖控制。
- 版本替换后批注保留；若页数变化，前端提示"页码可能偏移"。

---

## 5. 后端工程结构

```
backend/
├─ app/
│  ├─ main.py              # FastAPI 实例、路由注册、启动钩子
│  ├─ config.py            # 环境变量（pydantic-settings）
│  ├─ database.py          # SQLAlchemy engine / session
│  ├─ deps.py              # get_db / get_current_user / require_admin
│  ├─ models/              # ORM 模型（user/folder/document/annotation/...）
│  ├─ schemas/             # Pydantic 请求/响应模型
│  ├─ api/
│  │  ├─ auth.py           # 注册/登录/刷新/改密
│  │  ├─ users.py          # 我的资料
│  │  ├─ folders.py        # 文件夹 CRUD（管理员写）
│  │  ├─ documents.py      # 列表/详情/上传/替换/删除/版本（管理员写）
│  │  ├─ files.py          # 签名 URL 文件流（X-Accel-Redirect）
│  │  ├─ reader.py         # 阅读会话/进度
│  │  ├─ annotations.py    # 批注/书签 CRUD（本人数据）
│  │  ├─ search.py         # 全局检索
│  │  ├─ my_notes.py       # 我的笔记 / 导出
│  │  └─ admin.py          # 用户/邀请码/统计
│  ├─ services/
│  │  ├─ pdf_extract.py    # pypdf 提取页数/文本/大纲（异步任务）
│  │  ├─ search.py         # pg_trgm 查询与片段生成
│  │  ├─ storage.py        # 文件落盘/命名/删除
│  │  └─ security.py       # JWT / argon2 / 签名 URL
│  └─ cli.py               # create-admin 等命令行工具
├─ alembic/                # 迁移脚本
├─ requirements.txt
├─ Dockerfile
└─ .env.example
```

---

## 6. API 设计（REST 契约）

> 鉴权：`Authorization: Bearer <access_token>`；管理员接口额外校验 `role=admin`。

### 6.1 认证与账号

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/auth/register` | 公开 | 邀请码注册 `{username,email,password,invite_code}` |
| POST | `/api/auth/login` | 公开 | 返回 `{access_token, refresh_token, user}` |
| POST | `/api/auth/refresh` | refresh token | 刷新 access token |
| GET | `/api/auth/me` | 登录 | 当前用户信息 |
| PATCH | `/api/users/me` | 登录 | 修改昵称/头像 |
| PUT | `/api/users/me/password` | 登录 | 修改密码 |

### 6.2 资料库（读：全员；写：仅管理员）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/folders` | 登录 | 文件夹树 |
| POST | `/api/folders` | 管理员 | 新建文件夹 |
| PATCH | `/api/folders/{id}` | 管理员 | 重命名/移动/排序 |
| DELETE | `/api/folders/{id}` | 管理员 | 删除（含子级与文件，二次确认） |
| GET | `/api/documents?folder_id=&subject=&stage=&q=` | 登录 | 文件列表（含我的批注数/进度） |
| GET | `/api/documents/{id}` | 登录 | 文件详情（页数/大纲/版本） |
| POST | `/api/documents` | 管理员 | 上传 PDF（multipart，可多文件） |
| POST | `/api/documents/{id}/replace` | 管理员 | 替换文件（生成新版本 + 重新索引） |
| GET | `/api/documents/{id}/versions` | 登录 | 版本列表 |
| POST | `/api/documents/{id}/rollback` | 管理员 | 回滚到某版本 |
| DELETE | `/api/documents/{id}` | 管理员 | 软删除 → 回收站 |
| GET | `/api/trash` | 管理员 | 回收站列表 |
| POST | `/api/trash/{id}/restore` | 管理员 | 恢复 |
| DELETE | `/api/trash/{id}` | 管理员 | 彻底删除 |
| GET | `/api/files/{id}/url` | 登录 | 获取短时效签名文件 URL（TTL 5 分钟） |

### 6.3 阅读与批注（本人数据）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/reader/{doc_id}` | 登录 | 阅读会话：文件URL+大纲+我的批注+进度 |
| PUT | `/api/reader/{doc_id}/progress` | 登录 | 保存进度 `{page, scroll_y}` |
| GET | `/api/documents/{doc_id}/annotations` | 登录 | 我的批注（按页聚合） |
| POST | `/api/documents/{doc_id}/annotations` | 登录 | 新建批注 |
| PATCH | `/api/annotations/{id}` | 本人 | 修改（改色/改内容/移动） |
| DELETE | `/api/annotations/{id}` | 本人 | 删除 |
| GET/POST/DELETE | `/api/documents/{doc_id}/bookmarks` | 本人 | 书签列表/新增/删除 |

### 6.4 检索与笔记

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/search?q=&scope=all\|file\|content\|note` | 登录 | 分组检索结果（含页码） |
| GET | `/api/my-notes?document_id=&type=` | 登录 | 我的笔记聚合 |
| GET | `/api/my-notes/export?format=md\|pdf` | 登录 | 导出笔记 |

### 6.5 管理后台

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/admin/users` | 管理员 | 成员列表 |
| PATCH | `/api/admin/users/{id}` | 管理员 | 禁用/启用 |
| POST | `/api/admin/users/{id}/reset-password` | 管理员 | 重置密码 |
| POST | `/api/admin/invite-codes` | 管理员 | 生成邀请码 |
| GET | `/api/admin/invite-codes` | 管理员 | 邀请码列表 |
| DELETE | `/api/admin/invite-codes/{id}` | 管理员 | 作废邀请码 |
| GET | `/api/admin/stats` | 管理员 | 文件数/用户数/阅读量统计 |

### 6.6 鉴权依赖（后端兜底）

```python
def get_current_user(credentials=Depends(HTTPBearer()), db=Depends(get_db)) -> User:
    ...  # 解析 JWT → 校验 status=normal → 返回用户

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
```

---

## 7. 批注协议（前后端契约）

### 7.1 创建批注请求

```json
POST /api/documents/12/annotations
{
  "type": "highlight",          // highlight | underline | wave | note | star
  "page": 3,
  "color": "#ffe14d",
  "rect": { "x1": 0.12, "y1": 0.34, "x2": 0.65, "y2": 0.36 },
  "quoted_text": "被划词的文字原文",
  "content": "这段是重点！"
}
```

响应 = 同上 + `id` / `created_at`。

### 7.2 前端渲染规则

1. PDF.js 渲染页面为 canvas + text layer（每个字符/词是带 `data-page-no` 的 span）。
2. **划词**：`mouseup` → `window.getSelection()` → 取 text layer 内各 span 的 `getClientRects()` → 合并为矩形 → 除以当前页面渲染尺寸归一化到 0~1 → 提交。
3. **渲染**：进入阅读页拉取"我的批注" → 归一化坐标 × 当前渲染尺寸 → 绝对定位 div 叠加（高亮=半透明底色；下划线/波浪线=`border-bottom` 或 SVG path；笔记=页面内图标 + 面板展示）。
4. **缩放/翻页后重算坐标**；进度自动保存 `{page, scroll_y}`。

---

## 8. 检索实现

### 8.1 文本提取流水线（上传后自动）

1. 上传完成 → `documents.text_extract_status = 'pending'` → 入进程内异步队列。
2. 任务：pypdf 打开 → 页数 → 逐页 `extract_text()` → 批量写入 `document_pages` → 状态 `done`；异常重试 3 次后 `failed`（管理员后台可见"重新索引"按钮）。
3. 替换文件时对同一文档重新提取并清空旧页文本。

### 8.2 检索 SQL 思路

- 文件名命中：`documents.title ILIKE '%q%'`（pg_trgm 索引加速）。
- 内容命中：

```sql
SELECT d.id, d.title, p.page_no, p.text
FROM document_pages p
JOIN documents d ON d.id = p.document_id
WHERE d.deleted_at IS NULL
  AND p.text ILIKE '%' || :q || '%'
ORDER BY length(p.text) ASC          -- 简单相关性：越短越靠前（命中越密）
LIMIT 50;
```

- 我的笔记命中：`annotations.content/quoted_text ILIKE`（强制 `user_id = 当前用户`）。
- 片段生成：取首次命中位置前后 30 字符，前端高亮关键词；结果点击 → 打开 PDF 跳转 `page_no` 并定位高亮词。
- **中文说明**：pg_trgm 按字符三字组匹配，连续 2~4 字关键词效果良好；单字检索噪音较大属预期。若体验不足 → 升级 pg_jieba 分词或 Meilisearch（仅替换 `services/search.py`，API 不变）。

---

## 9. 文件直出与 Range（关键实现）

- 后端校验权限后签发短时效 URL：`/api/files/stream/{doc_id}?exp=…&sig=HMAC-SHA256…`（TTL 5 分钟，用 JWT secret 派生）。
- Nginx 配置 internal 直出：

```nginx
location /protected/ { internal; alias /data/pdf/; }

location /api/files/stream/ {
    proxy_pass http://backend:8000;      # FastAPI 校验签名后
    # 响应头 X-Accel-Redirect: /protected/<file_key> → Nginx 直接吐文件（原生支持 Range）
}
```

- 效果：PDF.js 可发起 Range 分段加载，大文件秒开；文件路径永不暴露。

---

## 10. Docker Compose 部署（公网 IP 直连）

### 10.1 docker-compose.yml（概要）

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: [ pgdata:/var/lib/postgresql/data ]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    env_file: .env
    volumes: [ pdfdata:/data/pdf ]
    depends_on:
      db: { condition: service_healthy }
    command: sh -c "alembic upgrade head && python -m app.cli ensure-admin && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  web:
    image: nginx:alpine
    ports: [ "80:80" ]
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on: [ backend ]

volumes:
  pgdata: {}
  pdfdata: {}
```

### 10.2 启动流程

```bash
docker compose up -d --build
docker compose exec backend python -m app.cli create-admin   # 创建管理员（或 env 预置）
# 浏览器打开 http://<公网IP> → 管理员登录 → 后台生成邀请码 → 分享给朋友
```

### 10.3 公网访问与 HTTPS 三个选项

| 方案 | 优点 | 缺点 | 建议 |
|---|---|---|---|
| A. 纯 HTTP（80 端口） | 零配置 | 密码/令牌明文传输 | 朋友间信任度高时可用，务必强密码 + 限流 |
| B. 自签 HTTPS（443） | 有加密 | 浏览器"不安全"警告 | 不推荐（体验差） |
| C. Cloudflare Tunnel（免费） | **免费 HTTPS、无需域名与备案、隐藏服务器真实 IP** | 多一个 cloudflared 进程 | **推荐**：服务器上跑 `cloudflared tunnel --url http://localhost:80` 即得 https 公网地址 |

### 10.4 安全基线（公网直连务必做）

- 防火墙只开放 80/443（SSH 改端口或仅密钥登录）；
- 登录/注册接口限流（slowapi：5 次/分钟/IP）；邀请码一次性 + 可过期；
- JWT secret / 数据库密码用强随机值，写入 `.env`（不入库、不提交 git）；
- 每日备份：`pg_dump` + PDF 数据目录 tar，cron 定时推到 OSS/COS/另一台机器；
- 所有"学习数据"接口强制 user_id 归属校验（越权测试用例必跑）；
- 前端构建产物只含静态文件，所有业务请求走后端鉴权。

---

## 11. 前端页面与组件规划

| 路由 | 页面 | 关键组件 |
|---|---|---|
| `/login` `/register` | 登录 / 邀请码注册 | AuthForm |
| `/` | 学习工作台（继续阅读/最近更新/我的笔记） | ContinueReading、RecentDocs |
| `/library` | 资料库（文件夹树 + 文件卡片） | FolderTree、DocumentCard、UploadDialog(admin) |
| `/reader/:id` | **阅读页**（PDF + 批注层 + 笔记面板） | PdfReader、AnnotationLayer、NotePanel、OutlinePanel |
| `/search?q=` | 检索结果（分组 + 直达跳页） | SearchBox、ResultGroup |
| `/my-notes` | 我的笔记聚合 / 导出 | NoteList、ExportBtn |
| `/settings` | 个人中心 | ProfileForm |
| `/admin/*` | 管理后台（文件/用户/邀请码） | AdminLayout、UserTable、InviteCodePanel |

状态管理：Pinia（auth / library / reader）；批注操作乐观更新 + 失败自动重试。
阅读器性能：页面懒加载、±2 页预渲染、滚动位置记录；宽屏双列（V1.1）。

---

## 12. 里程碑与工作量（单人估算）

| 阶段 | 内容 | 工作量 |
|---|---|---|
| M1 脚手架 | 项目结构、DDL/迁移、认证 + 邀请码 + 用户管理 | 1.5 天 |
| M2 资料库 | 文件夹、上传/替换/回收站、签名文件流（Range） | 2 天 |
| M3 索引检索 | 文本提取流水线、pg_trgm 检索 API | 1.5 天 |
| M4 阅读器 | PDF.js 集成、进度记忆 | 1.5 天 |
| M5 批注 | 坐标协议、叠加渲染层、CRUD、书签 | 2 天 |
| M6 检索前端 + 导出 | 结果页、直达跳页、笔记导出 | 1 天 |
| M7 管理后台 | 文件/用户/邀请码管理页面 | 1 天 |
| M8 部署加固 | Docker Compose、备份、限流、安全联调 | 1 天 |
| **合计** | | **≈ 11.5 人日（2~3 周）** |

---

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| 中文检索效果一般（无分词） | 起步 pg_trgm 够用；不满意换 pg_jieba 或 Meilisearch，检索接口不变 |
| 扫描版 PDF 无法提取文本 | 上传时检测并提示"疑似扫描件"；V2 接 OCR（PaddleOCR/Tesseract） |
| 纯 HTTP 明文风险 | 推荐 Cloudflare Tunnel；至少强密码 + 限流 + 邀请制 |
| PDF.js worker 跨域问题 | 前端同源部署（Nginx 托管），worker 走同源路径 |
| 批注坐标错位 | 归一化坐标 + 缩放换算；text layer 缺失时降级为"点选位置"批注 |
| 大文件上传超时 | 前端分片上传（V1.1）；上传期间任务化不阻塞接口 |
