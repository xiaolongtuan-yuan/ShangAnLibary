import axios from 'axios'

const ACCESS_KEY = 'dsh_access'
const REFRESH_KEY = 'dsh_refresh'
const USER_KEY = 'dsh_user'

export const storage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY) || '',
  getRefresh: () => localStorage.getItem(REFRESH_KEY) || '',
  getUser: () => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    } catch {
      return null
    }
  },
  // user 传 undefined 表示不动 user 键；null 表示清除；对象表示写入
  setSession(access, refresh, user) {
    if (access !== undefined) {
      if (access) localStorage.setItem(ACCESS_KEY, access)
      else localStorage.removeItem(ACCESS_KEY)
    }
    if (refresh !== undefined) {
      if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
      else localStorage.removeItem(REFRESH_KEY)
    }
    if (user !== undefined) {
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
      else localStorage.removeItem(USER_KEY)
    }
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
  }
}

const http = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 请求拦截器：附加 Bearer token
http.interceptors.request.use((config) => {
  const token = storage.getAccess()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 时用 refresh token 轮换并重放原请求一次；失败清空登录态跳登录页
let refreshPromise = null

function tryRefresh() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post('/api/auth/refresh', { refresh_token: storage.getRefresh() })
      .then((res) => {
        const data = res.data || {}
        if (data.access_token) {
          storage.setSession(data.access_token, data.refresh_token || storage.getRefresh(), undefined)
        }
        return data
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function isAuthUrl(url = '') {
  return url.includes('/auth/')
}

function redirectToLogin() {
  storage.clear()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

http.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { response, config } = error
    const status = response ? response.status : 0
    if (status === 401 && config && !config._retried && !isAuthUrl(config.url)) {
      if (!storage.getRefresh()) {
        redirectToLogin()
        return Promise.reject(error)
      }
      config._retried = true
      try {
        await tryRefresh()
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${storage.getAccess()}`
        return http(config)
      } catch (refreshError) {
        redirectToLogin()
        return Promise.reject(refreshError)
      }
    }
    return Promise.reject(error)
  }
)

// 从 FastAPI 错误结构里提取中文提示
export function getErr(e, fallback = '请求失败，请稍后重试') {
  const detail = e && e.response && e.response.data && e.response.data.detail
  if (detail) return detail
  return (e && e.message) || fallback
}

export default http
