<script setup>
import { MoreFilled } from '@element-plus/icons-vue'
import { fmtSize, fmtTime } from '@/utils'

const props = defineProps({
  doc: { type: Object, required: true },
  admin: { type: Boolean, default: false }
})

const emit = defineEmits(['open', 'replace', 'versions', 'delete'])

function onCommand(cmd, doc) {
  if (cmd === 'open') emit('open', doc.id)
  else emit(cmd, doc)
}
</script>

<template>
  <div class="doc-card" @click="emit('open', doc.id)">
    <div class="doc-card-head">
      <span class="doc-type">PDF</span>
      <el-dropdown v-if="admin" trigger="click" @command="(c) => onCommand(c, doc)" @click.stop>
        <el-icon class="doc-more" :size="16"><MoreFilled /></el-icon>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="replace">替换文件</el-dropdown-item>
            <el-dropdown-item command="versions">版本记录</el-dropdown-item>
            <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div class="doc-title" :title="doc.title">{{ doc.title }}</div>
    <div class="doc-meta">
      <span v-if="doc.subject">科目：{{ doc.subject }}</span>
      <span v-if="doc.stage">{{ doc.stage }}</span>
      <span>{{ doc.page_count ?? '—' }} 页</span>
      <span>{{ fmtSize(doc.file_size) }}</span>
    </div>
    <div class="doc-meta2">
      <span>{{ fmtTime(doc.updated_at) }} 更新</span>
      <span v-if="doc.my_annotation_count">批注 {{ doc.my_annotation_count }}</span>
      <span v-if="doc.my_progress_page">读到第 {{ doc.my_progress_page }} 页</span>
    </div>
  </div>
</template>
