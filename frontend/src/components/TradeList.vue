<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <h3 class="text-sm font-semibold text-gray-400 mb-3">Recent Trades</h3>
    <div class="text-xs text-gray-500 grid grid-cols-4 px-2 mb-1">
      <span>Price</span>
      <span class="text-right">Qty</span>
      <span class="text-right">Side</span>
      <span class="text-right">Time</span>
    </div>
    <div class="max-h-[400px] overflow-y-auto">
      <div
        v-for="trade in visibleTrades"
        :key="trade.trade_id"
        class="grid grid-cols-4 px-2 py-0.5 text-xs font-mono"
      >
        <span :class="trade.side === 'buy' ? 'text-green-400' : 'text-red-400'">
          {{ formatPrice(trade.price) }}
        </span>
        <span class="text-right text-gray-300">{{ formatQty(trade.quantity) }}</span>
        <span class="text-right" :class="trade.side === 'buy' ? 'text-green-400' : 'text-red-400'">
          {{ trade.side.toUpperCase() }}
        </span>
        <span class="text-right text-gray-500">{{ formatTime(trade.timestamp) }}</span>
      </div>
      <div v-if="visibleTrades.length === 0" class="text-center text-gray-500 py-4">
        Waiting for trades...
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTradesStore } from '../stores/trades'

const store = useTradesStore()
const visibleTrades = computed(() => store.trades.slice(0, 50))

function formatPrice(p: number): string {
  return Number(p).toFixed(2)
}

function formatQty(q: number): string {
  return Number(q).toFixed(4)
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false })
}
</script>
