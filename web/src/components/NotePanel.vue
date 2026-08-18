<script setup>
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Star, Document, Delete, Brush, Bottom, Opportunity } from '@element-plus/icons-vue'
import { ANNOTATION_COLORS, ANNOTATION_TYPE_LABELS } from '@/utils'

const props = defineProps({
  annotations: { type: Array, default: () => [] },
  bookmarks: { type: Array, default: () => [] },
  documentId: { type: [Number, String], required: true },
  currentPage: { type: Number, default: 1 }
})

const emit = defineEmits(['delete-annotation', 'delete-bookmark', 'add-bookmark', 'change-color', 'jump'])

const typeIcon = { highlight: Brush, underline: Bottom, wave: Opportunity, note: Document, star: Star }

// 按页分组（新在前）
const grouped = computed(() => {
  const map = new Map()
  for (const a of props.annotations) {
    if (!map.has(a.page)) map.set(a.page, [])
    map.get(a.page).push(a)
  }
  return [...map.entries()]
    .sort((x, y) => y[0] - x[0])
    .map(([page, items]) => ({ page, items }))
})

async function onAddBookmark() {
  try {
    const { value } = await ElMessageBox.prompt(
      `为第 ${props.currentPage} 页添加书签，可输入标签（选填）`,
      '添加书签',
      { inputPlaceholder: '例如：必背、重点', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    emit('add-bookmark', { page: props.currentPage, label: (value || '').trim() || null })
  } catch {
    /* 用户取消 */
  }
}
</script>

<template>
  <aside class="note-panel">
    <div class="np-header">
      <span>笔记与书签</span>
      <el-button size="small" type="primary" plain @click="onAddBookmark">＋ 加书签</el-button>
    </div>
    <div class="np-body">
      <div class="np-section-title">批注（{{ annotations.length }}）</div>
      <div v-if="!annotations.length" class="np-empty">暂无批注，阅读时划词即可添加</div>
      <div v-for="group in grouped" :key="'g' + group.page" class="np-group">
        <div class="np-group-head" @click="emit('jump', group.page)">
          第 {{ group.page }} 页<span class="np-jump">跳转</span>
        </div>
        <div v-for="a in group.items" :key="a.id" class="np-item">
          <div class="np-item-head">
            <el-icon :size="14" :color="a.color || '#606266'">
              <component :is="typeIcon[a.type] || Document" />
            </el-icon>
            <span class="np-type-chip" :style="{ color: a.color || '#333' }">
              {{ ANNOTATION_TYPE_LABELS[a.type] || a.type }}
            </span>
            <span class="np-dot" :style="{ background: a.color || '#888' }"></span>
            <el-button link type="danger" size="small" @click="emit('delete-annotation', a.id)">删除</el-button>
          </div>
          <div v-if="a.quoted_text" class="np-quote">{{ a.quoted_text }}</div>
          <div v-if="a.content" class="np-content">{{ a.content }}</div>
          <div class="np-colors">
            <span
              v-for="c in ANNOTATION_COLORS"
              :key="c"
              class="np-color"
              :class="{ on: a.color === c }"
              :style="{ background: c }"
              :title="'改为 ' + c"
              @click="emit('change-color', { id: a.id, color: c })"
            ></span>
          </div>
        </div>
      </div>

      <div class="np-section-title">书签（{{ bookmarks.length }}）</div>
      <div v-if="!bookmarks.length" class="np-empty">暂无书签</div>
      <div v-for="b in bookmarks" :key="b.id" class="np-bm">
        <span class="np-star">★</span>
        <span class="np-bm-label" @click="emit('jump', b.page)">
          第 {{ b.page }} 页{{ b.label ? ' · ' + b.label : '' }}
        </span>
        <el-button link type="danger" size="small" @click="emit('delete-bookmark', b.id)">删除</el-button>
      </div>
    </div>
  </aside>
</template>
