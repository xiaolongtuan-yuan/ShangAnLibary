<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'
import { fmtTime } from '@/utils'

const router = useRouter()
const q = ref('')

const recent = ref([]) // 继续阅读
const recentDocs = ref([]) // 最近更新
const recentNotes = ref([]) // 最近笔记
const loading = ref(true)

onMounted(async () => {
  try {
    const [r1, r2, r3] = await Promise.all([
      http.get('/my/recent'),
      http.get('/documents'),
      http.get('/my-notes')
    ])
    recent.value = r1.data || []
    recentDocs.value = (r2.data || []).slice(0, 6)
    recentNotes.value = (r3.data || []).slice(0, 5)
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
})

function goSearch() {
  const kw = q.value.trim()
  if (!kw) return
  router.push({ path: '/search', query: { q: kw } })
}

function openDoc(id, page) {
  router.push({ path: `/reader/${id}`, query: page ? { page } : {} })
}
</script>

<template>
  <div class="page-container">
    <div class="hero">
      <h1>上岸书房</h1>
      <p>考公资料库 · PDF 在线阅读 · 划词批注 · 全文检索</p>
      <div class="hero-search">
        <el-input
          v-model="q"
          size="large"
          placeholder="搜索资料、全文内容、我的笔记…"
          clearable
          @keyup.enter="goSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button size="large" type="primary" @click="goSearch">搜索</el-button>
      </div>
    </div>

    <div v-loading="loading" class="section-card">
      <div class="section-title">📖 继续阅读</div>
      <div v-if="!recent.length" class="np-empty">还没有阅读记录，去资料库挑一份资料吧</div>
      <div v-else class="continue-grid">
        <div v-for="r in recent" :key="r.id" class="continue-card" @click="openDoc(r.id, r.page)">
          <div class="cc-title" :title="r.title">{{ r.title }}</div>
          <div class="cc-meta">
            <span v-if="r.folder_name">{{ r.folder_name }}</span>
            <span>读到第 {{ r.page }} 页</span>
            <span>{{ fmtTime(r.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="section-card">
      <div class="section-title">🆕 最近更新</div>
      <div v-if="!recentDocs.length" class="np-empty">资料库暂无资料</div>
      <div v-else class="plain-list">
        <div v-for="d in recentDocs" :key="d.id" class="plain-item" @click="openDoc(d.id)">
          <span class="pi-title" :title="d.title">{{ d.title }}</span>
          <span class="pi-meta" v-if="d.folder_name">{{ d.folder_name }}</span>
          <span class="pi-meta">{{ fmtTime(d.updated_at) }}</span>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="section-card">
      <div class="section-title">🗒 最近笔记</div>
      <div v-if="!recentNotes.length" class="np-empty">还没有笔记，阅读时划词即可添加</div>
      <div v-else class="plain-list">
        <div
          v-for="n in recentNotes"
          :key="n.id"
          class="plain-item"
          @click="openDoc(n.document_id, n.page)"
        >
          <span class="pi-title" :title="n.content || n.quoted_text">
            {{ n.content || n.quoted_text || '（无内容）' }}
          </span>
          <span class="pi-meta">{{ n.title }} · 第 {{ n.page }} 页</span>
        </div>
      </div>
    </div>
  </div>
</template>
