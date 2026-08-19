#!/usr/bin/env bash
# 上岸书房 · 增量更新脚本：git 拉取最新代码 + 重建服务（Docker 数据卷保留）
# 用法：./scripts/update.sh
set -e
cd "$(dirname "$0")/.."

echo ">>> [1/3] 拉取最新代码..."
git pull

echo ">>> [2/3] 重新构建并启动（数据库与 PDF 数据卷不受影响）..."
docker compose up -d --build

echo ">>> [3/3] 确保管理员账号存在..."
docker compose exec -T backend python -m app.cli ensure-admin || true

echo ""
echo "✅ 更新完成！访问 http://<服务器IP> 验证即可"
