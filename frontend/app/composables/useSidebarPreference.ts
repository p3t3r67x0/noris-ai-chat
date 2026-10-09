import { onMounted, onUnmounted, ref, watch } from 'vue'

export const SIDEBAR_STORAGE_KEY = 'noris-ai:sidebar-open'

// USidebar owns its mobile drawer state. Only explicit desktop changes are persisted.
export function useSidebarPreference() {
  const sidebarOpen = ref(true)
  let stopWatching: (() => void) | undefined
  onMounted(() => {
    try {
      const saved = window.localStorage.getItem(SIDEBAR_STORAGE_KEY)
      if (window.matchMedia('(min-width: 1024px)').matches && saved !== null) sidebarOpen.value = saved !== 'false'
    }
    catch { /* Navigation remains usable without storage. */ }
    stopWatching = watch(sidebarOpen, (open) => {
      if (!window.matchMedia('(min-width: 1024px)').matches) return
      try { window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(open)) }
      catch { /* A preference must not prevent navigation. */ }
    })
  })
  onUnmounted(() => stopWatching?.())
  return { sidebarOpen }
}
