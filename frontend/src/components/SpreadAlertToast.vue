<template>
  <Teleport to="body">
    <Transition name="toast">
      <div
        v-if="store.visibleAlert"
        class="fixed top-4 right-4 z-50 max-w-sm bg-red-900/90 border border-red-500 rounded-lg p-3 shadow-lg backdrop-blur-sm"
      >
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="flex items-center gap-1 mb-1">
              <span class="w-2 h-2 rounded-full bg-red-400 animate-pulse"></span>
              <span class="text-xs font-semibold text-red-300">SPREAD ALERT</span>
              <span v-if="store.alertHistory.length > 1" class="text-xs text-gray-400 ml-2">
                ({{ store.alertHistory.length }} total)
              </span>
            </div>
            <p class="text-sm text-white">
              <span class="capitalize">{{ formatExchange(store.visibleAlert.exchange_a) }}</span>
              ⇄
              <span class="capitalize">{{ formatExchange(store.visibleAlert.exchange_b) }}</span>
            </p>
            <p class="text-lg font-mono font-bold text-red-300">
              {{ store.visibleAlert.spread_pct.toFixed(4) }}%
            </p>
            <p class="text-xs text-gray-400 mt-1">
              {{ formatTime(store.visibleAlert.timestamp) }} ·
              {{ store.visibleAlert.direction === 'a_to_b' ? 'Buy→Sell' : 'Sell←Buy' }}
            </p>
          </div>
          <button
            class="text-gray-400 hover:text-white text-lg leading-none"
            @click="store.dismissAlert()"
          >×</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { useSpreadStore } from '../stores/spread'

const store = useSpreadStore()

function formatExchange(name: string): string {
  return name.replace(/^mock_/, '')
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString()
}
</script>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.3s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
