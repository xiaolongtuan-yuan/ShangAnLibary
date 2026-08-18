# 上岸书房 V1.0 · 前后端 API 契约（唯一事实来源）

> 后端与前端两个实现子代理**必须**严格遵循本文档。字段名、路径、状态码、JSON 结构以本文为准；本文未覆盖之处参考《技术方案设计-Python版.md》，仍有歧义时以"后端优先、前端适配"为原则。

---

## 1. 全局约定

- **基础路径**：所有业务接口以 `/api` 开头；Nginx 将 `/api/*` 反代到后端 `:8000`。
- **鉴权**：`Authorization: Bearer <access_token>`；登录/注册/health 除外。
- **错误格式**：FastAPI 默认 `{"detail": "<中文提示>"}`。
- **状态码**：201 创建成功；200 其余成功；400 业务错误（如邀请码无效）；401 未登录/令牌失效；403 无权限（普通用户调管理员接口）；404 资源不存在；409 不用，重复用 400。
- **时间格式**：ISO 8601 字符串（`2026-05-01T10:00:00`，UTC）。
- **分页**：V1.0 不分页，列表接口返回全量（资料量 ≤ 数百份，够用）。
- **JSON 字段**：返回中 `null` 字段可省略；前端读取时用 `?? null` 兜底。

---

## 2. 后端环境变量（`backend/app/config.py` 读取）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://study:study123@db:5432/study` | 生产用 PostgreSQL；本地测试可用 `sqlite:///./dev.db` |
| `SECRET_KEY` | （必填，无默认） | JWT 与签名 URL 密钥，>=32 字符 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access token 有效期 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | refresh token 有效期 |
| `PDF_DATA_DIR` | `/data/pdf` | PDF 文件存储根目录（容器内挂载卷） |
| `USE_X_ACCEL` | `true` | true=返回 `X-Accel-Redirect` 头由 Nginx 直出；false=后端直接 `FileResponse`（本地开发用） |
| `INIT_ADMIN_USERNAME` | `admin` | 容器启动时自动创建的管理员账号 |
| `INIT_ADMIN_PASSWORD` | （必填） | 管理员初始密码 |
| `INIT_ADMIN_EMAIL` | `admin@example.com` | 管理员邮箱 |
| `CORS_ORIGINS` | `*` | 逗号分隔 |

---

## 3. 数据模型（SQLAlchemy 2.0，`backend/app/models/`）

> 兼容性要求：`rect`、`tags` 用 `JSON` 类型（PG 与 SQLite 均可用）；检索统一用 `column.ilike(f"%{q}%")`（PG 编译为 ILIKE）；**不得**直接写 `ARRAY(Text)`、`JSONB`、裸 `ILIKE` 字符串。pg_trgm 扩展与 GIN 索引在 `database.py` 的 `init_extensions()` 中**按方言判断**（仅 PostgreSQL 执行，用 `engine.dialect.name == "postgresql"` 判断），SQLite 下跳过。

### 3.1 users
`id` PK 自增 ｜ `username` str(32) unique ｜ `email` str(255) unique ｜ `password_hash` str ｜ `role` `'admin'|'user'` ｜ `status` `'normal'|'disabled'` ｜ `created_at` ｜ `updated_at`

### 3.2 invite_codes
`id` ｜ `code` str(32) unique ｜ `max_uses` int 默认 1 ｜ `used_count` int 默认 0 ｜ `expires_at` datetime 可空 ｜ `revoked` bool 默认 false ｜ `created_by` FK users ｜ `created_at`

### 3.3 folders
`id` ｜ `name` str(64) ｜ `parent_id` FK folders 可空 ｜ `sort` int ｜ `created_by` FK ｜ `created_at`；`UniqueConstraint(parent_id, name)`（SQLite 下 NULL 不参与唯一，接受）

### 3.4 documents
`id` ｜ `folder_id` FK 可空 ｜ `title` str(255) ｜ `subject` str(32) 可空 ｜ `stage` str(16) 可空 ｜ `year` str(16) 可空 ｜ `source` str(255) 可空 ｜ `tags` JSON(list) ｜ `file_key` str(255) ｜ `file_size` int ｜ `page_count` int 可空 ｜ `text_extract_status` `'pending'|'processing'|'done'|'failed'` ｜ `version` int 默认 1 ｜ `created_by` FK ｜ `created_at` ｜ `updated_at` ｜ `deleted_at` datetime 可空（软删除）

