// 通用常量与格式化工具

export const ANNOTATION_COLORS = ['#ffe14d', '#ff9f43', '#ff6b6b', '#51cf66', '#4dabf7']

export const ANNOTATION_TYPE_LABELS = {
  highlight: '高亮',
  underline: '下划线',
  wave: '波浪线',
  note: '笔记',
  star: '星标'
}

// '#rrggbb' -> 'rgba(r,g,b,alpha)'
export function withAlpha(hex, alpha) {
  if (!hex || hex.length < 7) return hex
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function fmtSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return String(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 文件夹树拍平为下拉选项 [{id, name}]
export function flattenFolders(nodes, prefix = '') {
  const out = []
  for (const f of nodes || []) {
    const name = prefix ? `${prefix} / ${f.name}` : f.name
    out.push({ id: f.id, name })
    out.push(...flattenFolders(f.children, name))
  }
  return out
}
