import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import type { BacktestRequest, BacktestResult, AvailableRange } from '../types/backtest'

export const useBacktestStore = defineStore('backtest', () => {
  const result = ref<BacktestResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const availableRanges = ref<AvailableRange[]>([])

  async function runBacktest(request: BacktestRequest) {
    loading.value = true
    error.value = null
    result.value = null
    try {
      const res = await api.post('/backtest/run', request)
      result.value = res.data
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Backtest failed'
    } finally {
      loading.value = false
    }
  }

  async function fetchAvailableRanges() {
    try {
      const res = await api.get('/backtest/available-ranges')
      availableRanges.value = res.data.ranges || []
    } catch {
      availableRanges.value = []
    }
  }

  function clearResult() {
    result.value = null
    error.value = null
  }

  return {
    result,
    loading,
    error,
    availableRanges,
    runBacktest,
    fetchAvailableRanges,
    clearResult,
  }
})
