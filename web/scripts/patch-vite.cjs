// 沙箱构建补丁：把 vite 的 optimizeSafeRealPathSync 中 `exec("net use")`
// （spawn cmd 探测网络盘，沙箱下 EPERM 崩溃）替换为直接使用 realpathSync.native。
// 运行：node scripts/patch-vite.cjs   （已备份 *.orig，可还原）
'use strict'
const fs = require('fs')
const path = require('path')

const f = path.join(__dirname, '..', 'node_modules', 'vite', 'dist', 'node', 'chunks', 'dep-BK3b2jBa.js')
const bak = f + '.orig'

if (!fs.existsSync(bak)) {
  fs.copyFileSync(f, bak)
}

let src = fs.readFileSync(f, 'utf8')

const marker = 'exec("net use", (error, stdout) => {'
const idx = src.indexOf(marker)
if (idx === -1) {
  console.error('PATTERN NOT FOUND — 可能已被补丁或版本不同')
  process.exit(1)
}

// 找到该 exec 调用所在函数体尾部：匹配到 "  });" 结束（exec 回调后紧跟函数右括号）
const tailStart = idx
const tailEnd = src.indexOf('  });', tailStart)
if (tailEnd === -1) {
  console.error('TAIL NOT FOUND')
  process.exit(1)
}

// 替换 exec(...) 整段（从 exec 到 "  });"）为直接赋值
src = src.slice(0, tailStart) + 'safeRealpathSync = fs__default.realpathSync.native;' + src.slice(tailEnd + '  });'.length)

fs.writeFileSync(f, src)
console.log('patched OK')
