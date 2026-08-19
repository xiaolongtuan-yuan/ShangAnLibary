<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as pdfjsLib from 'pdfjs-dist'
// worker 走 ?url 静态资源 + workerSrc（Node 运行时验证过的组合；nginx 已对 .mjs 返回正确 MIME）
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Menu, ArrowDown, FullScreen, Loading, Document } from '@element-plus/icons-vue'
import http, { getErr } from '@/api/http'
import { ANNOTATION_COLORS, withAlpha } from '@/utils'
import NotePanel from './NotePanel.vue'
import PdfPage from './PdfPage.vue'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const props = defineProps({
  documentId: { type: [Number, String], required: true }
})

const route = useRoute()
const router = useRouter()

/* ---------- 状态 ---------- */
const containerRef = ref(null)
const selectionAnchor = ref(null)
const wrapEls = reactive({})

const loading = ref(true)
const errorMsg = ref('')
const pdfDoc = ref(null)
const docInfo = ref(null)
const pageCount = ref(0)
const pageObjs = reactive({})
const baseSizes = reactive({})

const scale = ref(1)
const fitScale = ref(1)
const fitMode = ref(true)
const currentPage = ref(1)
const showNotes = ref(true)

const annotations = ref([])
const bookmarks = ref([])
const progress = ref({ page: 1, scroll_y: 0 })

const showToolbar = ref(false)
const noteMode = ref(false)
const noteContent = ref('')
const color = ref(ANNOTATION_COLORS[0])
let selectionInfo = null // { page, rect, quotedText }

const outline = computed(() =>
  docInfo.value && Array.isArray(docInfo.value.outline) ? docInfo.value.outline : []
)

/* ---------- 布局计算 ---------- */
function setWrap(el, n) {
  if (el) wrapEls[n] = el
}

function isActive(n) {
  return Math.abs(n - currentPage.value) <= 3
}

function pageAnnotations(n) {
  return annotations.value.filter((a) => a.page === n)
}

function currentSize(n) {
  const b = baseSizes[n]
  return b ? { w: b.w * scale.value, h: b.h * scale.value } : null
}

function wrapStyle(n) {
  const s = currentSize(n)
  return s ? { width: s.w + 'px', height: s.h + 'px' } : { minHeight: '300px' }
}

function layerStyle(n) {
  const s = currentSize(n)
  return s ? { width: s.w + 'px', height: s.h + 'px' } : {}
}

// rect（0~1 归一化）x 当前页容器尺寸 -> left/top/width/height
function annoStyle(a) {
  const s = currentSize(a.page)
  const style = { position: 'absolute' }
  if (s && a.rect && a.rect.x1 != null) {
    style.left = Math.round(a.rect.x1 * s.w) + 'px'
    style.top = Math.round(a.rect.y1 * s.h) + 'px'
    style.width = Math.max(2, Math.round((a.rect.x2 - a.rect.x1) * s.w)) + 'px'
    style.height = Math.max(2, Math.round((a.rect.y2 - a.rect.y1) * s.h)) + 'px'
  } else {
    // 无 rect（note/star 等）默认右上角
    style.right = '10px'
    style.top = '10px'
  }
  return style
}

/* ---------- 会话加载 ---------- */
async function loadSession() {
  loading.value = true
  errorMsg.value = ''
  try {
    const { data } = await http.get(`/reader/${props.documentId}`)
    docInfo.value = data.document || null
    annotations.value = data.annotations || []
    bookmarks.value = data.bookmarks || []
    progress.value = data.progress || { page: 1, scroll_y: 0 }
    if (docInfo.value && docInfo.value.title) {
      document.title = `${docInfo.value.title} - 上岸书房`
    }
    if (!data.file_url) throw new Error('未获取到文件地址')
    // isEvalSupported: false 禁用 pdf.js 内部 Function/eval 路径（该路径在压缩构建下
    // 与私有字段机制冲突，导致 "Cannot read private member #s" 报错）
    const task = pdfjsLib.getDocument({ url: data.file_url, isEvalSupported: false })
    pdfDoc.value = await task.promise
    pageCount.value = pdfDoc.value.numPages
    await preloadPages()
    computeFit()
    if (fitMode.value && fitScale.value) scale.value = fitScale.value
    const qp = Number(route.query.page)
    const startPage = qp > 0 && qp <= pageCount.value ? qp : progress.value.page || 1
    currentPage.value = startPage
    await nextTick()
    scrollToPage(startPage, progress.value.scroll_y || 0)
  } catch (e) {
    console.error(e)
    errorMsg.value = getErr(e, '加载文档失败，请确认后端服务可用')
  } finally {
    loading.value = false
  }
}

