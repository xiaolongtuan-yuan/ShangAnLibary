#!/usr/bin/env bash
# 上岸书房 · 恢复脚本（先停服务再恢复，谨慎使用）
set -e
cd "$(dirname "$0")/.."

set -a; [ -f .env ] && source .env; set +a
DB_USER="${POSTGRES_USER:-study}"
DB_NAME="${POSTGRES_DB:-study}"

DB_DUMP="${1:-$(ls -t backup/db_*.sql.gz 2>/dev/null | head -1)}"
PDF_TAR="${2:-$(ls -t backup/pdf_*.tar.gz 2>/dev/null | head -1)}"

[ -z "$DB_DUMP" ] && { echo "未找到数据库备份"; exit 1; }
echo ">>> 停止服务..."
docker compose stop backend web

echo ">>> 恢复数据库：$DB_DUMP"
gunzip -c "$DB_DUMP" | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"

if [ -n "$PDF_TAR" ]; then
  echo ">>> 恢复 PDF 文件：$PDF_TAR"
  docker run --rm -v shangan_pdfdata:/data -v "$(pwd)/backup:/backup" alpine \
    sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$PDF_TAR") -C /data"
fi

echo ">>> 重新启动..."
docker compose start
echo ">>> 恢复完成。"
