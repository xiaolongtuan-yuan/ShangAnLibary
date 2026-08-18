<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const q = ref('')
const showHeader = computed(() => !route.meta.public)
const username = computed(() => auth.user?.username || '')
const isAdmin = computed(() => auth.isAdmin)

function onSearch() {
  const kw = q.value.trim()
  if (!kw) return
  router.push({ path: '/search', query: { q: kw } })
}

function onUserCommand(cmd) {
  if (cmd === 'settings') router.push('/settings')
  else if (cmd === 'logout') onLogout()
}

async function onLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
  } catch {
    return
  }
  auth.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header v-if="showHeader" class="app-header">
      <router-link to="/" class="app-logo"><span class="logo-mark">📚</span> 上岸书房</router-link>
      <div class="app-search">
        <el-input
          v-model="q"
          placeholder="搜索资料、内容、我的笔记，回车搜索"
          clearable
          @keyup.enter="onSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
      <nav class="app-nav">
        <router-link to="/library">资料库</router-link>
        <router-link to="/my-notes">我的笔记</router-link>
        <router-link to="/settings">设置</router-link>
        <router-link v-if="isAdmin" to="/admin/files">管理后台</router-link>
      </nav>
      <el-dropdown @command="onUserCommand">
        <span class="app-user">{{ username }} <el-icon><ArrowDown /></el-icon></span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="settings">个人设置</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>
