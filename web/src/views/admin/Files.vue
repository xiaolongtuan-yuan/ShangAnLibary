<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Upload, FolderAdd, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { getErr } from '@/api/http'
import FolderTree from '@/components/FolderTree.vue'
import { flattenFolders, fmtSize, fmtTime } from '@/utils'

const tab = ref('files')

/* ---- 文件夹 ---- */
const folders = ref([])
const selectedFolder = ref(null)

const showNewFolder = ref(false)
const newFolderForm = reactive({ name: '', parent_id: null })

const showRenameFolder = ref(false)
const renameForm = reactive({ id: null, name: '' })

const folderOptions = computed(() => flattenFolders(folders.value))
const canEditFolder = computed(() => selectedFolder.value && selectedFolder.value > 0)

/* ---- 文档 ---- */
const documents = ref([])
const loading = ref(false)

const showUpload = ref(false)
const uploading = ref(false)
const uploadFiles = ref([])
const uploadForm = reactive({ folder_id: null, subject: '', stage: '', year: '', source: '', tags: '' })

const showReplace = ref(false)
const replacing = ref(false)
const replaceDoc = ref(null)
const replaceFiles = ref([])
const replaceNote = ref('')

const showVersions = ref(false)
const versionsDoc = ref(null)
const versions = ref([])

/* ---- 回收站 ---- */
const trashList = ref([])
const trashLoading = ref(false)

onMounted(async () => {
  await refreshFolders()
  await loadDocs(null)
})

