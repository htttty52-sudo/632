<template>
  <div class="min-h-screen bg-gray-900">
    <nav class="bg-gray-800 border-b border-gray-700 px-4 py-3 flex items-center justify-between">
      <h1 class="text-lg font-bold text-green-400">Crypto Arbitrage Monitor</h1>
      <div class="flex items-center gap-4">
        <router-link v-if="auth.isLoggedIn" to="/dashboard" class="text-gray-300 hover:text-white text-sm">Dashboard</router-link>
        <router-link v-if="auth.isAdmin" to="/admin" class="text-gray-300 hover:text-white text-sm">Admin</router-link>
        <button v-if="auth.isLoggedIn" @click="auth.logout()" class="text-red-400 hover:text-red-300 text-sm">Logout</button>
      </div>
    </nav>
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from './stores/auth'
const auth = useAuthStore()
</script>
