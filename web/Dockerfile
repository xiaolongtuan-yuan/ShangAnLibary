# ===== 构建阶段 =====
FROM node:20-alpine AS build
WORKDIR /app
# 连同 lockfile 一起复制并用 npm ci，保证构建依赖与本地一致（避免 pdfjs-dist 版本漂移导致 worker 哈希变化）
COPY package.json package-lock.json ./
# 国内服务器可换镜像源加速；失败自动回退官方源
RUN npm ci --registry=https://registry.npmmirror.com --replace-registry-host=always \
    || npm ci --registry=https://registry.npmjs.org
COPY . .
RUN npm run build

# ===== 运行阶段 =====
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
