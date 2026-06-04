import { defineStore } from 'pinia'
import { shallowRef } from 'vue'
import type { SpreadMatrix, SpreadAlertEvent } from '../types/market'

export const useSpreadStore = defineStore('spread', () => {
  const matrix = shallowRef<SpreadMatrix | null>(null)
  const alerts = shallowRef<SpreadAlertEvent[]>([])
  let rafId: number | null = null
  let pendingMatrix: SpreadMatrix | null = null

  function handleSpreadMatrix(data: SpreadMatrix) {
    pendingMatrix = data
    if (rafId === null) {
      rafId = requestAnimationFrame(flush)
    }
  }

  function flush() {
    rafId = null
    if (pendingMatrix) {
      matrix.value = pendingMatrix
      pendingMatrix = null
    }
  }

  function handleAlert(data: SpreadAlertEvent) {
    alerts.value = [data, ...alerts.value].slice(0, 50)
  }

  function dismissAlert(index: number) {
    const next = [...alerts.value]
    next.splice(index, 1)
    alerts.value = next
  }

  return { matrix, alerts, handleSpreadMatrix, handleAlert, dismissAlert }
})
