#!/usr/bin/env bash
# 打包项目目录（自动排除依赖库与敏感文件），输出 shangan-deploy.tar.gz
# 用法：./scripts/package.sh [输出路径]
set -e
cd "$(dirname "$0")/.."
OUT="${1:-../shangan-deploy.tar.gz}"

echo ">>> 打包中（排除 .venv / node_modules / .tools / dist / .env 等）..."
tar -czf "$OUT" \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='.tools' \
  --exclude='node_modules' \
  --exclude='web/.npm-cache' \
  --exclude='web/dist' \
  --exclude='__pycache__' \
  --exclude='*.db' \
  --exclude='smoke_pdf' \
  --exclude='uvicorn.log' \
  --exclude='uvicorn.err' \
  .

echo "✅ 打包完成：$OUT（约 $(du -h "$OUT" | cut -f1)）"
echo "   服务器上解压后执行 ./deploy.sh 即可"
