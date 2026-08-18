#!/usr/bin/env bash
# 修复 Docker 镜像加速源：改用 1ms.run 等可用镜像（需要 root 权限：sudo ./scripts/fix-docker-mirror.sh）
# 适用：拉取 postgres/python/node/nginx 等 docker.io 镜像时报 "failed to resolve reference" / "no such host"
set -e
cd "$(dirname "$0")/.."

DAEMON=/etc/docker/daemon.json
MIRRORS='["https://docker.1ms.run","https://docker.m.daocloud.io","https://dockerproxy.net"]'

if [ "$(id -u)" -ne 0 ]; then
  echo "⚠️  需要 root 权限，请用 sudo 运行本脚本"
  exit 1
fi

echo ">>> 写入 registry-mirrors 到 $DAEMON ..."
if command -v python3 >/dev/null 2>&1; then
  python3 - "$DAEMON" "$MIRRORS" <<'PY'
import json, os, sys
path, mirrors = sys.argv[1], json.loads(sys.argv[2])
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = {}
data["registry-mirrors"] = mirrors
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("已更新", path)
PY
elif command -v jq >/dev/null 2>&1; then
  if [ -f "$DAEMON" ]; then
    jq -S --argjson m "$MIRRORS" '. + {registry-mirrors: $m}' "$DAEMON" > "$DAEMON.tmp" && mv "$DAEMON.tmp" "$DAEMON"
  else
    echo "{\"registry-mirrors\":$MIRRORS}" > "$DAEMON"
  fi
  echo "已更新 $DAEMON"
else
  echo "❌ 需要 python3 或 jq，请先安装其一"
  exit 1
fi

echo ">>> 重启 Docker 服务..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart docker
elif command -v service >/dev/null 2>&1; then
  service docker restart
else
  echo "请手动重启 Docker 服务"
fi

echo ">>> 验证镜像源..."
docker info 2>/dev/null | sed -n '/Registry Mirrors/,+4p' || true

echo ""
echo "✅ 完成！现在重新拉取镜像："
echo "   docker compose pull"
echo "   ./deploy.sh"
