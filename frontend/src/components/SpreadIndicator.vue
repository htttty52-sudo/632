<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <h3 class="text-sm font-semibold text-gray-400 mb-2">Spread</h3>
    <div class="grid grid-cols-2 gap-4">
      <div>
        <span class="text-xs text-gray-500">Best Bid</span>
        <p class="text-lg font-mono text-green-400">{{ formatPrice(store.bestBid) }}</p>
      </div>
      <div>
        <span class="text-xs text-gray-500">Best Ask</span>
        <p class="text-lg font-mono text-red-400">{{ formatPrice(store.bestAsk) }}</p>
      </div>
    </div>
    <div class="mt-3 pt-3 border-t border-gray-700 grid grid-cols-2 gap-4">
      <div>
        <span class="text-xs text-gray-500">Spread</span>
        <p class="text-sm font-mono text-yellow-400">${{ formatPrice(store.spread) }}</p>
      </div>
      <div>
        <span class="text-xs text-gray-500">Spread %</span>
        <p class="text-sm font-mono text-yellow-400">{{ store.spreadPct.toFixed(4) }}%</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useOrderBookStore } from '../stores/orderbook'

const store = useOrderBookStore()

function formatPrice(p: number): string {
  return Number(p).toFixed(2)
}
</script>
