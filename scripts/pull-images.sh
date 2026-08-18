#!/usr/bin/env bash
# 预拉取全部基础镜像（自动重试，规避镜像源偶发的 EOF/超时/元数据失败）
# 用法：./scripts/pull-images.sh  然后 ./deploy.sh
set -e
cd "$(dirname "$0")/.."

IMAGES=(
  "postgres:16-alpine"
  "python:3.12-slim"
  "node:20-alpine"
  "nginx:alpine"
)

for img in "${IMAGES[@]}"; do
  echo ">>> 拉取 $img ..."
  n=0
  until docker pull "$img"; do
    n=$((n + 1))
    if [ "$n" -ge 5 ]; then
      echo "❌ $img 连续 5 次拉取失败，请检查镜像源（sudo ./scripts/fix-docker-mirror.sh）"
      exit 1
    fi
    echo "⚠️  第 $n 次失败，3 秒后重试..."
    sleep 3
  done
done

echo ""
echo "✅ 全部基础镜像就绪！现在执行："
echo "   ./deploy.sh"
