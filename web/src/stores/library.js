import { defineStore } from 'pinia'
import http from '@/api/http'

export const useLibraryStore = defineStore('library', {
  state: () => ({
    folders: [],
    documents: [],
    // null = 全部，0 = 未分类，>0 = 具体文件夹
    currentFolderId: null,
    loading: false
  }),
  actions: {
    async fetchFolders() {
      const { data } = await http.get('/folders')
      this.folders = data || []
      return this.folders
    },
    async fetchDocuments(folderId = this.currentFolderId) {
      this.loading = true
      try {
        const params = {}
        if (folderId === 0) params.folder_id = 0
        else if (folderId) params.folder_id = folderId
        const { data } = await http.get('/documents', { params })
        this.documents = data || []
        this.currentFolderId = folderId
        return this.documents
      } finally {
        this.loading = false
      }
    },
    setCurrentFolder(id) {
      this.currentFolderId = id
    }
  }
})