### 3.5 document_versions
`id` ｜ `document_id` FK ｜ `version_no` int ｜ `file_key` str ｜ `file_hash` str(64) 可空 ｜ `note` str(255) 可空 ｜ `created_by` FK ｜ `created_at`；`Unique(document_id, version_no)`

### 3.6 document_pages
`id` ｜ `document_id` FK ｜ `page_no` int ｜ `text` Text；`Unique(document_id, page_no)`

### 3.7 annotations（★账号隔离）
`id` ｜ `user_id` FK ｜ `document_id` FK ｜ `page` int ｜ `type` `'highlight'|'underline'|'wave'|'note'|'star'` ｜ `color` str 默认 `'#ffe14d'` ｜ `rect` JSON 可空 `{"x1":0.1,"y1":0.3,"x2":0.6,"y2":0.33}`（0~1 归一化）｜ `content` Text 可空 ｜ `quoted_text` Text 可空 ｜ `created_at` ｜ `updated_at`；索引 `(user_id, document_id)`

### 3.8 bookmarks
`id` ｜ `user_id` ｜ `document_id` ｜ `page` int ｜ `label` str(64) 可空 ｜ `created_at`；`Unique(user_id, document_id, page)`

### 3.9 reading_progress
`id` ｜ `user_id` ｜ `document_id` ｜ `page` int ｜ `scroll_y` float ｜ `updated_at`；`Unique(user_id, document_id)`

---

## 4. API 端点全集

### 4.1 认证与账号

**POST `/api/auth/register`**（公开）
请求：`{"username":"小明","email":"ming@x.com","password":"abc12345","invite_code":"XXXX"}`
响应 201：`{"id":3,"username":"小明","email":"ming@x.com","role":"user"}`
校验：用户名/邮箱唯一（重复→400）；密码 ≥8 位；邀请码有效（存在、未撤销、未过期、used_count<max_uses）且**成功注册后 used_count+1**。

**POST `/api/auth/login`**（公开，限流 5 次/分钟/IP，内存实现）
请求：`{"username":"admin","password":"..."}`（username 可为用户名或邮箱）
响应 200：`{"access_token":"...","refresh_token":"...","token_type":"bearer","user":{"id":1,"username":"admin","email":"...","role":"admin"}}`
被禁用账号返回 403。

**POST `/api/auth/refresh`**（公开）
请求：`{"refresh_token":"..."}` ｜ 响应 200：`{"access_token":"...","refresh_token":"..."}`（轮换，旧 refresh 立即失效）

**GET `/api/auth/me`**（登录）
响应：`{"id":1,"username":"admin","email":"...","role":"admin","created_at":"..."}`

**PATCH `/api/users/me`**（登录）
请求：`{"username":"新名","email":"new@x.com"}`（均可选）｜ 响应：同 me

**PUT `/api/users/me/password`**（登录）
请求：`{"old_password":"...","new_password":"..."}` ｜ 响应：`{"message":"密码已修改"}`

### 4.2 文件夹（读全员 / 写仅管理员）

**GET `/api/folders`** → 树形：
```json
[{"id":1,"name":"行测","parent_id":null,"sort":0,"children":[
   {"id":2,"name":"言语理解","parent_id":1,"sort":0,"children":[]}
]}]
```

**POST `/api/folders`**（管理员）`{"name":"申论","parent_id":null}` → 201 返回该文件夹（含 children:[]）

**PATCH `/api/folders/{id}`**（管理员）`{"name":"新名","parent_id":1,"sort":0}`（均可选）→ 200 返回该文件夹

**DELETE `/api/folders/{id}`**（管理员）→ 若含子文件夹或文件返回 400 `{"detail":"文件夹非空，请先清空"}`；否则级联删除，200 `{"message":"已删除"}`

### 4.3 文档（读全员 / 写仅管理员）

**GET `/api/documents?folder_id=&q=&subject=&stage=`** → 200 扁平列表（按 updated_at 倒序）：
```json
[{"id":1,"folder_id":2,"folder_name":"言语理解","title":"2025言语专项.pdf","subject":"行测",
  "stage":"强化","year":"2025","source":null,"tags":["真题"],
  "file_size":1234567,"page_count":86,"version":2,"text_extract_status":"done",
  "created_at":"...","updated_at":"...","my_annotation_count":5,"my_progress_page":42}]
```
`folder_id` 过滤：传 `folder_id=0` 表示"未分类"（folder_id IS NULL）；`q` 匹配标题。

