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
    }
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
    minify: noEsbuild ? false : 'esbuild',
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
