import { defineStore } from 'pinia'
import { shallowRef } from 'vue'
import type { UnifiedTrade } from '../types/market'

const MAX_TRADES = 100

export const useTradesStore = defineStore('trades', () => {
  const trades = shallowRef<UnifiedTrade[]>([])
  let buffer: UnifiedTrade[] = []
  let rafId: number | null = null
  let dirty = false

  function handleTrade(data: UnifiedTrade) {
    buffer = [data, ...buffer].slice(0, MAX_TRADES)
    dirty = true
    if (rafId === null) {
      rafId = requestAnimationFrame(flush)
    }
  }

  function flush() {
    rafId = null
    if (dirty) {
      trades.value = buffer
      dirty = false
    }
  }

  function clear() {
    buffer = []
    trades.value = []
    dirty = false
  }

  return { trades, handleTrade, clear }
})
