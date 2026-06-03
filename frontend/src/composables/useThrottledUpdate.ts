import { shallowRef } from 'vue'

/**
 * rAF-batched state update composable.
 * Incoming updates are buffered; only the latest is flushed to a shallowRef
 * once per animation frame. This decouples WS message rate from Vue render rate.
 */
export function useThrottledUpdate<T>(initialValue: T) {
  const displayState = shallowRef<T>(initialValue)
  let pendingUpdate: T | null = null
  let rafId: number | null = null

  function scheduleUpdate(newValue: T) {
    pendingUpdate = newValue
    if (rafId === null) {
      rafId = requestAnimationFrame(flush)
    }
  }

  function flush() {
    if (pendingUpdate !== null) {
      displayState.value = pendingUpdate
      pendingUpdate = null
    }
    rafId = null
  }

  function forceUpdate(newValue: T) {
    pendingUpdate = null
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    displayState.value = newValue
  }

  return { displayState, scheduleUpdate, forceUpdate }
}

/**
 * rAF-batched update that only triggers if data actually changed.
 * Uses a comparator function to avoid unnecessary Vue re-renders.
 */
export function useRafMerge<T>(initialValue: T, hasChanged: (prev: T, next: T) => boolean) {
  const displayState = shallowRef<T>(initialValue)
  let pendingUpdate: T | null = null
  let rafId: number | null = null

  function scheduleUpdate(newValue: T) {
    pendingUpdate = newValue
    if (rafId === null) {
      rafId = requestAnimationFrame(flush)
    }
  }

  function flush() {
    if (pendingUpdate !== null && hasChanged(displayState.value, pendingUpdate)) {
      displayState.value = pendingUpdate
    }
    pendingUpdate = null
    rafId = null
  }

  return { displayState, scheduleUpdate }
}
