"""后端冒烟测试（契约 §9）：TestClient + SQLite。

流程：health → ensure-admin 建管理员 → 管理员登录 → 生成邀请码 → 注册普通用户 →
普通用户登录 → 建文件夹 → 上传假 PDF（提取失败可接受）→ 文档列表断言 →
批注/书签/进度 → reader 会话 → my-notes → search → 签名 URL/文件流 → my/recent → stats → PASSED。

用法：在 backend/ 目录执行 `python smoke_test.py`。
"""

import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 必须在导入 app 之前设置环境变量（settings 在 import 时读取）
os.environ["DATABASE_URL"] = "sqlite:///./smoke.db"
os.environ["SECRET_KEY"] = "smoke-test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["INIT_ADMIN_USERNAME"] = "admin"
os.environ["INIT_ADMIN_PASSWORD"] = "admin123456"
os.environ["INIT_ADMIN_EMAIL"] = "admin@example.com"
os.environ["PDF_DATA_DIR"] = os.path.join(BASE_DIR, "smoke_pdf")
os.environ["USE_X_ACCEL"] = "false"

# 清理旧库与旧文件
for target in ("smoke.db", "smoke_pdf"):
    path = os.path.join(BASE_DIR, target)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)

from fastapi.testclient import TestClient  # noqa: E402

from app.cli import ensure_admin  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_PASSWORD = "admin123456"


def main() -> None:
    with TestClient(app) as client:
        # 1. health
        resp = client.get("/api/health")
        assert resp.status_code == 200 and resp.json() == {"status": "ok"}, resp.text

        # 2. 用 ensure-admin 逻辑创建管理员（lifespan 已建表）
        ensure_admin()

        # 3. 管理员登录
        resp = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
        assert resp.status_code == 200, resp.text
        admin_data = resp.json()
        admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}
        assert admin_data["user"]["role"] == "admin"

        # 4. 生成邀请码
        resp = client.post(
            "/api/admin/invite-codes", json={"count": 1, "max_uses": 1}, headers=admin_headers
        )
        assert resp.status_code == 201, resp.text
        invite_code = resp.json()["codes"][0]

        # 5. 注册普通用户（邀请码注册后 used_count+1）
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "小明",
                "email": "ming@x.com",
                "password": "abc12345",
                "invite_code": invite_code,
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["role"] == "user"

        # 6. 普通用户登录（用邮箱登录）
        resp = client.post("/api/auth/login", json={"username": "ming@x.com", "password": "abc12345"})
        assert resp.status_code == 200, resp.text
        user_data = resp.json()
        user_headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # 7. 建文件夹（管理员）
        resp = client.post("/api/folders", json={"name": "行测", "parent_id": None}, headers=admin_headers)
        assert resp.status_code == 201, resp.text
        folder_id = resp.json()["id"]

        # 8. 上传假 PDF（管理员；文本提取失败可接受）
        fake_pdf = (
            b"%PDF-1.4 fake\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
            b"trailer\n<< /Root 1 0 R >>\n%%EOF"
        )
        resp = client.post(
            "/api/documents",
            headers=admin_headers,
            data={"folder_id": str(folder_id), "subject": "行测", "tags": '["真题"]'},
            files=[("files", ("2025言语专项.pdf", fake_pdf, "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        uploads = resp.json()
        assert len(uploads) == 1
        doc_id = uploads[0]["id"]

        # 9. 文档列表断言（含 folder_id=0 未分类过滤）
        resp = client.get("/api/documents", headers=user_headers)
        assert resp.status_code == 200, resp.text
        docs = resp.json()
        assert any(
            d["id"] == doc_id and d["folder_name"] == "行测" and d["my_annotation_count"] == 0
            for d in docs
        ), docs
        resp = client.get("/api/documents", params={"folder_id": 0}, headers=user_headers)
        assert resp.status_code == 200, resp.text

        # 10. 建批注 / 书签 / 进度
        resp = client.post(
            f"/api/documents/{doc_id}/annotations",
            headers=user_headers,
            json={
                "type": "highlight",
                "page": 1,
                "color": "#ffe14d",
                "rect": {"x1": 0.1, "y1": 0.3, "x2": 0.6, "y2": 0.33},
                "content": "这是重点笔记",
                "quoted_text": "原文片段",
            },
        )
        assert resp.status_code == 201, resp.text

        resp = client.post(
            f"/api/documents/{doc_id}/bookmarks",
            headers=user_headers,
            json={"page": 1, "label": "必背"},
        )
        assert resp.status_code == 201, resp.text

        resp = client.put(
            f"/api/reader/{doc_id}/progress", headers=user_headers, json={"page": 1, "scroll_y": 0.55}
        )
        assert resp.status_code == 200, resp.text

        # 11. reader 会话
        resp = client.get(f"/api/reader/{doc_id}", headers=user_headers)
        assert resp.status_code == 200, resp.text
        session = resp.json()
        assert len(session["annotations"]) == 1
        assert len(session["bookmarks"]) == 1
        assert session["progress"]["page"] == 1
        assert session["file_url"].startswith("/api/files/stream/")

        # 12. my-notes
        resp = client.get("/api/my-notes", headers=user_headers)
        assert resp.status_code == 200 and len(resp.json()) == 1, resp.text

        # 13. search（命中笔记组）
        resp = client.get("/api/search", params={"q": "重点"}, headers=user_headers)
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["notes"]) == 1, resp.text

        # 14. 签名 URL 与文件流（USE_X_ACCEL=false → FileResponse）
        resp = client.get(f"/api/files/{doc_id}/url", headers=user_headers)
        assert resp.status_code == 200, resp.text
        stream_url = resp.json()["url"]
        resp = client.get(stream_url)
        assert resp.status_code == 200, resp.text

        # 15. my/recent
        resp = client.get("/api/my/recent", headers=user_headers)
        assert resp.status_code == 200 and len(resp.json()) == 1, resp.text

        # 16. 管理员 stats
        resp = client.get("/api/admin/stats", headers=admin_headers)
        assert resp.status_code == 200 and resp.json()["documents"] == 1, resp.text

    print("PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)
