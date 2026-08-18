<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getErr } from '@/api/http'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function onSubmit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' && redirect ? redirect : '/')
  } catch (e) {
    ElMessage.error(getErr(e, '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">上岸书房</div>
      <div class="auth-sub">考公资料 · 在线阅读 · 划词批注</div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="账号（用户名或邮箱）">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名或邮箱"
            size="large"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
            size="large"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button class="auth-btn" type="primary" size="large" :loading="loading" @click="onSubmit">
          登 录
        </el-button>
      </el-form>
      <div class="auth-foot">
        还没有账号？<router-link to="/register">邀请码注册</router-link>
      </div>
    </div>
  </div>
</template>