**GET `/api/documents/{id}`** → 详情：
```json
{"id":1,"folder_id":2,"folder_name":"言语理解","title":"...","subject":"行测","stage":"强化",
 "year":"2025","source":null,"tags":["真题"],"file_size":1234567,"page_count":86,
 "text_extract_status":"done","version":2,"created_at":"...","updated_at":"...",
 "outline":[{"title":"第一章 概述","page":1},{"title":"第二章 技巧","page":10}]}
```
`outline` 由 pypdf `get_outlines()` 提取，扁平化（忽略层级，只取 (title, 页码)）；无大纲返回 `[]`。

**POST `/api/documents`**（管理员）multipart/form-data：
- 字段：`files`（`List[UploadFile]`，可多个）、`folder_id`（可选）、`subject`/`stage`/`year`/`source`（可选字符串）、`tags`（可选 JSON 字符串如 `'["真题"]'`）
- 行为：每个文件落盘到 `<PDF_DATA_DIR>/original/<uuid>.pdf`，创建 document（title=文件名去扩展名，`text_extract_status='pending'`），随后 `BackgroundTasks` 异步执行文本提取（见 §7）。同名文件自动加 ` (1)`、` (2)` 后缀。
- 响应 201：`[{"id":1,"title":"...","file_size":123,"text_extract_status":"pending"}]`

**POST `/api/documents/{id}/replace`**（管理员）multipart：`file`（单个）+ `note`（可选）→ 保存为新文件 → `document_versions` 新增一条（version_no = 当前+1，当前文件记录进 versions 表）→ documents.file_key/version 更新 → 重新入队文本提取 → 200 `{"id":1,"version":3,"message":"已替换"}`

**GET `/api/documents/{id}/versions`** → `[{"id":1,"version_no":1,"file_size":123,"note":"初版","created_at":"..."}]`（file_size 从文件读取，可选 0）

**POST `/api/documents/{id}/rollback`**（管理员）`{"version_no":1}` → 把该版本文件恢复为当前（file_key 指向版本文件，version=该版本号，重新索引）→ 200 `{"id":1,"version":1,"message":"已回滚"}`

**DELETE `/api/documents/{id}`**（管理员）→ 软删除（deleted_at=now）→ 200 `{"message":"已移入回收站"}`

**GET `/api/trash`**（管理员）→ 回收站文档列表（同 documents 列表字段 + `deleted_at`）

**POST `/api/trash/{id}/restore`**（管理员）→ 200 `{"message":"已恢复"}`

**DELETE `/api/trash/{id}`**（管理员）→ 彻底删除（文件+版本+页文本+批注+书签+进度 级联）→ 200 `{"message":"已彻底删除"}`

### 4.4 文件流（签名 URL）

**GET `/api/files/{id}/url`**（登录）→ `{"url":"/api/files/stream/1?exp=1750000000&sig=abc123"}`（相对路径，TTL 5 分钟，HMAC-SHA256(secret, "doc:{id}:{exp}")）

**GET `/api/files/stream/{id}?exp=&sig=`**（登录）：
- 校验签名与过期；失败 403。
- `USE_X_ACCEL=true`：返回 `Response(status_code=200, headers={"X-Accel-Redirect": f"/protected/{file_key}", "Content-Type":"application/pdf", "Content-Disposition":"inline; filename*=UTF-8''{quoted_title}"})`（**不要** body）。
- `USE_X_ACCEL=false`：返回 `FileResponse(path, filename=title, media_type="application/pdf")`（Starlette 自带 Range 支持，本地开发 PDF.js 可分段加载）。

### 4.5 阅读与批注（本人数据）

**GET `/api/reader/{doc_id}`**（登录）→ 阅读会话：
```json
{"document":{...详情同 GET /api/documents/{id}...},
 "file_url":"/api/files/stream/1?exp=...&sig=...",
 "annotations":[{"id":1,"document_id":1,"page":3,"type":"highlight","color":"#ffe14d",
                 "rect":{"x1":0.1,"y1":0.3,"x2":0.6,"y2":0.33},"content":"重点","quoted_text":"原文",
                 "created_at":"...","updated_at":"..."}],
 "bookmarks":[{"id":1,"page":42,"label":"必背","created_at":"..."}],
 "progress":{"page":42,"scroll_y":0.55}}
```

