#!/usr/bin/env bash
# 上岸书房 · 备份脚本（数据库 + PDF 文件）
# 建议 crontab 每日执行：0 3 * * * /path/to/scripts/backup.sh >> /var/log/shangan-backup.log 2>&1
set -e
cd "$(dirname "$0")/.."

# 读取 .env 中的数据库账号
set -a; [ -f .env ] && source .env; set +a
DB_USER="${POSTGRES_USER:-study}"
DB_NAME="${POSTGRES_DB:-study}"

STAMP=$(date +%F_%H%M%S)
mkdir -p backup

echo ">>> [1/2] 备份 PostgreSQL（backup/db_${STAMP}.sql.gz）..."
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "backup/db_${STAMP}.sql.gz"

echo ">>> [2/2] 备份 PDF 文件卷（backup/pdf_${STAMP}.tar.gz）..."
docker run --rm -v shangan_pdfdata:/data:ro -v "$(pwd)/backup:/backup" alpine \
  tar czf "/backup/pdf_${STAMP}.tar.gz" -C /data .

echo ">>> 完成。旧备份请自行清理（建议保留最近 7 份）。"
ls -lh backup/ | tail -5
