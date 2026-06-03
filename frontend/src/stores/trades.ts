import { defineStore } from 'pinia'
import { useThrottledUpdate } from '../composables/useThrottledUpdate'
import type { UnifiedTrade } from '../types/market'

const MAX_TRADES = 100

export const useTradesStore = defineStore('trades', () => {
  const { displayState, scheduleUpdate } = useThrottledUpdate<UnifiedTrade[]>([])
  let buffer: UnifiedTrade[] = []

  function handleTrade(data: UnifiedTrade) {
    buffer = [data, ...buffer].slice(0, MAX_TRADES)
    scheduleUpdate(buffer)
  }

  function clear() {
    buffer = []
    scheduleUpdate([])
  }

  return { trades: displayState, handleTrade, clear }
})