**PUT `/api/reader/{doc_id}/progress`**（登录）`{"page":42,"scroll_y":0.55}` → 200 `{"page":42,"scroll_y":0.55}`（upsert）

**GET `/api/documents/{doc_id}/annotations`**（登录）→ 本人批注数组（同 reader.annotations 元素）

**POST `/api/documents/{doc_id}/annotations`**（登录）
请求：`{"type":"highlight","page":3,"color":"#ffe14d","rect":{...},"content":"笔记","quoted_text":"原文"}`（content/quoted_text 可选）→ 201 返回完整 annotation

**PATCH `/api/annotations/{id}`**（本人）`{"color":"#ff0000","content":"改","rect":{...},"page":3}`（均可选）→ 200 返回 annotation；非本人 404

**DELETE `/api/annotations/{id}`**（本人）→ 200 `{"message":"已删除"}`

**GET `/api/documents/{doc_id}/bookmarks`**（登录）→ 本人书签数组
**POST `/api/documents/{doc_id}/bookmarks`**（登录）`{"page":42,"label":"必背"}` → 201 返回 bookmark
**DELETE `/api/bookmarks/{id}`**（本人）→ 200 `{"message":"已删除"}`

### 4.6 检索

**GET `/api/search?q=&scope=all|file|content|note`**（登录，q 必填非空，scope 默认 all）→ 200：
```json
{"files":[{"id":1,"title":"...","subject":"行测","folder_name":"言语理解","matched_field":"title"}],
 "content":[{"document_id":1,"title":"...","folder_name":"言语理解","page":12,"snippet":"……关键词前后30字……"}],
 "notes":[{"id":3,"document_id":1,"title":"...","page":12,"content":"我的笔记","quoted_text":"原文","type":"highlight","color":"#ffe14d"}]}
```
- `files`：documents.title ilike（q 为空时该组为空）。
- `content`：document_pages.text ilike，限制已删除文档，snippet 取首个命中位置前后各 30 字符，`LIMIT 50`。
- `notes`：本人 annotations.content/quoted_text ilike。
- scope 过滤：`file` 只返回 files；`content` 只返回 content；`note` 只返回 notes；`all` 返回全部三组。
- 中文无分词说明：连续 2~4 字关键词效果最佳（pg_trgm）。

### 4.7 我的笔记 / 导出

**GET `/api/my-notes?document_id=&type=`**（登录）→ 本人全部批注列表（跨文档）：
`[{"id":3,"document_id":1,"title":"...","folder_name":"言语理解","page":12,"type":"highlight","color":"#ffe14d","content":"...","quoted_text":"...","created_at":"..."}]`（可按 document_id/type 过滤）

**GET `/api/my-notes/export?format=md`**（登录）→ `Response(content=markdown字符串, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": "attachment; filename=\"my-notes.md\""})`。格式：
```markdown
# 我的笔记
## 《标题》 第12页
> 被划词原文
- 笔记内容（高亮 #ffe14d）
```

### 4.8 我的最近阅读（工作台）

**GET `/api/my/recent`**（登录）→ 按 reading_progress.updated_at 倒序取 10：
`[{"id":1,"title":"...","folder_name":"言语理解","page":42,"updated_at":"..."}]`（id 为 document_id）

### 4.9 管理后台（全部仅管理员）

**GET `/api/admin/users`** → `[{"id":1,"username":"admin","email":"...","role":"admin","status":"normal","created_at":"..."}]`
**PATCH `/api/admin/users/{id}`** `{"status":"disabled"}` → 200 返回该用户
**POST `/api/admin/users/{id}/reset-password`** `{"new_password":"..."}` → 200 `{"message":"已重置"}`
**POST `/api/admin/invite-codes`** `{"count":3,"max_uses":1,"expires_days":7}`（均可选，默认 1/1/null）→ 201 `{"codes":["AB12CD34","EF56GH78","IJ90KL12"]}`（`secrets.token_urlsafe(6).upper()` 风格）
**GET `/api/admin/invite-codes`** → `[{"id":1,"code":"AB12CD34","max_uses":1,"used_count":1,"expires_at":null,"revoked":false,"created_at":"..."}]`
**DELETE `/api/admin/invite-codes/{id}`** → 撤销（revoked=true）→ 200 `{"message":"已作废"}`
**GET `/api/admin/stats`** → `{"users":5,"documents":12,"folders":6,"annotations":80,"total_file_size":12345678}`