async function refreshFolders() {
  try {
    folders.value = (await http.get('/folders')).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function loadDocs(folderId) {
  loading.value = true
  try {
    const params = {}
    if (folderId === 0) params.folder_id = 0
    else if (folderId) params.folder_id = folderId
    const { data } = await http.get('/documents', { params })
    documents.value = data || []
    selectedFolder.value = folderId
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    loading.value = false
  }
}

function onSelectFolder(id) {
  loadDocs(id)
}

function statusLabel(s) {
  return { pending: '待处理', processing: '处理中', done: '已完成', failed: '失败' }[s] || s
}

function statusTag(s) {
  return { pending: 'info', processing: 'warning', done: 'success', failed: 'danger' }[s] || 'info'
}

/* ---- 文件夹管理 ---- */
async function submitNewFolder() {
  if (!newFolderForm.name.trim()) {
    ElMessage.warning('请输入文件夹名称')
    return
  }
  try {
    await http.post('/folders', {
      name: newFolderForm.name.trim(),
      parent_id: newFolderForm.parent_id || null
    })
    ElMessage.success('已创建')
    showNewFolder.value = false
    newFolderForm.name = ''
    newFolderForm.parent_id = null
    await refreshFolders()
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

function openRename() {
  if (!canEditFolder.value) return
  const f = findFolder(folders.value, selectedFolder.value)
  renameForm.id = selectedFolder.value
  renameForm.name = f ? f.name : ''
  showRenameFolder.value = true
}

function findFolder(nodes, id) {
  for (const f of nodes || []) {
    if (f.id === id) return f
    const hit = findFolder(f.children, id)
    if (hit) return hit
  }
  return null
}

async function submitRename() {
  if (!renameForm.name.trim()) {
    ElMessage.warning('请输入新名称')
    return
  }
  try {
    await http.patch(`/folders/${renameForm.id}`, { name: renameForm.name.trim() })
    ElMessage.success('已重命名')
    showRenameFolder.value = false
    await refreshFolders()
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function deleteFolder() {
  if (!canEditFolder.value) return
  try {
    await ElMessageBox.confirm('确定删除该文件夹？删除前请确保其为空', '删除文件夹', { type: 'warning' })
  } catch {
    return
  }
  try {
    const { data } = await http.delete(`/folders/${selectedFolder.value}`)
    ElMessage.success((data && data.message) || '已删除')
    selectedFolder.value = null
    await refreshFolders()
    await loadDocs(null)
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

/* ---- 上传 ---- */
function openUploadDialog() {
  uploadFiles.value = []
  Object.assign(uploadForm, {
    folder_id: selectedFolder.value && selectedFolder.value > 0 ? selectedFolder.value : null,
    subject: '',
    stage: '',
    year: '',
    source: '',
    tags: ''
  })
  showUpload.value = true
}

async function submitUpload() {
  const raws = uploadFiles.value.map((f) => f.raw).filter(Boolean)
  if (!raws.length) {
    ElMessage.warning('请选择 PDF 文件')
    return
  }
  const fd = new FormData()
  for (const raw of raws) fd.append('files', raw)
  if (uploadForm.folder_id) fd.append('folder_id', uploadForm.folder_id)
  if (uploadForm.subject.trim()) fd.append('subject', uploadForm.subject.trim())
  if (uploadForm.stage.trim()) fd.append('stage', uploadForm.stage.trim())
  if (uploadForm.year.trim()) fd.append('year', uploadForm.year.trim())
  if (uploadForm.source.trim()) fd.append('source', uploadForm.source.trim())
  if (uploadForm.tags.trim()) {
    const tags = uploadForm.tags
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (tags.length) fd.append('tags', JSON.stringify(tags))
  }
  uploading.value = true
  try {
    const { data } = await http.post('/documents', fd)
    ElMessage.success(`上传成功 ${data ? data.length : 0} 个文件`)
    showUpload.value = false
    await loadDocs(selectedFolder.value)
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    uploading.value = false
  }
}

/* ---- 替换 ---- */
function openReplace(doc) {
  replaceDoc.value = doc
  replaceFiles.value = []
  replaceNote.value = ''
  showReplace.value = true
}

async function submitReplace() {
  const raw = replaceFiles.value[0] && replaceFiles.value[0].raw
  if (!raw) {
    ElMessage.warning('请选择替换文件')
    return
  }
  const fd = new FormData()
  fd.append('file', raw)
  if (replaceNote.value.trim()) fd.append('note', replaceNote.value.trim())
  replacing.value = true
  try {
    await http.post(`/documents/${replaceDoc.value.id}/replace`, fd)
    ElMessage.success('已替换，正在重新提取文本')
    showReplace.value = false
    await loadDocs(selectedFolder.value)
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    replacing.value = false
  }
}

/* ---- 版本 ---- */
async function openVersions(doc) {
  versionsDoc.value = doc
  versions.value = []
  showVersions.value = true
  try {
    versions.value = (await http.get(`/documents/${doc.id}/versions`)).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function rollback(v) {
  try {
    await ElMessageBox.confirm(
      `确定回滚到第 ${v.version_no} 版？当前文件将被该版本替换`,
      '版本回滚',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await http.post(`/documents/${versionsDoc.value.id}/rollback`, { version_no: v.version_no })
    ElMessage.success('已回滚')
    showVersions.value = false
    await loadDocs(selectedFolder.value)
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

/* ---- 删除（软删除） ---- */
async function removeDoc(doc) {
  try {
    await ElMessageBox.confirm(`确定删除《${doc.title}》？将移入回收站`, '删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await http.delete(`/documents/${doc.id}`)
    ElMessage.success('已移入回收站')
    await loadDocs(selectedFolder.value)
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

/* ---- 回收站 ---- */
async function loadTrash() {
  trashLoading.value = true
  try {
    trashList.value = (await http.get('/trash')).data || []
  } catch (e) {
    ElMessage.error(getErr(e))
  } finally {
    trashLoading.value = false
  }
}

async function restoreDoc(doc) {
  try {
    await http.post(`/trash/${doc.id}/restore`)
    ElMessage.success('已恢复')
    await loadTrash()
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}

async function purgeDoc(doc) {
  try {
    await ElMessageBox.confirm(
      `彻底删除《${doc.title}》？文件、版本、批注等将一并删除且不可恢复`,
      '彻底删除',
      { type: 'warning', confirmButtonText: '彻底删除' }
    )
  } catch {
    return
  }
  try {
    await http.delete(`/trash/${doc.id}`)
    ElMessage.success('已彻底删除')
    await loadTrash()
  } catch (e) {
    ElMessage.error(getErr(e))
  }
}
</script>

<template>
  <div>
    <el-tabs v-model="tab" @tab-change="(name) => (name === 'trash' ? loadTrash() : null)">
      <el-tab-pane label="资料管理" name="files">
        <div class="admin-files-layout">
          <aside class="af-side">
            <FolderTree :folders="folders" :model-value="selectedFolder" @update:model-value="onSelectFolder" />
            <div class="folder-actions">
              <el-button size="small" type="primary" plain :icon="FolderAdd" @click="showNewFolder = true">
                新建
              </el-button>
              <el-button size="small" plain :icon="Edit" :disabled="!canEditFolder" @click="openRename">
                重命名
              </el-button>
              <el-button size="small" type="danger" plain :icon="Delete" :disabled="!canEditFolder" @click="deleteFolder">
                删除
              </el-button>
            </div>
          </aside>
          <div class="af-main">
            <div class="toolbar-row">
              <el-button type="primary" :icon="Upload" @click="openUploadDialog">上传资料</el-button>
              <span style="color: #909399">共 {{ documents.length }} 份</span>
            </div>
            <el-table :data="documents" v-loading="loading" border stripe>
              <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
              <el-table-column prop="subject" label="科目" width="90" />
              <el-table-column prop="stage" label="阶段" width="80" />
              <el-table-column label="大小" width="90">
                <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
              </el-table-column>
              <el-table-column prop="page_count" label="页数" width="70" />
              <el-table-column prop="version" label="版本" width="70" />
              <el-table-column label="索引" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.text_extract_status)" size="small">
                    {{ statusLabel(row.text_extract_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="更新时间" width="150">
                <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="190" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openVersions(row)">版本</el-button>
                  <el-button link type="primary" size="small" @click="openReplace(row)">替换</el-button>
                  <el-button link type="danger" size="small" @click="removeDoc(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="回收站" name="trash">
        <el-table :data="trashList" v-loading="trashLoading" border stripe>
          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="删除时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.deleted_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="restoreDoc(row)">恢复</el-button>
              <el-button link type="danger" size="small" @click="purgeDoc(row)">彻底删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建文件夹 -->
    <el-dialog v-model="showNewFolder" title="新建文件夹" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newFolderForm.name" placeholder="文件夹名称" />
        </el-form-item>
        <el-form-item label="上级目录">
          <el-select v-model="newFolderForm.parent_id" placeholder="不选则为根目录" clearable style="width: 100%">
            <el-option v-for="f in folderOptions" :key="f.id" :label="f.name" :value="f.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewFolder = false">取消</el-button>
        <el-button type="primary" @click="submitNewFolder">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重命名 -->
    <el-dialog v-model="showRenameFolder" title="重命名文件夹" width="400px">
      <el-input v-model="renameForm.name" placeholder="新名称" @keyup.enter="submitRename" />
      <template #footer>
        <el-button @click="showRenameFolder = false">取消</el-button>
        <el-button type="primary" @click="submitRename">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上传 -->
    <el-dialog v-model="showUpload" title="上传资料（PDF）" width="560px">
      <el-form label-width="90px">
        <el-form-item label="文件">
          <el-upload
            v-model:file-list="uploadFiles"
            drag
            multiple
            :auto-upload="false"
            accept="application/pdf,.pdf"
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em>（可多选）</div>
          </el-upload>
        </el-form-item>
        <el-form-item label="所属文件夹">
          <el-select v-model="uploadForm.folder_id" placeholder="不选则为未分类" clearable style="width: 100%">
            <el-option v-for="f in folderOptions" :key="f.id" :label="f.name" :value="f.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="uploadForm.subject" placeholder="如：行测 / 申论" />
        </el-form-item>
        <el-form-item label="阶段">
          <el-input v-model="uploadForm.stage" placeholder="如：基础 / 强化 / 冲刺" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input v-model="uploadForm.year" placeholder="如：2025" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="uploadForm.source" placeholder="来源说明（选填）" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="uploadForm.tags" placeholder="逗号分隔，如：真题, 高频" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 替换 -->
    <el-dialog v-model="showReplace" title="替换文件（保留批注，生成新版本）" width="480px">
      <p style="margin: 0 0 12px; color: #909399">
        《{{ replaceDoc ? replaceDoc.title : '' }}》 当前版本 v{{ replaceDoc ? replaceDoc.version : '' }}
      </p>
      <el-form label-width="80px">
        <el-form-item label="新文件">
          <el-upload
            v-model:file-list="replaceFiles"
            :auto-upload="false"
            :limit="1"
            accept="application/pdf,.pdf"
          >
            <el-button :icon="Upload">选择 PDF 文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="replaceNote" placeholder="本次替换说明（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReplace = false">取消</el-button>
        <el-button type="primary" :loading="replacing" @click="submitReplace">替换</el-button>
      </template>
    </el-dialog>

    <!-- 版本 -->
    <el-dialog v-model="showVersions" title="版本记录" width="560px">
      <el-table :data="versions" border stripe>
        <el-table-column prop="version_no" label="版本" width="80" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="rollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>
