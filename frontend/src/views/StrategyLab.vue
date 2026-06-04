<template>
  <div class="p-4 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-xl font-bold text-white">策略实验室</h2>
      <span class="text-sm text-gray-400">
        总模拟盈亏: <span :class="totalPnl >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ totalPnl >= 0 ? '+' : '' }}{{ totalPnl.toFixed(2) }} USDT
        </span>
      </span>
    </div>

    <!-- Create Strategy Form -->
    <div class="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
      <h3 class="text-sm font-medium text-gray-300 mb-3">新建策略</h3>
      <div class="flex gap-3 items-end flex-wrap">
        <div>
          <label class="block text-xs text-gray-500 mb-1">策略名称</label>
          <input v-model="form.name" type="text" placeholder="我的套利策略"
            class="bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white w-48" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">初始资金 (USDT)</label>
          <input v-model.number="form.balance" type="number" min="100"
            class="bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-white w-32" />
        </div>
        <button @click="addCondition" class="px-3 py-1.5 text-xs rounded bg-blue-600 text-white hover:bg-blue-500">
          + 条件
        </button>
        <button @click="submitStrategy" :disabled="!canSubmit"
          class="px-4 py-1.5 text-sm rounded bg-green-600 text-white hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed">
          保存策略
        </button>
      </div>

      <!-- Conditions -->
      <div v-if="form.conditions.length" class="mt-3 space-y-2">
        <div v-for="(cond, idx) in form.conditions" :key="idx"
          class="flex items-center gap-2 bg-gray-900 rounded px-3 py-2">
          <select v-model="cond.field" class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white">
            <option value="spread_pct">价差 %</option>
            <option value="best_spread">最佳价差</option>
            <option value="volume">交易量</option>
          </select>
          <select v-model="cond.operator" class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white">
            <option value=">">&gt;</option>
            <option value=">=">&gt;=</option>
            <option value="<">&lt;</option>
            <option value="<=">&lt;=</option>
            <option value="==">==</option>
          </select>
          <input v-model.number="cond.value" type="number" step="0.01"
            class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white w-24" />
          <button @click="form.conditions.splice(idx, 1)" class="text-red-400 hover:text-red-300 text-xs">删除</button>
        </div>
      </div>
    </div>

    <!-- Strategy List -->
    <div class="bg-gray-800 rounded-lg border border-gray-700 mb-6">
      <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 class="text-sm font-medium text-gray-300">我的策略</h3>
        <button @click="store.fetchStrategies()" class="text-xs text-gray-500 hover:text-white">刷新</button>
      </div>
      <div v-if="loading" class="p-4 text-center text-gray-500 text-sm">加载中...</div>
      <div v-else-if="!strategies.length" class="p-4 text-center text-gray-500 text-sm">暂无策略</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-gray-500 text-xs border-b border-gray-700">
            <th class="px-4 py-2 text-left">名称</th>
            <th class="px-4 py-2 text-left">条件</th>
            <th class="px-4 py-2 text-right">余额</th>
            <th class="px-4 py-2 text-right">盈亏</th>
            <th class="px-4 py-2 text-center">状态</th>
            <th class="px-4 py-2 text-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in strategies" :key="s.id" class="border-b border-gray-700/50 hover:bg-gray-700/30">
            <td class="px-4 py-2 text-white">{{ s.name }}</td>
            <td class="px-4 py-2 text-gray-400 text-xs">
              <span v-for="(c, i) in s.conditions" :key="i" class="inline-block mr-2 bg-gray-900 px-1.5 py-0.5 rounded">
                {{ fieldLabel(c.field) }} {{ c.operator }} {{ c.value }}
              </span>
            </td>
            <td class="px-4 py-2 text-right text-white font-mono">{{ s.simulated_balance.toFixed(2) }}</td>
            <td class="px-4 py-2 text-right font-mono"
              :class="s.pnl >= 0 ? 'text-green-400' : 'text-red-400'">
              {{ s.pnl >= 0 ? '+' : '' }}{{ s.pnl.toFixed(2) }}
            </td>
            <td class="px-4 py-2 text-center">
              <span :class="s.active ? 'text-green-400' : 'text-gray-500'" class="text-xs">
                {{ s.active ? '运行中' : '已暂停' }}
              </span>
            </td>
            <td class="px-4 py-2 text-center space-x-2">
              <button @click="toggleStrategy(s)"
                class="text-xs px-2 py-0.5 rounded"
                :class="s.active ? 'bg-yellow-600/20 text-yellow-400' : 'bg-green-600/20 text-green-400'">
                {{ s.active ? '暂停' : '启动' }}
              </button>
              <button @click="viewLogs(s.id)" class="text-xs px-2 py-0.5 rounded bg-blue-600/20 text-blue-400">
                日志
              </button>
              <button @click="removeStrategy(s.id)" class="text-xs px-2 py-0.5 rounded bg-red-600/20 text-red-400">
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Recent Triggers (Real-time) -->
    <div v-if="recentTriggers.length" class="bg-gray-800 rounded-lg border border-gray-700 mb-6">
      <div class="px-4 py-3 border-b border-gray-700">
        <h3 class="text-sm font-medium text-gray-300">实时触发 <span class="text-xs text-green-400 animate-pulse">●</span></h3>
      </div>
      <div class="max-h-48 overflow-y-auto">
        <div v-for="(t, i) in recentTriggers" :key="i"
          class="px-4 py-2 border-b border-gray-700/30 text-xs flex items-center justify-between">
          <span class="text-gray-300">
            <span class="text-white font-medium">{{ t.strategy_name }}</span>
            {{ t.symbol }} {{ t.exchange_a }}→{{ t.exchange_b }}
          </span>
          <span :class="t.simulated_pnl >= 0 ? 'text-green-400' : 'text-red-400'" class="font-mono">
            {{ t.simulated_pnl >= 0 ? '+' : '' }}{{ t.simulated_pnl.toFixed(4) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Logs -->
    <div v-if="showLogs" class="bg-gray-800 rounded-lg border border-gray-700">
      <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 class="text-sm font-medium text-gray-300">执行日志</h3>
        <button @click="showLogs = false" class="text-xs text-gray-500 hover:text-white">关闭</button>
      </div>
      <div v-if="!logs.length" class="p-4 text-center text-gray-500 text-sm">暂无日志</div>
      <div v-else class="max-h-64 overflow-y-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-gray-700">
              <th class="px-3 py-2 text-left">时间</th>
              <th class="px-3 py-2 text-left">交易对</th>
              <th class="px-3 py-2 text-left">方向</th>
              <th class="px-3 py-2 text-right">价差%</th>
              <th class="px-3 py-2 text-right">模拟盈亏</th>
              <th class="px-3 py-2 text-right">余额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id" class="border-b border-gray-700/30">
              <td class="px-3 py-1.5 text-gray-400">{{ log.triggered_at?.slice(0, 19) }}</td>
              <td class="px-3 py-1.5 text-white">{{ log.exchange_a }}/{{ log.exchange_b }}</td>
              <td class="px-3 py-1.5 text-gray-300">{{ log.direction }}</td>
              <td class="px-3 py-1.5 text-right text-gray-300 font-mono">{{ log.spread_pct.toFixed(4) }}%</td>
              <td class="px-3 py-1.5 text-right font-mono"
                :class="log.simulated_pnl >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ log.simulated_pnl >= 0 ? '+' : '' }}{{ log.simulated_pnl.toFixed(4) }}
              </td>
              <td class="px-3 py-1.5 text-right text-white font-mono">{{ log.balance_after.toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useStrategyStore, type ConditionRule } from '../stores/strategy'

const store = useStrategyStore()

const showLogs = ref(false)

const strategies = computed(() => store.strategies)
const logs = computed(() => store.logs)
const loading = computed(() => store.loading)
const totalPnl = computed(() => store.totalPnl)
const recentTriggers = computed(() => store.recentTriggers)

const form = ref({
  name: '',
  balance: 10000,
  conditions: [] as ConditionRule[],
})

const canSubmit = computed(() =>
  form.value.name.trim() && form.value.conditions.length > 0 && form.value.balance >= 100
)

function addCondition() {
  form.value.conditions.push({ field: 'spread_pct', operator: '>', value: 0.1 })
}

function fieldLabel(field: string) {
  const map: Record<string, string> = { spread_pct: '价差%', best_spread: '最佳价差', volume: '交易量' }
  return map[field] || field
}

async function submitStrategy() {
  if (!canSubmit.value) return
  await store.createStrategy(form.value.name, form.value.conditions, form.value.balance)
  form.value = { name: '', balance: 10000, conditions: [] }
}

async function toggleStrategy(s: { id: number; active: boolean }) {
  await store.updateStrategy(s.id, { active: !s.active })
}

async function removeStrategy(id: number) {
  await store.deleteStrategy(id)
}

async function viewLogs(strategyId: number) {
  showLogs.value = true
  await store.fetchLogs(strategyId)
}

onMounted(() => {
  store.fetchStrategies()
})
</script>