### 4.10 其他

**GET `/api/health`**（公开）→ `{"status":"ok"}`

---

## 5. 文本提取流水线（后端 `services/pdf_extract.py`）

- 使用 `pypdf.PdfReader`；`len(reader.pages)` 得页数；逐页 `page.extract_text() or ""`；`reader.get_outlines()` 得大纲（取 `item` 为 tuple 时的 `item[1].page_number+1`）。
- 提取结果写入 `document_pages`（先删旧页再批量插入）、更新 documents.page_count、`text_extract_status='done'`；异常时置 `'failed'`，重试 3 次（简单 sleep 重试即可）。
- 以 FastAPI `BackgroundTasks` 触发（上传/替换/回滚后）；`processing` 状态在任务开始时置位。

## 6. CLI（`backend/app/cli.py`）

- `python -m app.cli create-admin`：交互式或读 `INIT_ADMIN_*` 环境变量创建管理员（已存在则提示）。
- `python -m app.cli ensure-admin`：幂等创建（容器启动用，读环境变量）。

## 7. 后端工程约束

- 目录：`backend/app/{main,config,database,deps,cli}.py` + `models/`、`schemas/`、`api/`、`services/`。
- `main.py`：`lifespan` 中执行 `Base.metadata.create_all` + `init_extensions()`（建 pg_trgm 扩展与 GIN 索引，按方言判断）；挂 CORS；注册所有路由。
- `deps.py`：`get_db`、`get_current_user`（解析 Bearer JWT → 校验 status → 返回 User，异常 401）、`require_admin`（非 admin → 403）。
- JWT payload：`{"sub": str(user_id), "role": ..., "exp": ..., "type": "access"|"refresh"}`。
- 密码：`argon2-cffi` 的 `PasswordHasher`。
- 所有学习数据接口强制 `WHERE user_id = 当前用户`（防越权）；管理员接口全部过 `require_admin`。
- 签名 URL：`hmac.new(secret, f"doc:{id}:{exp}".encode(), sha256).hexdigest()`。
- 登录限流：内存 dict {ip: [timestamps]}，5 次/分钟，超限 429。

## 8. 前端工程要求（`web/`，Vue3 + Vite + JS）

> 用 **JavaScript（`<script setup>`）**，不用 TypeScript（MVP 求稳）；UI 用 Element Plus（中文）；状态 Pinia；路由 Vue Router。

- `package.json`：`vue ^3.4`、`vue-router ^4`、`pinia ^2`、`element-plus ^2`、`@element-plus/icons-vue`、`axios ^1`、`pdfjs-dist ^4`；scripts：`"dev": "vite"`、`"build": "vite build"`。**不要** vue-tsc。
- `vite.config.js`：`base:'/'`、`server.proxy['/api'] → http://localhost:8000`、`build.outDir:'dist'`。
- `src/api/http.js`：axios 实例，baseURL `/api`；请求拦截器带 `Authorization: Bearer`；响应拦截器：401 时用 refresh_token 调 `/api/auth/refresh`（轮换成功后重放原请求一次；失败清空登录态跳 /login）。token 存 `localStorage`（key：`dsh_access`/`dsh_refresh`/`dsh_user`）。
- 路由与页面（`src/router/index.js`，含全局守卫：未登录跳 /login；`/admin/*` 需 role==='admin'）：
  | 路径 | 页面 | 要点 |
  |---|---|---|
  | `/login` `/register` | 登录/邀请码注册 | 注册必填邀请码 |
  | `/` | 工作台 | `GET /api/my/recent` 继续阅读、`GET /api/documents` 最近更新（取前 6）、`GET /api/my-notes` 最近 5 条 |
  | `/library` | 资料库 | 左 FolderTree（`GET /api/folders`）+ 右文件卡片（`GET /api/documents?folder_id=`）；管理员可见上传/新建文件夹/行操作 |
  | `/reader/:id` | 阅读页（★） | 见下 |
  | `/search?q=` | 检索结果 | `GET /api/search` 三组展示；content 结果点击 → `/reader/:docId?page=N` |
  | `/my-notes` | 我的笔记 | `GET /api/my-notes` 聚合 + 导出按钮（`GET /api/my-notes/export?format=md`，window.open 或 a 标签下载） |
  | `/settings` | 个人中心 | 改资料/改密码 |
  | `/admin/files` | 管理-资料 | 文件夹树管理、上传（el-upload）、替换/版本/回滚/删除/回收站 |
  | `/admin/users` | 管理-用户 | 列表、禁用/启用、重置密码 |
  | `/admin/invites` | 管理-邀请码 | 生成/列表/作废 |
