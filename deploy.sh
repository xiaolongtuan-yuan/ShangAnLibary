#!/usr/bin/env bash
# 上岸书房 · 一键部署脚本
# 用法：./deploy.sh （首次运行会自动提示配置 .env）
set -e
cd "$(dirname "$0")"

echo "=============================================================="
echo "  上岸书房 · 一键部署"
echo "=============================================================="

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  已生成 .env 文件，请先编辑它："
  echo "    1) SECRET_KEY           → 随机长字符串（openssl rand -hex 32）"
  echo "    2) INIT_ADMIN_PASSWORD  → 管理员初始密码"
  echo "    3) POSTGRES_PASSWORD    → 数据库密码"
  echo "    然后重新运行 ./deploy.sh"
  exit 1
fi

echo ">>> [1/4] 构建并启动容器（首次构建约需 3~10 分钟）..."
docker compose up -d --build

echo ">>> [2/4] 等待服务就绪..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
  [ "$i" = "60" ] && echo "⚠️  等待超时，请用 docker compose logs backend 排查"
done

echo ">>> [3/4] 确保管理员账号存在..."
docker compose exec -T backend python -m app.cli ensure-admin || true

echo ">>> [4/4] 完成"
IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "=============================================================="
echo " ✅ 部署完成！"
echo "    访问地址: http://${IP:-服务器公网IP}"
echo "    管理员账号: ${INIT_ADMIN_USERNAME:-admin}"
echo "    管理员密码: 见 .env 的 INIT_ADMIN_PASSWORD"
echo ""
echo "    下一步："
echo "    1. 用管理员登录 →「管理后台 → 邀请码」生成邀请码"
echo "    2. 把邀请码发给朋友，他们在 /register 注册即可使用"
echo "    3. 在「管理后台 → 资料」中创建文件夹并上传 PDF"
echo "=============================================================="
