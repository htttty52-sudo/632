<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <h3 class="text-sm font-semibold text-gray-400 mb-3">Recent Trades</h3>
    <div class="text-xs text-gray-500 grid grid-cols-4 px-1 mb-1">
      <span>Price</span>
      <span class="text-right">Qty</span>
      <span class="text-right">Side</span>
      <span class="text-right">Time</span>
    </div>
    <div
      ref="container"
      class="overflow-y-auto"
      :style="{ height: containerHeight + 'px' }"
      @scroll="onScroll"
    >
      <div :style="{ height: totalHeight + 'px', position: 'relative' }">
        <div
          v-for="item in visibleTrades"
          :key="item.trade_id"
          class="grid grid-cols-4 px-1 text-xs font-mono absolute w-full"
          :style="{ top: item.vTop + 'px', height: ROW_HEIGHT + 'px', lineHeight: ROW_HEIGHT + 'px' }"
        >
          <span :class="item.side === 'buy' ? 'text-green-400' : 'text-red-400'">
            {{ fmtPrice(item.price) }}
          </span>
          <span class="text-right text-gray-300">{{ fmtQty(item.quantity) }}</span>
          <span class="text-right" :class="item.side === 'buy' ? 'text-green-400' : 'text-red-400'">
            {{ item.side === 'buy' ? 'BUY' : 'SELL' }}
          </span>
          <span class="text-right text-gray-500">{{ fmtTime(item.timestamp) }}</span>
        </div>
      </div>
    </div>
    <div v-if="store.trades.length === 0" class="text-center text-gray-500 py-4 text-xs">
      Waiting for trades...
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTradesStore } from '../stores/trades'
import type { UnifiedTrade } from '../types/market'

const ROW_HEIGHT = 20
const VISIBLE_ROWS = 15
const OVERSCAN = 3

const store = useTradesStore()
const containerHeight = VISIBLE_ROWS * ROW_HEIGHT
const scrollTop = ref(0)

function onScroll(e: Event) {
  scrollTop.value = (e.target as HTMLElement).scrollTop
}

const totalHeight = computed(() => store.trades.length * ROW_HEIGHT)

interface VisibleTrade extends UnifiedTrade {
  vTop: number
}

const visibleTrades = computed((): VisibleTrade[] => {
  const items = store.trades
  if (!items.length) return []
  const startIdx = Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN)
  const endIdx = Math.min(items.length, startIdx + VISIBLE_ROWS + OVERSCAN * 2)
  const result: VisibleTrade[] = []
  for (let i = startIdx; i < endIdx; i++) {
    result.push({ ...items[i], vTop: i * ROW_HEIGHT })
  }
  return result
})

function fmtPrice(p: number): string {
  return Number(p).toFixed(2)
}
function fmtQty(q: number): string {
  return Number(q).toFixed(4)
}
function fmtTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false })
}
</script>
