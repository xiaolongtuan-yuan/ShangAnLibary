import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 重要：全局禁用 esbuild 变换（transform）与 CSS 压缩。
// 实测证据：esbuild 的 transform 步骤会破坏 pdf.js 4.10 的打包产物，
// 导致生产环境报 "Cannot read private member #s"（本机禁用 esbuild 的构建 + Node 运行时验证通过，
// 启用 esbuild 的 Docker 构建必现）。JS 压缩改由 terser 承担（对私有字段安全，已运行时验证）。
export default defineConfig({
  base: '/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
    // 强制全局只解析一份 pdfjs-dist，杜绝任何双实例（类身份不一致 → 私有字段报错）
    dedupe: ['pdfjs-dist']
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    target: 'esnext',
    // terser 压缩（esbuild 压缩/变换均会破坏 pdf.js 私有字段）
    minify: 'terser',
    cssMinify: false,
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      output: {
        // 版本化资源路径（v2）：强制改变所有静态资源 URL，
        // 使曾缓存了错误 MIME 响应的浏览器（pdf.worker 加载失败问题）立即失效
        assetFileNames: 'assets/v2/[name]-[hash][extname]',
        chunkFileNames: 'assets/v2/[name]-[hash].js'
      }
    }
  },
  esbuild: false
})
