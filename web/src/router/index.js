import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('@/views/Register.vue'), meta: { public: true } },
  { path: '/', name: 'home', component: () => import('@/views/Home.vue') },
  { path: '/library', name: 'library', component: () => import('@/views/Library.vue') },
  { path: '/reader/:id', name: 'reader', component: () => import('@/views/Reader.vue') },
  { path: '/search', name: 'search', component: () => import('@/views/Search.vue') },
  { path: '/my-notes', name: 'my-notes', component: () => import('@/views/MyNotes.vue') },
  { path: '/settings', name: 'settings', component: () => import('@/views/Settings.vue') },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { admin: true },
    redirect: '/admin/files',
    children: [
      { path: 'files', name: 'admin-files', component: () => import('@/views/admin/Files.vue'), meta: { admin: true } },
      { path: 'users', name: 'admin-users', component: () => import('@/views/admin/Users.vue'), meta: { admin: true } },
      { path: 'invites', name: 'admin-invites', component: () => import('@/views/admin/Invites.vue'), meta: { admin: true } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局守卫：未登录跳 /login；/admin/* 需 admin 角色
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (auth.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
      return '/'
    }
    return true
  }
  if (!auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.isAdmin) {
    return '/'
  }
  return true
})

export default router
