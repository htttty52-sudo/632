<template>
  <div class="flex items-center gap-2 text-sm">
    <span class="relative flex h-2.5 w-2.5">
      <span
        v-if="status === 'open'"
        class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"
      ></span>
      <span
        class="relative inline-flex rounded-full h-2.5 w-2.5"
        :class="{
          'bg-green-400': status === 'open',
          'bg-yellow-400': status === 'connecting',
          'bg-red-400': status === 'closed',
        }"
      ></span>
    </span>
    <span class="text-gray-400">
      {{ statusText }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WSStatus } from '../composables/useWebSocket'

const props = defineProps<{ status: WSStatus }>()

const statusText = computed(() => {
  switch (props.status) {
    case 'open': return 'Connected'
    case 'connecting': return 'Connecting...'
    case 'closed': return 'Disconnected'
  }
})
</script>
