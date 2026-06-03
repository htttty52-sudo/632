<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <div class="flex justify-between items-center mb-3">
      <h3 class="text-sm font-semibold text-gray-400">Order Book</h3>
      <span class="text-xs text-gray-500">{{ state.exchange }} · {{ state.symbol }}</span>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <!-- Asks (reversed so lowest ask is at bottom) -->
      <div>
        <div class="text-xs text-gray-500 grid grid-cols-3 px-2 mb-1">
          <span>Price</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div class="space-y-0">
          <div
            v-for="(level, i) in asksReversed"
            :key="'a' + i"
            class="grid grid-cols-3 px-2 py-0.5 text-xs font-mono relative"
          >
            <div class="absolute inset-0 bg-red-900/20 origin-right" :style="{ width: barWidth(level.quantity, maxAskQty) + '%' }"></div>
            <span class="relative text-red-400">{{ formatPrice(level.price) }}</span>
            <span class="relative text-right text-gray-300">{{ formatQty(level.quantity) }}</span>
            <span class="relative text-right text-gray-500">{{ formatQty(askCumulative[i]) }}</span>
          </div>
        </div>
      </div>

      <!-- Bids -->
      <div>
        <div class="text-xs text-gray-500 grid grid-cols-3 px-2 mb-1">
          <span>Price</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div class="space-y-0">
          <div
            v-for="(level, i) in state.bids.slice(0, 20)"
            :key="'b' + i"
            class="grid grid-cols-3 px-2 py-0.5 text-xs font-mono relative"
          >
            <div class="absolute inset-0 bg-green-900/20 origin-left" :style="{ width: barWidth(level.quantity, maxBidQty) + '%' }"></div>
            <span class="relative text-green-400">{{ formatPrice(level.price) }}</span>
            <span class="relative text-right text-gray-300">{{ formatQty(level.quantity) }}</span>
            <span class="relative text-right text-gray-500">{{ formatQty(bidCumulative[i]) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useOrderBookStore } from '../stores/orderbook'

const store = useOrderBookStore()
const state = computed(() => store.state)

const asksReversed = computed(() => {
  return [...state.value.asks.slice(0, 20)].reverse()
})

const maxBidQty = computed(() => {
  return Math.max(...state.value.bids.slice(0, 20).map(l => l.quantity), 0.001)
})

const maxAskQty = computed(() => {
  return Math.max(...state.value.asks.slice(0, 20).map(l => l.quantity), 0.001)
})

const bidCumulative = computed(() => {
  let sum = 0
  return state.value.bids.slice(0, 20).map(l => { sum += l.quantity; return sum })
})

const askCumulative = computed(() => {
  const asks = [...state.value.asks.slice(0, 20)].reverse()
  let sum = 0
  return asks.map(l => { sum += l.quantity; return sum })
})

function barWidth(qty: number, max: number): number {
  return Math.min((qty / max) * 100, 100)
}

function formatPrice(p: number): string {
  return Number(p).toFixed(2)
}

function formatQty(q: number): string {
  return Number(q).toFixed(4)
}
</script>
