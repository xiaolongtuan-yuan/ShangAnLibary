<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { getErr } from '@/api/http'
import { fmtTime } from '@/utils'

const users = ref([])
const loading = ref(false)

const resetTarget = ref(null)
const showReset = ref(false)
const newPassword = ref('')

onMounted(loadUsers)

async function loadUsers() {
  loading.value = true
  try {
    users.value = (await http.get('/admin/users')).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
}

async function toggleStatus(u) {
  const next = u.status === 'disabled' ? 'normal' : 'disabled'
  const action = next === 'disabled' ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定${action}用户「${u.username}」？`, action, { type: 'warning' })
  } catch {
    return
  }
  try {
    const { data } = await http.patch(`/admin/users/${u.id}`, { status: next })
    Object.assign(u, data)
    ElMessage.success(`已${action}`)
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

function openReset(u) {
  resetTarget.value = u
  newPassword.value = ''
  showReset.value = true
}

async function doReset() {
  if (newPassword.value.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  try {
    await http.post(`/admin/users/${resetTarget.value.id}/reset-password`, {
      new_password: newPassword.value
    })
    ElMessage.success('密码已重置')
    showReset.value = false
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}
</script>

<template>
  <div>
    <div class="toolbar-row">
      <span style="color: #909399">共 {{ users.length }} 个用户</span>
    </div>
    <el-table :data="users" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" min-width="130" />
      <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
      <el-table-column label="角色" width="90">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
            {{ row.role === 'admin' ? '管理员' : '用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'normal' ? 'success' : 'danger'">
            {{ row.status === 'normal' ? '正常' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link :type="row.status === 'normal' ? 'danger' : 'success'" size="small" @click="toggleStatus(row)">
            {{ row.status === 'normal' ? '禁用' : '启用' }}
          </el-button>
          <el-button link type="primary" size="small" @click="openReset(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showReset" title="重置密码" width="420px">
      <p style="margin: 0 0 12px; color: #909399">为用户「{{ resetTarget ? resetTarget.username : '' }}」设置新密码</p>
      <el-input
        v-model="newPassword"
        type="password"
        show-password
        placeholder="新密码（至少 8 位）"
        @keyup.enter="doReset"
      />
      <template #footer>
        <el-button @click="showReset = false">取消</el-button>
        <el-button type="primary" @click="doReset">重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>
