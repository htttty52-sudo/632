<template>
  <div class="bg-gray-800 rounded-lg p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-400">Cross-Exchange Spread Matrix</h3>
      <div v-if="staleExchanges.length" class="flex items-center gap-1">
        <span class="w-2 h-2 rounded-full bg-yellow-500 animate-pulse"></span>
        <span class="text-xs text-yellow-400">{{ staleExchanges.map(formatExchange).join(', ') }} 延迟</span>
      </div>
    </div>

    <div v-if="allExchanges.length < 2" class="text-center text-gray-500 text-sm py-4">
      Waiting for data from multiple exchanges...
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-xs font-mono">
        <thead>
          <tr>
            <th class="p-2 text-gray-500 text-left">Buy \ Sell</th>
            <th v-for="ex in allExchanges" :key="ex" class="p-2 text-gray-400 text-center capitalize">
              {{ formatExchange(ex) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(exRow, i) in allExchanges" :key="exRow">
            <td class="p-2 text-gray-400 capitalize">{{ formatExchange(exRow) }}</td>
            <td
              v-for="(exCol, j) in allExchanges"
              :key="exCol"
              class="p-2 text-center rounded"
              :style="{ backgroundColor: getCellBg(exRow, exCol, i, j) }"
            >
              <span v-if="i === j" class="text-gray-600">—</span>
              <span v-else-if="isDelayed(exRow, exCol)" class="text-yellow-400 text-xs">
                延迟
              </span>
              <span v-else class="text-white font-medium">
                {{ getCellText(exRow, exCol) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 flex items-center justify-between text-xs text-gray-500">
      <div class="flex items-center gap-2">
        <span class="inline-block w-3 h-3 rounded" style="background: rgba(34, 197, 94, 0.4)"></span>
        <span>&le;0%</span>
        <span class="inline-block w-3 h-3 rounded" style="background: rgba(234, 179, 8, 0.4)"></span>
        <span>0.05%</span>
        <span class="inline-block w-3 h-3 rounded" style="background: rgba(239, 68, 68, 0.5)"></span>
        <span>&ge;0.1%</span>
        <span class="inline-block w-3 h-3 rounded bg-yellow-900/50 border border-yellow-700"></span>
        <span>延迟</span>
      </div>
      <span v-if="store.lastTimestamp">Updated: {{ formatTime(store.lastTimestamp) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSpreadStore } from '../stores/spread'

const store = useSpreadStore()

const staleExchanges = computed(() => store.staleExchanges)

// Show all known exchanges including stale ones in the matrix grid
const allExchanges = computed(() => {
  const active = store.exchanges
  const stale = store.staleExchanges.filter(s => !active.includes(s))
  return [...active, ...stale].sort()
})

function isDelayed(exRow: string, exCol: string): boolean {
  const stale = store.staleExchanges
  return stale.includes(exRow) || stale.includes(exCol)
}

function formatExchange(name: string): string {
  return name.replace(/^mock_/, '')
}

function getCellText(exRow: string, exCol: string): string {
  const cell = store.getCell(exRow, exCol)
  if (!cell) return '—'
  return `${cell.spread_pct.toFixed(4)}%`
}

function getCellBg(exRow: string, exCol: string, i: number, j: number): string {
  if (i === j) return 'transparent'
  if (isDelayed(exRow, exCol)) return 'rgba(120, 80, 0, 0.2)'
  const cell = store.getCell(exRow, exCol)
  if (!cell) return 'transparent'
  return spreadToColor(cell.spread_pct)
}

function spreadToColor(pct: number): string {
  if (pct <= 0) return 'rgba(34, 197, 94, 0.3)'
  if (pct >= 0.1) return 'rgba(239, 68, 68, 0.5)'
  const ratio = pct / 0.1
  const r = Math.round(34 + (239 - 34) * ratio)
  const g = Math.round(197 - (197 - 68) * ratio)
  return `rgba(${r}, ${g}, 68, 0.4)`
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString()
}
</script>