// 预取全部页面对象与基准尺寸（布局稳定；页数 ≤ 数百，可接受）
async function preloadPages() {
  const doc = pdfDoc.value
  const tasks = []
  for (let i = 1; i <= doc.numPages; i++) {
    tasks.push(
      doc.getPage(i).then((p) => {
        pageObjs[i] = p
        const vp = p.getViewport({ scale: 1 })
        baseSizes[i] = { w: vp.width, h: vp.height }
      })
    )
  }
  await Promise.all(tasks)
}

/* ---------- 缩放 / 布局 ---------- */
function computeFit() {
  const c = containerRef.value
  if (!c) return
  let maxW = 0
  for (const k in baseSizes) maxW = Math.max(maxW, baseSizes[k].w)
  if (!maxW) return
  fitScale.value = Math.max(0.3, (c.clientWidth - 48) / maxW)
}

function setScale(s) {
  scale.value = Math.min(3.5, Math.max(0.3, s))
}

function zoomIn() {
  fitMode.value = false
  setScale(scale.value * 1.2)
}

function zoomOut() {
  fitMode.value = false
  setScale(scale.value / 1.2)
}

function fitWidth() {
  fitMode.value = true
  computeFit()
  setScale(fitScale.value)
}

function onResize() {
  computeFit()
  if (fitMode.value && fitScale.value) scale.value = fitScale.value
}

function toggleFullscreen() {
  const el = containerRef.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {})
  } else if (el.requestFullscreen) {
    el.requestFullscreen().catch(() => ElMessage.warning('浏览器拒绝了全屏请求'))
  } else {
    ElMessage.warning('当前浏览器不支持全屏')
  }
}

/* ---------- 滚动 / 当前页 / 进度 ---------- */
let scrollRaf = 0
let saveTimer = null

function onScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    computeCurrentPage()
    scheduleProgressSave()
  })
}

function computeCurrentPage() {
  const c = containerRef.value
  if (!c || !pageCount.value) return
  const top = c.getBoundingClientRect().top + 60
  let best = currentPage.value
  for (let i = 1; i <= pageCount.value; i++) {
    const el = wrapEls[i]
    if (!el) continue
    const r = el.getBoundingClientRect()
    if (r.bottom < top) continue
    best = i
    break
  }
  if (best !== currentPage.value) currentPage.value = best
}

function scheduleProgressSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(saveProgress, 1000)
}

async function saveProgress() {
  const c = containerRef.value
  if (!c || !pageCount.value) return
  const scrollY = c.scrollHeight > c.clientHeight ? c.scrollTop / (c.scrollHeight - c.clientHeight) : 0
  const p = { page: currentPage.value, scroll_y: Math.round(scrollY * 100) / 100 }
  progress.value = { ...progress.value, ...p }
  try {
    await http.put(`/reader/${props.documentId}/progress`, p)
  } catch (e) {
    /* 进度保存失败静默 */
  }
}

function scrollToPage(n, scrollY = 0) {
  const el = wrapEls[n]
  if (!el) return
  el.scrollIntoView({ block: 'start' })
  const c = containerRef.value
  if (c && scrollY > 0 && el.offsetHeight) {
    c.scrollTop += scrollY * el.offsetHeight
  }
  currentPage.value = n
}

function onOutlineJump(page) {
  scrollToPage(Number(page))
}

function goBack() {
  router.push('/library')
}

/* ---------- 划词批注 ---------- */
function onMouseUp(e) {
  if (e.button !== 0) return
  if (e.target && e.target.closest && e.target.closest('.anno-item')) return
  const wrap = e.target && e.target.closest ? e.target.closest('.pdf-page-wrap') : null
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !sel.toString().trim() || !wrap) {
    hideToolbar()
    return
  }
  const pageNo = Number(wrap.dataset.pageNo)
  if (!pageNo) {
    hideToolbar()
    return
  }
  const pr = wrap.getBoundingClientRect()
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (let i = 0; i < sel.rangeCount; i++) {
    const rects = sel.getRangeAt(i).getClientRects()
    for (const r of rects) {
      if (!r.width && !r.height) continue
      minX = Math.min(minX, r.left)
      minY = Math.min(minY, r.top)
      maxX = Math.max(maxX, r.right)
      maxY = Math.max(maxY, r.bottom)
    }
  }
  if (!isFinite(minX) || minX === Infinity) {
    hideToolbar()
    return
  }
  const clamp01 = (v) => Math.max(0, Math.min(1, v))
  selectionInfo = {
    page: pageNo,
    rect: {
      x1: clamp01((minX - pr.left) / pr.width),
      y1: clamp01((minY - pr.top) / pr.height),
      x2: clamp01((maxX - pr.left) / pr.width),
      y2: clamp01((maxY - pr.top) / pr.height)
    },
    quotedText: sel.toString().trim().slice(0, 500)
  }
  const anchor = selectionAnchor.value
  if (anchor) {
    anchor.style.left = (minX + maxX) / 2 + 'px'
    anchor.style.top = minY + 'px'
  }
  noteMode.value = false
  noteContent.value = ''
  showToolbar.value = true
}

