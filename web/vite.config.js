import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 沙箱环境（无法 spawn esbuild 子进程）下用 VITE_NO_ESBUILD=1 关闭 esbuild 变换与压缩；
// 常规环境构建不受影响（esbuild 默认开启）。
const noEsbuild = process.env.VITE_NO_ESBUILD === '1'

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
    // pdfjs-dist v4 产物含较新语法，放宽目标避免构建报错
    target: 'esnext',
    // 用 terser 压缩：esbuild 的标识符/私有字段重命名会破坏 pdf.js 的
    // 私有字段（生产环境报 "Cannot read private member #s"），terser 不重命名私有成员
    minify: 'terser',
    cssMinify: noEsbuild ? false : undefined,
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
  esbuild: noEsbuild ? false : undefined
})
