import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const role = ref<string>(localStorage.getItem('role') || 'user')
  const username = ref<string>(localStorage.getItem('username') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function login(user: string, password: string) {
    const res = await api.post('/auth/login', { username: user, password })
    token.value = res.data.access_token
    role.value = res.data.role
    username.value = user
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('role', res.data.role)
    localStorage.setItem('username', user)
  }

  async function register(user: string, password: string, userRole: string = 'user') {
    const res = await api.post('/auth/register', { username: user, password, role: userRole })
    token.value = res.data.access_token
    role.value = res.data.role
    username.value = user
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('role', res.data.role)
    localStorage.setItem('username', user)
  }

  function logout() {
    token.value = null
    role.value = 'user'
    username.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
  }

  return { token, role, username, isLoggedIn, isAdmin, login, register, logout }
})
