<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'

const router = useRouter()

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirm: '',
  invite_code: ''
})
const loading = ref(false)

async function onSubmit() {
  if (!form.username.trim()) return ElMessage.warning('请输入用户名')
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return ElMessage.warning('请输入正确的邮箱')
  if (form.password.length < 8) return ElMessage.warning('密码至少 8 位')
  if (form.password !== form.confirm) return ElMessage.warning('两次输入的密码不一致')
  if (!form.invite_code.trim()) return ElMessage.warning('注册需要邀请码')
  loading.value = true
  try {
    await http.post('/auth/register', {
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      invite_code: form.invite_code.trim()
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (e) {
    ElMessage.error(getErr(e, '注册失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">上岸书房</div>
      <div class="auth-sub">邀请码注册</div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" />
        </el-form-item>
        <el-form-item label="邮箱" required>
          <el-input v-model="form.email" placeholder="请输入邮箱" size="large" />
        </el-form-item>
        <el-form-item label="密码（至少 8 位）" required>
          <el-input v-model="form.password" type="password" show-password placeholder="设置密码" size="large" />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input v-model="form.confirm" type="password" show-password placeholder="再次输入密码" size="large" />
        </el-form-item>
        <el-form-item label="邀请码" required>
          <el-input v-model="form.invite_code" placeholder="请输入邀请码" size="large" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button class="auth-btn" type="primary" size="large" :loading="loading" @click="onSubmit">
          注 册
        </el-button>
      </el-form>
      <div class="auth-foot">
        已有账号？<router-link to="/login">直接登录</router-link>
      </div>
    </div>
  </div>
</template>
