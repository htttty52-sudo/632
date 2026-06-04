<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      <TransitionGroup name="toast">
        <div
          v-for="(alert, index) in visibleAlerts"
          :key="alert.timestamp + alert.exchange_a + alert.exchange_b"
          class="bg-red-900/90 border border-red-500 rounded-lg p-3 shadow-lg backdrop-blur-sm"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="flex items-center gap-1 mb-1">
                <span class="w-2 h-2 rounded-full bg-red-400 animate-pulse"></span>
                <span class="text-xs font-semibold text-red-300">SPREAD ALERT</span>
              </div>
              <p class="text-sm text-white">
                <span class="capitalize">{{ formatExchange(alert.exchange_a) }}</span>
                ⇄
                <span class="capitalize">{{ formatExchange(alert.exchange_b) }}</span>
              </p>
              <p class="text-lg font-mono font-bold text-red-300">
                {{ alert.spread_pct.toFixed(4) }}%
              </p>
              <p class="text-xs text-gray-400 mt-1">
                {{ formatTime(alert.timestamp) }} · {{ alert.direction === 'a_to_b' ? 'Buy→Sell' : 'Sell←Buy' }}
              </p>
            </div>
            <button
              class="text-gray-400 hover:text-white text-lg leading-none"
              @click="dismiss(index)"
            >×</button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useSpreadStore } from '../stores/spread'

const store = useSpreadStore()

const visibleAlerts = computed(() => store.alerts.slice(0, 5))

watch(() => store.alerts.length, () => {
  if (store.alerts.length > 0) {
    setTimeout(() => {
      if (store.alerts.length > 0) {
        store.dismissAlert(store.alerts.length - 1)
      }
    }, 10000)
  }
})

function dismiss(index: number) {
  store.dismissAlert(index)
}

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
