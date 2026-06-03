import { shallowRef } from 'vue'

export function useThrottledUpdate<T>(initialValue: T) {
  const displayState = shallowRef<T>(initialValue)
  let pendingUpdate: T | null = null
  let rafId: number | null = null

  function scheduleUpdate(newValue: T) {
    pendingUpdate = newValue
    if (rafId === null) {
      rafId = requestAnimationFrame(() => {
        if (pendingUpdate !== null) {
          displayState.value = Object.freeze(pendingUpdate) as T
          pendingUpdate = null
        }
        rafId = null
      })
    }
  }

  function forceUpdate(newValue: T) {
    pendingUpdate = null
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    displayState.value = Object.freeze(newValue) as T
  }

  return { displayState, scheduleUpdate, forceUpdate }
}
