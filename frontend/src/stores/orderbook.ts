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
 * Merge-sort diff: compare old and new arrays sorted by price.
 * Returns a new array only replacing positions that actually changed.
 * Bids: descending by price. Asks: ascending by price.
 */
function mergeDiff(
  prev: OrderBookLevel[],
  next: OrderBookLevel[]
): { result: OrderBookLevel[]; changed: boolean } {
  if (prev.length === 0 && next.length === 0) return { result: prev, changed: false }
  if (prev.length !== next.length) return { result: next, changed: true }

  let changed = false
  const result: OrderBookLevel[] = new Array(next.length)

  // Two-pointer merge: both arrays should already be sorted.
  // Walk both in order, detect mismatches.
  for (let i = 0; i < next.length; i++) {
    const p = prev[i]
    const n = next[i]
    if (p && p.price === n.price && p.quantity === n.quantity) {
      result[i] = p // reuse same object reference (no re-render for this slot)
    } else {
      result[i] = n
      changed = true
    }
  }

  return { result, changed }
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

    // Merge-sort diff: only replace positions that changed
    const bidsMerge = mergeDiff(prev.bids, next.bids)
    const asksMerge = mergeDiff(prev.asks, next.asks)

    if (!bidsMerge.changed && !asksMerge.changed && prev.exchange === next.exchange) {
      // Nothing changed, skip re-render entirely
      return
    }

    state.value = {
      exchange: next.exchange,
      symbol: next.symbol,
      timestamp: next.timestamp,
      sequence: next.sequence,
      bids: bidsMerge.changed ? bidsMerge.result : prev.bids,
      asks: asksMerge.changed ? asksMerge.result : prev.asks,
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
