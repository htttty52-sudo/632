import { defineStore } from 'pinia'
import { shallowRef, triggerRef } from 'vue'
import type { SpreadMatrix, SpreadAlertEvent } from '../types/market'

export interface CellState {
  spread_pct: number
  spread_ab: number
  spread_ba: number
  best_spread: number
}

export const useSpreadStore = defineStore('spread', () => {
  // Per-cell Map: key = "exA:exB", only triggers when a cell's value actually changes
  const cellMap = shallowRef<Map<string, CellState>>(new Map())
  const exchanges = shallowRef<string[]>([])
  const staleExchanges = shallowRef<string[]>([])
  const lastTimestamp = shallowRef(0)

  // Alert queue: throttled to show at most 1 every 2 seconds
  const visibleAlert = shallowRef<SpreadAlertEvent | null>(null)
  const alertHistory = shallowRef<SpreadAlertEvent[]>([])
  let alertQueue: SpreadAlertEvent[] = []
  let alertTimer: number | null = null

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
    if (!pendingMatrix) return
    const incoming = pendingMatrix
    pendingMatrix = null

    // Update exchanges list only if changed
    const newExchanges = incoming.exchanges
    if (JSON.stringify(exchanges.value) !== JSON.stringify(newExchanges)) {
      exchanges.value = newExchanges
    }

    // Update stale list only if changed
    const newStale = incoming.stale_exchanges
    if (JSON.stringify(staleExchanges.value) !== JSON.stringify(newStale)) {
      staleExchanges.value = newStale
    }

    lastTimestamp.value = incoming.timestamp

    // Diff cells: only update Map entries that actually changed
    const prev = cellMap.value
    let changed = false
    const seen = new Set<string>()

    for (const cell of incoming.cells) {
      const key = `${cell.exchange_a}:${cell.exchange_b}`
      seen.add(key)
      const existing = prev.get(key)
      if (!existing ||
          existing.spread_pct !== cell.spread_pct ||
          existing.spread_ab !== cell.spread_ab ||
          existing.spread_ba !== cell.spread_ba) {
        prev.set(key, {
          spread_pct: cell.spread_pct,
          spread_ab: cell.spread_ab,
          spread_ba: cell.spread_ba,
          best_spread: cell.best_spread,
        })
        changed = true
      }
    }

    // Remove cells no longer present
    for (const key of prev.keys()) {
      if (!seen.has(key)) {
        prev.delete(key)
        changed = true
      }
    }

    if (changed) {
      triggerRef(cellMap)
    }
  }

  function handleAlert(data: SpreadAlertEvent) {
    alertHistory.value = [data, ...alertHistory.value].slice(0, 50)
    alertQueue.push(data)
    drainAlertQueue()
  }

  function drainAlertQueue() {
    if (alertTimer !== null) return
    showNextAlert()
  }

  function showNextAlert() {
    const next = alertQueue.shift()
    if (!next) {
      alertTimer = null
      return
    }
    visibleAlert.value = next
    alertTimer = window.setTimeout(() => {
      visibleAlert.value = null
      // Wait 2 seconds before showing next
      alertTimer = window.setTimeout(() => {
        alertTimer = null
        if (alertQueue.length > 0) {
          showNextAlert()
        }
      }, 500)
    }, 2000)
  }

  function dismissAlert() {
    visibleAlert.value = null
    if (alertTimer !== null) {
      clearTimeout(alertTimer)
      alertTimer = window.setTimeout(() => {
        alertTimer = null
        if (alertQueue.length > 0) {
          showNextAlert()
        }
      }, 500)
    }
  }

  function getCell(exA: string, exB: string): CellState | undefined {
    return cellMap.value.get(`${exA}:${exB}`) || cellMap.value.get(`${exB}:${exA}`)
  }

  return {
    cellMap, exchanges, staleExchanges, lastTimestamp,
    visibleAlert, alertHistory,
    handleSpreadMatrix, handleAlert, dismissAlert, getCell,
  }
})
