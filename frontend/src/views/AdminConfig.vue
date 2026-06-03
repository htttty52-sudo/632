<template>
  <div class="p-6 max-w-4xl mx-auto">
    <h2 class="text-xl font-bold text-green-400 mb-6">Exchange API Configuration</h2>

    <div class="mb-6 bg-gray-800 p-4 rounded-lg">
      <h3 class="text-sm font-semibold text-gray-400 mb-3">Add New Config</h3>
      <form @submit.prevent="addConfig" class="flex gap-3 flex-wrap">
        <input v-model="newConfig.exchange_name" placeholder="Exchange name" class="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm" required />
        <input v-model="newConfig.api_key" placeholder="API Key" class="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm flex-1" />
        <input v-model="newConfig.api_secret" placeholder="API Secret" type="password" class="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm flex-1" />
        <button type="submit" class="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-sm font-semibold">Add</button>
      </form>
    </div>

    <div class="bg-gray-800 rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-750">
          <tr class="text-gray-400 text-left">
            <th class="px-4 py-3">Exchange</th>
            <th class="px-4 py-3">API Key</th>
            <th class="px-4 py-3">Active</th>
            <th class="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="config in configs" :key="config.id" class="border-t border-gray-700">
            <td class="px-4 py-3">{{ config.exchange_name }}</td>
            <td class="px-4 py-3 font-mono text-xs">{{ config.api_key.slice(0, 8) }}...</td>
            <td class="px-4 py-3">
              <span :class="config.is_active ? 'text-green-400' : 'text-red-400'">
                {{ config.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="px-4 py-3">
              <button @click="deleteConfig(config.id)" class="text-red-400 hover:text-red-300 text-xs">Delete</button>
            </td>
          </tr>
          <tr v-if="configs.length === 0">
            <td colspan="4" class="px-4 py-6 text-center text-gray-500">No configs yet</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import api from '../services/api'

interface Config {
  id: number
  exchange_name: string
  api_key: string
  is_active: boolean
}

const configs = ref<Config[]>([])
const newConfig = reactive({ exchange_name: '', api_key: '', api_secret: '' })

async function loadConfigs() {
  const res = await api.get('/exchange-configs/')
  configs.value = res.data
}

async function addConfig() {
  await api.post('/exchange-configs/', { ...newConfig, is_active: true })
  newConfig.exchange_name = ''
  newConfig.api_key = ''
  newConfig.api_secret = ''
  await loadConfigs()
}

async function deleteConfig(id: number) {
  await api.delete(`/exchange-configs/${id}`)
  await loadConfigs()
}

onMounted(loadConfigs)
</script>