- 阅读器实现要点（`src/components/PdfReader.vue` + `AnnotationLayer` + `NotePanel`）：
  1. 载入：`import * as pdfjsLib from 'pdfjs-dist'`；`import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'`；`pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl`。
  2. `getDocument(url)`（url 为签名相对路径，浏览器带 Cookie/token 无碍；签名 URL 无需额外 header）。
  3. 渲染：容器内垂直排列页面；每页 `<div class="page">` 内含 `<canvas>` 与绝对定位的文本层。文本层：`const viewport = page.getViewport({scale})`；canvas 尺寸 = viewport 尺寸；`const textContent = await page.getTextContent()`；对每个 item：`const tx = pdfjsLib.Util.transform(viewport.transform, item.transform)`；`fontHeight = Math.hypot(tx[2], tx[3])`；`left = tx[4]`；`top = tx[5] - fontHeight`；创建 `<span style="position:absolute;left:left px;top:top px;font-size:fontHeight px;line-height:fontHeight px;transform-origin:0 0">item.str</span>`，span 加 `data-page-no`。
  4. 懒加载：IntersectionObserver 观察页容器，进入视口 ±3 页才渲染（含文本层）；已渲染缓存不重绘；PDF 较大时 canvas 用 `page.render` 每页一次。
  5. 批注渲染：容器内叠加 `annotation-layer`（position:absolute 覆盖该页），按 `rect`（0~1 归一化）× 页容器当前尺寸换算：`left = rect.x1*w; top = rect.y1*h; width=(x2-x1)*w; height=(y2-y1)*h`；高亮=半透明底色 div；下划线=底部 border；波浪线=SVG path；star=角标；note=右上角便签图标。
  6. 划词创建：`mouseup` → `getSelection()` → 遍历其 range 的 `getClientRects()` → 相对页容器归一化 → 弹 Element Plus Popover 工具条（高亮/下划线/波浪线/笔记/星标，颜色 5 选 1，笔记弹输入框）→ `POST /api/documents/{id}/annotations` → 乐观更新列表。
  7. 进度：监听当前可见页（IntersectionObserver 或滚动计算），防抖 1s `PUT /api/reader/{doc_id}/progress`；打开时若 URL 带 `?page=N` 滚动到该页并闪亮该页命中词（可简化为滚动定位）。
  8. 笔记面板：右侧抽屉/栏，按页分组显示批注，可删除/改色/跳页；书签按钮（`POST/GET/DELETE /api/documents/{id}/bookmarks`）。
  9. 工具栏：返回、文件名、大纲下拉（点击跳页）、缩放 +/-、适合宽度、全屏（Fullscreen API）、笔记面板开关。
- 全局 UI：Element Plus `zh-cn` locale；页面顶栏含全局搜索框（回车 → `/search?q=`）；管理员顶栏有"管理后台"入口。
- 主题：浅色为主，简洁；图标用 @element-plus/icons-vue。

## 9. 交付要求

- 后端子代理：产出 `backend/app/**`、`backend/requirements.txt`、`backend/smoke_test.py`（TestClient + `sqlite:///./test.db` 冒烟：health→register(需先经 CLI 建 admin 再生成邀请码，或直接向 DB 插入 invite)→login→建文件夹→上传假 PDF 字节→建批注→search）。代码需自洽、缩进一致、无语法错误（无法本机运行 Python 时务必逐行自查）。
- 前端子代理：产出 `web/{package.json,vite.config.js,index.html,src/**}`；**必须**在本机执行 `npm install` 与 `npm run build` 直至成功（本机有 Node 24），并修复所有构建错误；不要创建 web/Dockerfile 与 web/nginx.conf（由主代理负责）。
