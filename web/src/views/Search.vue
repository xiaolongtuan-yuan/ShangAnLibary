<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'
import { ANNOTATION_TYPE_LABELS, fmtTime } from '@/utils'

const route = useRoute()
const router = useRouter()

const q = ref(route.query.q || '')
const scope = ref('all')
const result = ref({ files: [], content: [], notes: [] })
const loading = ref(false)
const searched = ref(false)

const scopeOptions = [
  { value: 'all', label: '全部' },
  { value: 'file', label: '文件名' },
  { value: 'content', label: '全文内容' },
  { value: 'note', label: '我的笔记' }
]

async function doSearch() {
  const kw = q.value.trim()
  if (!kw) {
    result.value = { files: [], content: [], notes: [] }
    searched.value = false
    return
  }
  loading.value = true
  try {
    const { data } = await http.get('/search', { params: { q: kw, scope: scope.value } })
    result.value = data || { files: [], content: [], notes: [] }
    searched.value = true
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
}

// 命中词分段（避免 v-html XSS）
function parts(text) {
  if (!text) return [{ t: '', hit: false }]
  const kw = q.value.trim()
  if (!kw) return [{ t: text, hit: false }]
  const lower = text.toLowerCase()
  const klower = kw.toLowerCase()
  const out = []
  let i = 0
  while (i < text.length) {
    const idx = lower.indexOf(klower, i)
    if (idx < 0) {
      out.push({ t: text.slice(i), hit: false })
      break
    }
    if (idx > i) out.push({ t: text.slice(i, idx), hit: false })
    out.push({ t: text.slice(idx, idx + kw.length), hit: true })
    i = idx + kw.length
  }
  return out
}

function openContent(item) {
  router.push({ path: `/reader/${item.document_id}`, query: { page: item.page } })
}

function openDoc(id, page) {
  router.push({ path: `/reader/${id}`, query: page ? { page } : {} })
}

watch(() => route.query.q, (v) => {
  q.value = v || ''
  doSearch()
})

watch(scope, doSearch)

onMounted(() => {
  if (q.value.trim()) doSearch()
})
</script>

<template>
  <div class="page-container">
    <div class="search-box">
      <el-input
        v-model="q"
        size="large"
        placeholder="输入关键词搜索（连续 2~4 字效果最佳）"
        clearable
        @keyup.enter="doSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button size="large" type="primary" @click="doSearch">搜索</el-button>
    </div>

    <el-radio-group v-model="scope" style="margin-bottom: 16px">
      <el-radio-button v-for="s in scopeOptions" :key="s.value" :value="s.value">
        {{ s.label }}
      </el-radio-button>
    </el-radio-group>

    <div v-loading="loading">
      <template v-if="searched">
        <!-- 文件 -->
        <div v-if="result.files && result.files.length" class="result-group">
          <div class="result-title">📄 文件（{{ result.files.length }}）</div>
          <div v-for="f in result.files" :key="'f' + f.id" class="result-item" @click="openDoc(f.id)">
            <div class="ri-title">{{ f.title }}</div>
            <div class="ri-meta">
              <span v-if="f.folder_name">{{ f.folder_name }}</span>
              <span v-if="f.subject">{{ f.subject }}</span>
              <span>命中：{{ f.matched_field }}</span>
            </div>
          </div>
        </div>

        <!-- 内容 -->
        <div v-if="result.content && result.content.length" class="result-group">
          <div class="result-title">📑 全文内容（{{ result.content.length }}）</div>
          <div
            v-for="(c, i) in result.content"
            :key="'c' + c.document_id + '-' + c.page + '-' + i"
            class="result-item"
            @click="openContent(c)"
          >
            <div class="ri-title">{{ c.title }} <el-tag size="small">第 {{ c.page }} 页</el-tag></div>
            <div class="ri-snippet">
              <template v-for="(p, j) in parts(c.snippet)" :key="j">
                <mark v-if="p.hit" class="hit">{{ p.t }}</mark>
                <template v-else>{{ p.t }}</template>
              </template>
            </div>
            <div class="ri-meta" v-if="c.folder_name">
              <span>{{ c.folder_name }}</span>
              <span>点击直达该页</span>
            </div>
          </div>
        </div>

        <!-- 我的笔记 -->
        <div v-if="result.notes && result.notes.length" class="result-group">
          <div class="result-title">🗒 我的笔记（{{ result.notes.length }}）</div>
          <div v-for="n in result.notes" :key="'n' + n.id" class="result-item" @click="openDoc(n.document_id, n.page)">
            <div class="ri-title">
              {{ n.title }}
              <el-tag size="small">{{ ANNOTATION_TYPE_LABELS[n.type] || n.type }}</el-tag>
            </div>
            <div class="ri-snippet" v-if="n.quoted_text">「{{ n.quoted_text }}」</div>
            <div class="ri-snippet" v-if="n.content">{{ n.content }}</div>
            <div class="ri-meta">
              <span>第 {{ n.page }} 页</span>
              <span>{{ fmtTime(n.created_at) }}</span>
            </div>
          </div>
        </div>

        <el-empty
          v-if="!result.files.length && !result.content.length && !result.notes.length"
          description="没有找到相关内容"
        />
      </template>
    </div>
  </div>
</template>
