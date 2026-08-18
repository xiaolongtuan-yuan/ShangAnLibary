<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const active = computed(() => route.path)
</script>

<template>
  <div class="admin-layout">
    <div class="admin-header">
      <el-button text @click="router.push('/')">
        <el-icon><Back /></el-icon>返回前台
      </el-button>
      <span class="admin-title">管理后台</span>
      <el-menu mode="horizontal" :default-active="active" router class="admin-menu">
        <el-menu-item index="/admin/files">资料</el-menu-item>
        <el-menu-item index="/admin/users">用户</el-menu-item>
        <el-menu-item index="/admin/invites">邀请码</el-menu-item>
      </el-menu>
    </div>
    <div class="admin-body">
      <router-view />
    </div>
  </div>
</template>
