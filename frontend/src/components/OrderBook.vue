<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <div class="flex justify-between items-center mb-3">
      <h3 class="text-sm font-semibold text-gray-400">Order Book</h3>
      <span class="text-xs text-gray-500">{{ state.exchange }} · {{ state.symbol }}</span>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <!-- Asks (sell side) - reversed so lowest ask at bottom -->
      <div class="flex flex-col">
        <div class="text-xs text-gray-500 grid grid-cols-3 px-1 mb-1 sticky top-0 bg-gray-800">
          <span>Price</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div
          ref="askContainer"
          class="overflow-y-auto"
          :style="{ height: containerHeight + 'px' }"
          @scroll="onAskScroll"
        >
          <div :style="{ height: askTotalHeight + 'px', position: 'relative' }">
            <div
              v-for="level in visibleAsks"
              :key="level.vIndex"
              class="grid grid-cols-3 px-1 text-xs font-mono absolute w-full"
              :style="{ top: level.vIndex * ROW_HEIGHT + 'px', height: ROW_HEIGHT + 'px', lineHeight: ROW_HEIGHT + 'px' }"
            >
              <div class="absolute inset-0 bg-red-900/20 origin-right" :style="{ width: barPct(level.quantity, maxAskQty) + '%' }"></div>
              <span class="relative text-red-400">{{ fmtPrice(level.price) }}</span>
              <span class="relative text-right text-gray-300">{{ fmtQty(level.quantity) }}</span>
              <span class="relative text-right text-gray-500">{{ fmtQty(level.cumulative) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Bids (buy side) -->
      <div class="flex flex-col">
        <div class="text-xs text-gray-500 grid grid-cols-3 px-1 mb-1 sticky top-0 bg-gray-800">
          <span>Price</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div
          ref="bidContainer"
          class="overflow-y-auto"
          :style="{ height: containerHeight + 'px' }"
          @scroll="onBidScroll"
        >
          <div :style="{ height: bidTotalHeight + 'px', position: 'relative' }">
            <div
              v-for="level in visibleBids"
              :key="level.vIndex"
              class="grid grid-cols-3 px-1 text-xs font-mono absolute w-full"
              :style="{ top: level.vIndex * ROW_HEIGHT + 'px', height: ROW_HEIGHT + 'px', lineHeight: ROW_HEIGHT + 'px' }"
            >
              <div class="absolute inset-0 bg-green-900/20 origin-left" :style="{ width: barPct(level.quantity, maxBidQty) + '%' }"></div>
              <span class="relative text-green-400">{{ fmtPrice(level.price) }}</span>
              <span class="relative text-right text-gray-300">{{ fmtQty(level.quantity) }}</span>
              <span class="relative text-right text-gray-500">{{ fmtQty(level.cumulative) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useOrderBookStore } from '../stores/orderbook'

const ROW_HEIGHT = 22
const VISIBLE_ROWS = 15
const OVERSCAN = 3

const store = useOrderBookStore()
const state = computed(() => store.state)

const containerHeight = VISIBLE_ROWS * ROW_HEIGHT

const askScrollTop = ref(0)
const bidScrollTop = ref(0)

function onAskScroll(e: Event) {
  askScrollTop.value = (e.target as HTMLElement).scrollTop
}
function onBidScroll(e: Event) {
  bidScrollTop.value = (e.target as HTMLElement).scrollTop
}

interface VirtualLevel {
  vIndex: number
  price: number
  quantity: number
  cumulative: number
}

// Asks reversed (lowest ask at bottom of the container)
const asksReversed = computed(() => [...state.value.asks].reverse())
const askTotalHeight = computed(() => asksReversed.value.length * ROW_HEIGHT)
const bidTotalHeight = computed(() => state.value.bids.length * ROW_HEIGHT)

const maxAskQty = computed(() => {
  let max = 0.001
  for (const l of state.value.asks) { if (l.quantity > max) max = l.quantity }
  return max
})
const maxBidQty = computed(() => {
  let max = 0.001
  for (const l of state.value.bids) { if (l.quantity > max) max = l.quantity }
  return max
})

const visibleAsks = computed((): VirtualLevel[] => {
  const items = asksReversed.value
  if (!items.length) return []
  const startIdx = Math.max(0, Math.floor(askScrollTop.value / ROW_HEIGHT) - OVERSCAN)
  const endIdx = Math.min(items.length, startIdx + VISIBLE_ROWS + OVERSCAN * 2)
  const result: VirtualLevel[] = []
  let cum = 0
  // Precompute cumulative from the reversed array start
  for (let i = 0; i < startIdx; i++) cum += items[i].quantity
  for (let i = startIdx; i < endIdx; i++) {
    cum += items[i].quantity
    result.push({ vIndex: i, price: items[i].price, quantity: items[i].quantity, cumulative: cum })
  }
  return result
})

const visibleBids = computed((): VirtualLevel[] => {
  const items = state.value.bids
  if (!items.length) return []
  const startIdx = Math.max(0, Math.floor(bidScrollTop.value / ROW_HEIGHT) - OVERSCAN)
  const endIdx = Math.min(items.length, startIdx + VISIBLE_ROWS + OVERSCAN * 2)
  const result: VirtualLevel[] = []
  let cum = 0
  for (let i = 0; i < startIdx; i++) cum += items[i].quantity
  for (let i = startIdx; i < endIdx; i++) {
    cum += items[i].quantity
    result.push({ vIndex: i, price: items[i].price, quantity: items[i].quantity, cumulative: cum })
  }
  return result
})

function barPct(qty: number, max: number): number {
  return Math.min((qty / max) * 100, 100)
}
function fmtPrice(p: number): string {
  return Number(p).toFixed(2)
}
function fmtQty(q: number): string {
  return Number(q).toFixed(4)
}
</script>
