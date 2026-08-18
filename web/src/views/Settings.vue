<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const profile = reactive({ username: '', email: '' })
const pwd = reactive({ old_password: '', new_password: '', confirm: '' })
const savingProfile = ref(false)
const savingPwd = ref(false)

onMounted(() => {
  profile.username = auth.user?.username || ''
  profile.email = auth.user?.email || ''
})

async function saveProfile() {
  if (!profile.username.trim()) {
    ElMessage.warning('用户名不能为空')
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(profile.email.trim())) {
    ElMessage.warning('请输入正确的邮箱')
    return
  }
  savingProfile.value = true
  try {
    const { data } = await http.patch('/users/me', {
      username: profile.username.trim(),
      email: profile.email.trim()
    })
    auth.setSession(auth.accessToken, auth.refreshToken, data)
    ElMessage.success('资料已更新')
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    savingProfile.value = false
  }
}

async function savePwd() {
  if (!pwd.old_password || !pwd.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwd.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwd.new_password !== pwd.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPwd.value = true
  try {
    await http.put('/users/me/password', {
      old_password: pwd.old_password,
      new_password: pwd.new_password
    })
    ElMessage.success('密码已修改')
    pwd.old_password = ''
    pwd.new_password = ''
    pwd.confirm = ''
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    savingPwd.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2>个人设置</h2>
    </div>

    <div class="settings-card">
      <h3>基本资料</h3>
      <el-form label-width="80px" style="max-width: 420px">
        <el-form-item label="用户名">
          <el-input v-model="profile.username" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="profile.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-tag :type="auth.isAdmin ? 'danger' : 'info'">{{ auth.isAdmin ? '管理员' : '普通用户' }}</el-tag>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="settings-card">
      <h3>修改密码</h3>
      <el-form label-width="80px" style="max-width: 420px">
        <el-form-item label="原密码">
          <el-input v-model="pwd.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwd.new_password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwd.confirm" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPwd" @click="savePwd">修改密码</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>
