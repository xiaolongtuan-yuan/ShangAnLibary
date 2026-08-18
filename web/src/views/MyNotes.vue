<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'
import { ANNOTATION_TYPE_LABELS, fmtTime } from '@/utils'

const router = useRouter()
const notes = ref([])
const loading = ref(false)
const exporting = ref(false)
const typeFilter = ref('')

const typeOptions = [
  { value: '', label: '全部类型' },
  { value: 'highlight', label: '高亮' },
  { value: 'underline', label: '下划线' },
  { value: 'wave', label: '波浪线' },
  { value: 'note', label: '笔记' },
  { value: 'star', label: '星标' }
]

onMounted(loadNotes)

async function loadNotes() {
  loading.value = true
  try {
    const params = {}
    if (typeFilter.value) params.type = typeFilter.value
    notes.value = (await http.get('/my-notes', { params })).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
}

// 按文件分组
const groups = computed(() => {
  const map = new Map()
  for (const n of notes.value) {
    if (!map.has(n.document_id)) {
      map.set(n.document_id, {
        document_id: n.document_id,
        title: n.title,
        folder_name: n.folder_name,
        items: []
      })
    }
    map.get(n.document_id).items.push(n)
  }
  return [...map.values()]
})

function openNote(n) {
  router.push({ path: `/reader/${n.document_id}`, query: { page: n.page } })
}

async function exportMd() {
  exporting.value = true
  try {
    const res = await http.get('/my-notes/export', { params: { format: 'md' }, responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'my-notes.md'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出 Markdown')
  } catch (e) {
    ElMessage.error(getErr(e, '导出失败'))
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2>我的笔记</h2>
      <div>
        <el-select v-model="typeFilter" style="width: 140px; margin-right: 10px" @change="loadNotes">
          <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-button type="primary" :icon="Download" :loading="exporting" @click="exportMd">
          导出 Markdown
        </el-button>
      </div>
    </div>

    <div v-loading="loading">
      <div v-for="g in groups" :key="g.document_id" class="section-card">
        <div class="section-title" style="margin-bottom: 8px">
          📚 {{ g.title }}
          <span style="font-size: 12px; color: #909399; font-weight: 400">
            {{ g.folder_name || '' }} · {{ g.items.length }} 条
          </span>
        </div>
        <div class="plain-list">
          <div v-for="n in g.items" :key="n.id" class="plain-item" @click="openNote(n)">
            <span class="np-dot" :style="{ background: n.color || '#888' }"></span>
            <span class="pi-title" style="flex: none; width: 70px; font-size: 12px; color: #909399">
              第 {{ n.page }} 页
            </span>
            <span class="pi-title" :title="n.content || n.quoted_text">
              {{ n.content || n.quoted_text || '（无内容）' }}
            </span>
            <el-tag size="small">{{ ANNOTATION_TYPE_LABELS[n.type] || n.type }}</el-tag>
            <span class="pi-meta">{{ fmtTime(n.created_at) }}</span>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && !notes.length" description="还没有笔记，阅读时划词即可添加" />
    </div>
  </div>
</template>
