<template>
  <div class="p-4">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-4">
        <h2 class="text-lg font-bold text-white">BTC/USDT Dashboard</h2>
        <ConnectionStatus :status="wsStatus" />
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">Updates/sec:</span>
        <span class="text-xs font-mono text-green-400">{{ updateRate }}</span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2">
        <OrderBook />
      </div>
      <div class="space-y-4">
        <SpreadIndicator />
        <TradeList />
      </div>
    </div>

    <div class="mt-4">
      <SpreadMatrixHeatmap />
    </div>

    <SpreadAlertToast />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import { useOrderBookStore } from '../stores/orderbook'
import { useTradesStore } from '../stores/trades'
import { useSpreadStore } from '../stores/spread'
import { useStrategyStore } from '../stores/strategy'
import type { WSMessage, UnifiedOrderBook, UnifiedTrade, SpreadMatrix, SpreadAlertEvent } from '../types/market'
import ConnectionStatus from '../components/ConnectionStatus.vue'
import OrderBook from '../components/OrderBook.vue'
import TradeList from '../components/TradeList.vue'
import SpreadIndicator from '../components/SpreadIndicator.vue'
import SpreadMatrixHeatmap from '../components/SpreadMatrixHeatmap.vue'
import SpreadAlertToast from '../components/SpreadAlertToast.vue'

const orderbookStore = useOrderBookStore()
const tradesStore = useTradesStore()
const spreadStore = useSpreadStore()
const strategyStore = useStrategyStore()
const updateRate = ref(0)

let msgCount = 0
let lastCountTime = performance.now()

function updateCounter() {
  msgCount++
  const now = performance.now()
  if (now - lastCountTime >= 1000) {
    updateRate.value = msgCount
    msgCount = 0
    lastCountTime = now
  }
}

const { status: wsStatus } = useWebSocket('/ws/market', {
  onMessage(msg: WSMessage) {
    updateCounter()
    switch (msg.type) {
      case 'orderbook':
        orderbookStore.handleOrderBook(msg.data as UnifiedOrderBook)
        break
      case 'trade':
        tradesStore.handleTrade(msg.data as UnifiedTrade)
        break
      case 'spread_matrix':
        spreadStore.handleSpreadMatrix(msg.data as SpreadMatrix)
        break
      case 'spread_alert':
        spreadStore.handleAlert(msg.data as SpreadAlertEvent)
        break
      case 'strategy_trigger':
        strategyStore.handleTriggerEvent(msg.data as any)
        break
    }
  },
})
</script>
