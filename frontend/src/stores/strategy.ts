import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export interface ConditionRule {
  field: 'spread_pct' | 'best_spread' | 'volume'
  operator: '>' | '<' | '>=' | '<=' | '=='
  value: number
}

export interface StrategyItem {
  id: number
  user_id: number
  name: string
  conditions: ConditionRule[]
  active: boolean
  simulated_balance: number
  initial_balance: number
  pnl: number
  created_at: string | null
}

export interface StrategyLogItem {
  id: number
  strategy_id: number
  triggered_at: string | null
  symbol: string
  exchange_a: string
  exchange_b: string
  direction: string
  spread_pct: number
  simulated_quantity: number
  simulated_pnl: number
  balance_after: number
  condition_snapshot: string
}

export interface StrategyTriggerEvent {
  strategy_id: number
  strategy_name: string
  user_id: number
  symbol: string
  exchange_a: string
  exchange_b: string
  direction: string
  spread_pct: number
  simulated_pnl: number
  balance_after: number
}

export const useStrategyStore = defineStore('strategy', () => {
  const strategies = ref<StrategyItem[]>([])
  const logs = ref<StrategyLogItem[]>([])
  const loading = ref(false)
  const recentTriggers = ref<StrategyTriggerEvent[]>([])

  const totalPnl = computed(() =>
    strategies.value.reduce((sum, s) => sum + s.pnl, 0)
  )

  async function fetchStrategies() {
    loading.value = true
    try {
      const res = await api.get('/strategies/')
      strategies.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createStrategy(name: string, conditions: ConditionRule[], balance: number) {
    const res = await api.post('/strategies/', { name, conditions, simulated_balance: balance })
    strategies.value.unshift(res.data)
    return res.data
  }

  async function updateStrategy(id: number, data: { name?: string; conditions?: ConditionRule[]; active?: boolean }) {
    const res = await api.put(`/strategies/${id}`, data)
    const idx = strategies.value.findIndex(s => s.id === id)
    if (idx !== -1) strategies.value[idx] = res.data
    return res.data
  }

  async function deleteStrategy(id: number) {
    await api.delete(`/strategies/${id}`)
    strategies.value = strategies.value.filter(s => s.id !== id)
  }

  async function fetchLogs(strategyId?: number) {
    const params: Record<string, any> = { limit: 50 }
    if (strategyId) params.strategy_id = strategyId
    const res = await api.get('/strategies/logs', { params })
    logs.value = res.data
  }

  function handleTriggerEvent(event: StrategyTriggerEvent) {
    recentTriggers.value.unshift(event)
    if (recentTriggers.value.length > 20) recentTriggers.value.pop()
    const strat = strategies.value.find(s => s.id === event.strategy_id)
    if (strat) {
      strat.simulated_balance = event.balance_after
      strat.pnl = event.balance_after - strat.initial_balance
    }
  }

  return {
    strategies, logs, loading, recentTriggers, totalPnl,
    fetchStrategies, createStrategy, updateStrategy,
    deleteStrategy, fetchLogs, handleTriggerEvent,
  }
})
