import { defineStore } from 'pinia'
import { shallowRef, computed } from 'vue'
import type { UnifiedOrderBook, OrderBookLevel } from '../types/market'

interface OrderBookState {
  exchange: string
  symbol: string
  timestamp: number
  sequence: number
  bids: OrderBookLevel[]
  asks: OrderBookLevel[]
}

const emptyState: OrderBookState = {
  exchange: '',
  symbol: 'BTC/USDT',
  timestamp: 0,
  sequence: 0,
  bids: [],
  asks: [],
}

/**
 * Compare two level arrays and return true if any price or quantity differs.
 * Short-circuits on first difference for performance.
 */
function levelsChanged(prev: OrderBookLevel[], next: OrderBookLevel[]): boolean {
  if (prev.length !== next.length) return true
  for (let i = 0; i < prev.length; i++) {
    if (prev[i].price !== next[i].price || prev[i].quantity !== next[i].quantity) {
      return true
    }
  }
  return false
}

export const useOrderBookStore = defineStore('orderbook', () => {
  const state = shallowRef<OrderBookState>(emptyState)
  let rafId: number | null = null
  let pendingData: UnifiedOrderBook | null = null

  function handleOrderBook(data: UnifiedOrderBook) {
    pendingData = data
    if (rafId === null) {
      rafId = requestAnimationFrame(flush)
    }
  }

  function flush() {
    rafId = null
    if (!pendingData) return

    const prev = state.value
    const next = pendingData
    pendingData = null

    // Only update if bids or asks actually changed
    const bidsChanged = levelsChanged(prev.bids, next.bids)
    const asksChanged = levelsChanged(prev.asks, next.asks)

    if (!bidsChanged && !asksChanged && prev.exchange === next.exchange) {
      return
    }

    state.value = {
      exchange: next.exchange,
      symbol: next.symbol,
      timestamp: next.timestamp,
      sequence: next.sequence,
      bids: bidsChanged ? next.bids : prev.bids,
      asks: asksChanged ? next.asks : prev.asks,
    }
  }

  const bestBid = computed(() => state.value.bids[0]?.price ?? 0)
  const bestAsk = computed(() => state.value.asks[0]?.price ?? 0)
  const spread = computed(() => {
    if (!bestBid.value || !bestAsk.value) return 0
    return bestAsk.value - bestBid.value
  })
  const spreadPct = computed(() => {
    if (!bestAsk.value) return 0
    return (spread.value / bestAsk.value) * 100
  })

  return { state, handleOrderBook, bestBid, bestAsk, spread, spreadPct }
})
