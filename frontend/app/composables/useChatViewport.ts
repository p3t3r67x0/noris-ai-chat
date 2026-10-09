import { onMounted, onUnmounted, ref } from 'vue'

export function useChatViewport() {
  const viewportStyle = ref<Record<string, string>>({})
  function update(): void {
    const viewport = window.visualViewport
    // Pinch zoom should keep its natural pan behavior; keyboard resizing should not.
    if (!viewport || viewport.scale !== 1) { viewportStyle.value = {}; return }
    viewportStyle.value = { '--chat-viewport-height': `${viewport.height}px`, '--chat-viewport-offset': `${viewport.offsetTop}px` }
  }
  onMounted(() => {
    update()
    window.visualViewport?.addEventListener('resize', update)
    window.visualViewport?.addEventListener('scroll', update)
    window.addEventListener('resize', update)
  })
  onUnmounted(() => {
    if (typeof window === 'undefined') return
    window.visualViewport?.removeEventListener('resize', update)
    window.visualViewport?.removeEventListener('scroll', update)
    window.removeEventListener('resize', update)
  })
  return { viewportStyle }
}
