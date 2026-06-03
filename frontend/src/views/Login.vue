<template>
  <div class="flex items-center justify-center min-h-[80vh]">
    <div class="bg-gray-800 p-8 rounded-lg shadow-xl w-full max-w-sm">
      <h2 class="text-2xl font-bold text-center mb-6 text-green-400">Login</h2>
      <form @submit.prevent="handleSubmit">
        <div class="mb-4">
          <label class="block text-sm text-gray-400 mb-1">Username</label>
          <input
            v-model="form.username"
            type="text"
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-green-400"
            required
          />
        </div>
        <div class="mb-4">
          <label class="block text-sm text-gray-400 mb-1">Password</label>
          <input
            v-model="form.password"
            type="password"
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-green-400"
            required
          />
        </div>
        <div class="mb-4">
          <label class="flex items-center gap-2 text-sm text-gray-400">
            <input v-model="isRegister" type="checkbox" class="accent-green-400" />
            Register new account
          </label>
        </div>
        <div v-if="isRegister" class="mb-4">
          <label class="block text-sm text-gray-400 mb-1">Role</label>
          <select v-model="form.role" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <p v-if="error" class="text-red-400 text-sm mb-3">{{ error }}</p>
        <button
          type="submit"
          class="w-full py-2 bg-green-600 hover:bg-green-500 rounded font-semibold transition"
        >
          {{ isRegister ? 'Register' : 'Login' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const error = ref('')
const isRegister = ref(false)
const form = reactive({ username: '', password: '', role: 'user' })

async function handleSubmit() {
  error.value = ''
  try {
    if (isRegister.value) {
      await auth.register(form.username, form.password, form.role)
    } else {
      await auth.login(form.username, form.password)
    }
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed'
  }
}
</script>
