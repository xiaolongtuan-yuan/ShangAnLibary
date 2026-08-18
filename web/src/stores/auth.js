import { defineStore } from 'pinia'
import http, { storage } from '@/api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: storage.getUser(),
    accessToken: storage.getAccess(),
    refreshToken: storage.getRefresh()
  }),
  getters: {
    isLoggedIn: (s) => !!s.accessToken,
    isAdmin: (s) => !!s.user && s.user.role === 'admin'
  },
  actions: {
    setSession(access, refresh, user) {
      storage.setSession(access, refresh, user)
      if (access !== undefined) this.accessToken = access || ''
      if (refresh !== undefined) this.refreshToken = refresh || ''
      if (user !== undefined) this.user = user
    },
    async login(username, password) {
      const { data } = await http.post('/auth/login', { username, password })
      this.setSession(data.access_token, data.refresh_token, data.user)
      return data.user
    },
    logout() {
      this.setSession('', '', null)
    },
    async refreshUser() {
      const { data } = await http.get('/auth/me')
      this.setSession(this.accessToken, this.refreshToken, data)
      return data
    }
  }
})
