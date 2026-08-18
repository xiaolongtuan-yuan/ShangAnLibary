<script setup>
import { ref } from 'vue'

// 递归文件夹树：组件通过文件名自引用
const props = defineProps({
  folders: { type: Array, default: () => [] },
  modelValue: { type: [Number, null], default: null },
  depth: { type: Number, default: 0 }
})
const emit = defineEmits(['update:modelValue'])

const expanded = ref(true)

function select(id) {
  emit('update:modelValue', id)
}
</script>

<template>
  <div class="ft-children">
    <template v-if="depth === 0">
      <div class="ft-row" :class="{ active: modelValue === null }" @click="select(null)">
        <span class="ft-name">📁 全部资料</span>
      </div>
      <div class="ft-row" :class="{ active: modelValue === 0 }" @click="select(0)">
        <span class="ft-name">🗂 未分类</span>
      </div>
    </template>

    <div v-for="f in folders" :key="f.id" class="ft-sub">
      <div
        class="ft-row"
        :class="{ active: modelValue === f.id }"
        :style="{ paddingLeft: 12 + depth * 16 + 'px' }"
        @click="select(f.id)"
      >
        <span
          v-if="f.children && f.children.length"
          class="ft-arrow"
          @click.stop="expanded = !expanded"
        >
          {{ expanded ? '▾' : '▸' }}
        </span>
        <span v-else class="ft-arrow"></span>
        <span class="ft-name">{{ f.name }}</span>
      </div>
      <FolderTree
        v-if="f.children && f.children.length && expanded"
        :folders="f.children"
        :model-value="modelValue"
        :depth="depth + 1"
        @update:model-value="select"
      />
    </div>
  </div>
</template>
