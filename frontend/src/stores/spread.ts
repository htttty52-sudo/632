import { defineStore } from 'pinia'
import { shallowRef, triggerRef } from 'vue'
import type { SpreadMatrix, SpreadAlertEvent } from '../types/market'

export interface CellState {
  exchange_a: string
  exchange_b: string
  spread_pct: number
  spread_ab: number
  spread_ba: number
  best_spread: number
}

export const useSpreadStore = defineStore('spread', () => {
  // Fixed-length array: only triggers re-render on cells whose values changed
  const cells = shallowRef<CellState[]>([])
  const cellCount = shallowRef(0)
  const exchanges = shallowRef<string[]>([])
  const staleExchanges = shallowRef<string[]>([])
  const lastTimestamp = shallowRef(0)

  // Alert queue: shows each alert popup, max 3 within 5min per type
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

    const newExchanges = incoming.exchanges
    if (exchanges.value.length !== newExchanges.length ||
        exchanges.value.some((e, i) => e !== newExchanges[i])) {
      exchanges.value = newExchanges
    }

    const newStale = incoming.stale_exchanges
    if (staleExchanges.value.length !== newStale.length ||
        staleExchanges.value.some((e, i) => e !== newStale[i])) {
      staleExchanges.value = newStale
    }

    lastTimestamp.value = incoming.timestamp

    // Fixed-length array diff: only mutate slots where value changed
    const prev = cells.value
    const incomingCells = incoming.cells
    let changed = false

    // Resize if needed
    if (prev.length !== incomingCells.length) {
      cells.value = incomingCells.map(c => ({
        exchange_a: c.exchange_a,
        exchange_b: c.exchange_b,
        spread_pct: c.spread_pct,
        spread_ab: c.spread_ab,
        spread_ba: c.spread_ba,
        best_spread: c.best_spread,
      }))
      cellCount.value = incomingCells.length
      triggerRef(cells)
      return
    }

    for (let i = 0; i < incomingCells.length; i++) {
      const n = incomingCells[i]
      const p = prev[i]
      if (p.spread_pct !== n.spread_pct ||
          p.spread_ab !== n.spread_ab ||
          p.spread_ba !== n.spread_ba ||
          p.exchange_a !== n.exchange_a ||
          p.exchange_b !== n.exchange_b) {
        prev[i] = {
          exchange_a: n.exchange_a,
          exchange_b: n.exchange_b,
          spread_pct: n.spread_pct,
          spread_ab: n.spread_ab,
          spread_ba: n.spread_ba,
          best_spread: n.best_spread,
        }
        changed = true
      }
    }

    if (changed) {
      triggerRef(cells)
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
    // Show for 2s, then gap 500ms before next
    alertTimer = window.setTimeout(() => {
      visibleAlert.value = null
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
    const arr = cells.value
    for (let i = 0; i < arr.length; i++) {
      const c = arr[i]
      if ((c.exchange_a === exA && c.exchange_b === exB) ||
          (c.exchange_a === exB && c.exchange_b === exA)) {
        return c
      }
    }
    return undefined
  }

  return {
    cells, cellCount, exchanges, staleExchanges, lastTimestamp,
    visibleAlert, alertHistory,
    handleSpreadMatrix, handleAlert, dismissAlert, getCell,
  }
})
