import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { distanceToBottom, followingAfterScroll } from '../lib/chat/scroll'

export function useChatScroll(scroller: Ref<HTMLElement | null>, content: Ref<HTMLElement | null>, conversationId: Ref<string | null>, turnId: Ref<string | null>) {
  const following = ref(true)
  const distance = ref(0)
  const showScrollButton = computed(() => !following.value || distance.value > 64)
  const positions = new Map<string, { top: number, following: boolean }>()
  let lastTop = 0
  let frame: number | undefined
  let observer: ResizeObserver | undefined
  let changing = false
  let revision = 0
  let touchY = 0

  function measure(): void {
    const element = scroller.value
    if (!element) return
    distance.value = distanceToBottom({ top: element.scrollTop, height: element.scrollHeight, viewport: element.clientHeight })
    const timeline = content.value
    const style = timeline ? getComputedStyle(timeline) : undefined
    const padding = style ? (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.paddingBottom) || 0) : 0
    const height = `${Math.max(0, element.clientHeight - padding)}px`
    if (content.value?.style.getPropertyValue('--last-turn-height') !== height) content.value?.style.setProperty('--last-turn-height', height)
  }
  function cancelFrame(): void {
    if (frame !== undefined) cancelAnimationFrame(frame)
    frame = undefined
  }
  function setTop(top: number): void {
    const element = scroller.value
    if (!element) return
    lastTop = Math.max(0, Math.min(top, element.scrollHeight - element.clientHeight))
    element.scrollTop = lastTop
    measure()
  }
  function follow(): void {
    if (!following.value || changing || frame !== undefined) return
    frame = requestAnimationFrame(() => {
      frame = undefined
      if (following.value && !changing) setTop(scroller.value?.scrollHeight ?? 0)
    })
  }
  function scrollToBottom(): void {
    following.value = true
    cancelFrame()
    setTop(scroller.value?.scrollHeight ?? 0)
  }
  function onScroll(): void {
    const element = scroller.value
    if (!element || changing) return
    measure()
    following.value = followingAfterScroll(following.value, lastTop, element.scrollTop, distance.value, element.scrollHeight - element.clientHeight)
    lastTop = element.scrollTop
    if (!following.value) cancelFrame()
  }
  function pause(): void { following.value = false; cancelFrame() }
  function onWheel(event: WheelEvent): void { if (event.deltaY < 0) pause() }
  function onKeydown(event: KeyboardEvent): void {
    if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) pause()
  }
  function onTouchstart(event: TouchEvent): void { touchY = event.touches[0]?.clientY ?? 0 }
  function onTouchmove(event: TouchEvent): void {
    const nextY = event.touches[0]?.clientY ?? touchY
    if (nextY > touchY + 2) pause()
    touchY = nextY
  }
  function contentChanged(): void { measure(); follow() }
  function contentRendered(): void {
    measure()
    if (following.value && !changing) {
      cancelFrame()
      setTop(scroller.value?.scrollHeight ?? 0)
    }
  }
  const stopWatching = watch([conversationId, turnId], async ([id, turn], [previousId, previousTurn]) => {
    if (typeof window === 'undefined') return
    cancelFrame()
    const currentRevision = ++revision
    changing = true
    if (previousId && id !== previousId) positions.set(previousId, { top: scroller.value?.scrollTop ?? 0, following: following.value })
    await nextTick()
    if (currentRevision !== revision) return
    measure()
    const saved = id !== previousId && id ? positions.get(id) : undefined
    if (saved) { following.value = saved.following; setTop(saved.following ? scroller.value?.scrollHeight ?? 0 : saved.top) }
    else if (id !== previousId || turn !== previousTurn) { following.value = true; setTop(scroller.value?.scrollHeight ?? 0) }
    changing = false
    follow()
  }, { flush: 'pre' })

  onMounted(() => {
    observer = new ResizeObserver(() => { measure(); follow() })
    if (scroller.value) observer.observe(scroller.value)
    if (content.value) observer.observe(content.value)
    measure(); follow()
  })
  onUnmounted(() => { ++revision; stopWatching(); observer?.disconnect(); cancelFrame() })
  return { following, showScrollButton, scrollToBottom, contentChanged, contentRendered, onScroll, onWheel, onKeydown, onTouchstart, onTouchmove }
}