function hideToolbar() {
  showToolbar.value = false
  noteMode.value = false
  noteContent.value = ''
}

async function createAnnotation(type) {
  const info = selectionInfo
  if (!info) return
  const payload = {
    type,
    page: info.page,
    color: color.value,
    rect: info.rect,
    quoted_text: info.quotedText || null,
    content: type === 'note' ? noteContent.value.trim() || null : null
  }
  // 乐观更新
  const tempId = 'temp-' + Date.now()
  annotations.value.push({ ...payload, id: tempId, created_at: new Date().toISOString() })
  hideToolbar()
  if (window.getSelection) window.getSelection().removeAllRanges()
  try {
    const { data } = await http.post(`/documents/${props.documentId}/annotations`, payload)
    const idx = annotations.value.findIndex((a) => a.id === tempId)
    if (idx >= 0) annotations.value[idx] = data
  } catch (err) {
    const idx = annotations.value.findIndex((a) => a.id === tempId)
    if (idx >= 0) annotations.value.splice(idx, 1)
    ElMessage.error(getErr(err, '批注保存失败'))
  }
}

async function deleteAnnotation(target) {
  // 兼容传入批注对象或 id（模板中传对象，NotePanel 中传 id）
  const id = target && typeof target === 'object' ? target.id : target
  if (String(id).startsWith('temp-')) {
    annotations.value = annotations.value.filter((x) => x.id !== id)
    return
  }
  try {
    await ElMessageBox.confirm('确定删除这条批注？', '删除批注', { type: 'warning' })
  } catch {
    return
  }
  try {
    await http.delete(`/annotations/${id}`)
    annotations.value = annotations.value.filter((x) => x.id !== id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function changeColor({ id, color: c }) {
  const a = annotations.value.find((x) => x.id === id)
  if (!a || String(a.id).startsWith('temp-')) return
  const old = a.color
  a.color = c
  try {
    await http.patch(`/annotations/${id}`, { color: c })
  } catch (e) {
    a.color = old
    ElMessage.error(getErr(e))
  }
}

async function addBookmark({ page, label }) {
  try {
    const { data } = await http.post(`/documents/${props.documentId}/bookmarks`, { page, label: label || null })
    bookmarks.value.push(data)
    ElMessage.success('已添加书签')
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function deleteBookmark(id) {
  try {
    await http.delete(`/bookmarks/${id}`)
    bookmarks.value = bookmarks.value.filter((b) => b.id !== id)
    ElMessage.success('已删除书签')
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

/* ---------- 生命周期 ---------- */
onMounted(() => {
  loadSession()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<template>
  <div class="reader-root">
    <!-- 工具栏 -->
    <div class="reader-toolbar">
      <el-button text @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      <span class="rt-title" :title="docInfo && docInfo.title">{{ docInfo ? docInfo.title : '阅读' }}</span>

      <el-dropdown v-if="outline.length" @command="onOutlineJump">
        <el-button text>
          <el-icon><Menu /></el-icon>大纲<el-icon><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu class="outline-menu">
            <el-dropdown-item v-for="o in outline" :key="o.title + '-' + o.page" :command="o.page">
              第 {{ o.page }} 页 · {{ o.title }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <div class="rt-spacer"></div>

      <el-button-group>
        <el-button size="small" @click="zoomOut">－</el-button>
        <el-button size="small" disabled>{{ Math.round(scale * 100) }}%</el-button>
        <el-button size="small" @click="zoomIn">＋</el-button>
      </el-button-group>
      <el-button size="small" @click="fitWidth">适合宽度</el-button>
      <el-button size="small" @click="toggleFullscreen">
        <el-icon><FullScreen /></el-icon>全屏
      </el-button>
      <el-button size="small" :type="showNotes ? 'primary' : 'default'" @click="showNotes = !showNotes">
        笔记
      </el-button>
      <span class="rt-page">第 {{ currentPage }} / {{ pageCount }} 页</span>
    </div>

    <!-- 阅读主体 -->
    <div class="reader-body">
      <div ref="containerRef" class="pdf-scroll" @scroll.passive="onScroll" @mouseup="onMouseUp">
        <div v-if="loading" class="pdf-state">
          <el-icon class="is-loading"><Loading /></el-icon>正在加载文档…
        </div>
        <div v-else-if="errorMsg" class="pdf-state">
          <p>{{ errorMsg }}</p>
          <el-button type="primary" @click="loadSession">重试</el-button>
        </div>
        <template v-else>
          <div
            v-for="n in pageCount"
            :key="n"
            class="pdf-page-wrap"
            :data-page-no="n"
            :ref="(el) => setWrap(el, n)"
            :style="wrapStyle(n)"
          >
            <PdfPage
              v-if="pageObjs[n]"
              :page-obj="pageObjs[n]"
              :page-no="n"
              :scale="scale"
              :visible="isActive(n)"
            />
            <div v-else class="pdf-page-loading" :style="wrapStyle(n)">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>

            <!-- 批注叠加层 -->
            <div v-if="pageAnnotations(n).length" class="annotation-layer" :style="layerStyle(n)">
              <div
                v-for="a in pageAnnotations(n)"
                :key="a.id"
                class="anno-item"
                :class="'anno-' + a.type"
                :style="annoStyle(a)"
              >
                <template v-if="a.type === 'highlight'">
                  <div class="anno-fill" :style="{ backgroundColor: withAlpha(a.color, 0.4) }"></div>
                </template>
                <template v-else-if="a.type === 'underline'">
                  <div class="anno-underline" :style="{ borderBottomColor: a.color }"></div>
                </template>
                <template v-else-if="a.type === 'wave'">
                  <svg class="anno-wave" viewBox="0 0 8 6" preserveAspectRatio="none">
                    <path d="M0,3 Q2,0 4,3 T8,3" :stroke="a.color" stroke-width="1.4" fill="none" />
                  </svg>
                </template>
                <template v-else-if="a.type === 'star'">
                  <span class="anno-star" :style="{ color: a.color }">★</span>
                </template>
                <template v-else-if="a.type === 'note'">
                  <span class="anno-note" :style="{ color: a.color }">
                    <el-icon :size="13"><Document /></el-icon>
                  </span>
                </template>
                <span class="anno-del" title="删除批注" @click.stop="deleteAnnotation(a)">✕</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <NotePanel
        v-if="showNotes && !loading && !errorMsg"
        :annotations="annotations"
        :bookmarks="bookmarks"
        :document-id="props.documentId"
        :current-page="currentPage"
        @delete-annotation="deleteAnnotation"
        @delete-bookmark="deleteBookmark"
        @add-bookmark="addBookmark"
        @change-color="changeColor"
        @jump="scrollToPage"
      />
    </div>

    <!-- 划词工具条（Popover 虚拟锚点） -->
    <div ref="selectionAnchor" class="selection-anchor"></div>
    <el-popover
      :visible="showToolbar"
      :virtual-ref="selectionAnchor"
      virtual-triggering
      trigger="click"
      placement="top"
      :width="380"
      popper-class="selection-pop"
    >
      <div class="sel-toolbar">
        <template v-if="!noteMode">
          <el-button size="small" type="primary" @click="createAnnotation('highlight')">高亮</el-button>
          <el-button size="small" @click="createAnnotation('underline')">下划线</el-button>
          <el-button size="small" @click="createAnnotation('wave')">波浪线</el-button>
          <el-button size="small" @click="createAnnotation('star')">星标</el-button>
          <el-button size="small" @click="noteMode = true">笔记</el-button>
          <div class="sel-colors">
            <span
              v-for="c in ANNOTATION_COLORS"
              :key="c"
              class="sel-color"
              :class="{ on: color === c }"
              :style="{ background: c }"
              :title="c"
              @click="color = c"
            ></span>
          </div>
        </template>
        <template v-else>
          <el-input v-model="noteContent" placeholder="输入笔记内容，回车保存" @keyup.enter="createAnnotation('note')" />
          <div class="sel-note-actions">
            <el-button size="small" type="primary" @click="createAnnotation('note')">保存</el-button>
            <el-button size="small" @click="noteMode = false">取消</el-button>
          </div>
        </template>
      </div>
    </el-popover>
  </div>
</template>
