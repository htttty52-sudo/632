import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useThrottledUpdate } from '../composables/useThrottledUpdate'
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

export const useOrderBookStore = defineStore('orderbook', () => {
  const { displayState, scheduleUpdate } = useThrottledUpdate<OrderBookState>(emptyState)

  function handleOrderBook(data: UnifiedOrderBook) {
    scheduleUpdate({
      exchange: data.exchange,
      symbol: data.symbol,
      timestamp: data.timestamp,
      sequence: data.sequence,
      bids: data.bids,
      asks: data.asks,
    })
  }

  const bestBid = computed(() => displayState.value.bids[0]?.price ?? 0)
  const bestAsk = computed(() => displayState.value.asks[0]?.price ?? 0)
  const spread = computed(() => {
    if (!bestBid.value || !bestAsk.value) return 0
    return bestAsk.value - bestBid.value
  })
  const spreadPct = computed(() => {
    if (!bestAsk.value) return 0
    return (spread.value / bestAsk.value) * 100
  })

  return { state: displayState, handleOrderBook, bestBid, bestAsk, spread, spreadPct }
})
