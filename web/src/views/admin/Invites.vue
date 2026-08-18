<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http, { getErr } from '@/api/http'
import { fmtTime } from '@/utils'

const genForm = reactive({ count: 5, max_uses: 1, expires_days: 7 })
const generating = ref(false)
const generated = ref([])

const codes = ref([])
const loading = ref(false)

onMounted(loadCodes)

async function generate() {
  generating.value = true
  try {
    const { data } = await http.post('/admin/invite-codes', {
      count: Number(genForm.count) || 1,
      max_uses: Number(genForm.max_uses) || 1,
      expires_days: genForm.expires_days ? Number(genForm.expires_days) : null
    })
    generated.value = data.codes || []
    ElMessage.success(`已生成 ${generated.value.length} 个邀请码`)
    await loadCodes()
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    generating.value = false
  }
}

async function loadCodes() {
  loading.value = true
  try {
    codes.value = (await http.get('/admin/invite-codes')).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
}

async function copyCode(c) {
  try {
    await navigator.clipboard.writeText(c)
    ElMessage.success(`已复制：${c}`)
  } catch {
    ElMessage.info(c)
  }
}

async function revoke(item) {
  try {
    await http.delete(`/admin/invite-codes/${item.id}`)
    ElMessage.success('已作废')
    await loadCodes()
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}
</script>

<template>
  <div>
    <div class="settings-card" style="max-width: 640px">
      <h3>生成邀请码</h3>
      <el-form inline>
        <el-form-item label="数量">
          <el-input-number v-model="genForm.count" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="可注册次数">
          <el-input-number v-model="genForm.max_uses" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="有效期（天）">
          <el-input-number v-model="genForm.expires_days" :min="0" :max="365" placeholder="0 为永久" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" @click="generate">生成</el-button>
        </el-form-item>
      </el-form>
      <div v-if="generated.length" class="gen-codes">
        <el-tag
          v-for="c in generated"
          :key="c"
          size="large"
          style="cursor: pointer"
          @click="copyCode(c)"
        >
          {{ c }}
        </el-tag>
        <div style="width: 100%; color: #909399; font-size: 12px">点击邀请码即可复制</div>
      </div>
    </div>

    <div class="settings-card" style="max-width: 640px">
      <h3>邀请码列表</h3>
      <el-table :data="codes" v-loading="loading" border stripe size="small">
        <el-table-column prop="code" label="邀请码" min-width="140" />
        <el-table-column label="使用" width="100">
          <template #default="{ row }">{{ row.used_count }} / {{ row.max_uses }}</template>
        </el-table-column>
        <el-table-column label="过期时间" width="150">
          <template #default="{ row }">{{ row.expires_at ? fmtTime(row.expires_at) : '永久' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.revoked ? 'info' : 'success'" size="small">
              {{ row.revoked ? '已作废' : '有效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              size="small"
              :disabled="row.revoked"
              @click="revoke(row)"
            >
              作废
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>
