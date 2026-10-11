<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import type { ApiSchemas } from '../../types/generated/api'
import { chatSelection, selectionPosition } from '../../lib/chat/selection'
import type { SelectionSnapshot } from '../../lib/chat/selection'

const props = defineProps<{ scroller: HTMLElement | null, conversationId: string | null }>()
const emit = defineEmits<{ reference: [value: ApiSchemas['TextReference']] }>()
const action = ref<HTMLElement | null>(null)
const button = ref<HTMLButtonElement | null>(null)
const selected = shallowRef<SelectionSnapshot | null>(null)
const position = ref({ left: 0, top: 0 })
const editable = 'input, textarea, select, [contenteditable]:not([contenteditable="false"])'
let pointerDown = false
let keyboardSelecting = false
let timer: ReturnType<typeof setTimeout> | undefined
let dismissed = false
let observer: ResizeObserver | undefined
function close(): void {
  clearTimeout(timer)
  selected.value = null
}
function modalOpen(): boolean { return Boolean(document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"][data-state="open"]')) }
function place(): void {
  if (!selected.value || !props.scroller || !action.value) return
  if (modalOpen() || !selected.value.range.startContainer.isConnected) { close(); return }
  const visual = window.visualViewport
  const viewport = { left: visual?.offsetLeft ?? 0, top: visual?.offsetTop ?? 0, right: (visual?.offsetLeft ?? 0) + (visual?.width ?? window.innerWidth), bottom: (visual?.offsetTop ?? 0) + (visual?.height ?? window.innerHeight) }
  action.value.style.maxWidth = `${Math.max(0, viewport.right - viewport.left - 16)}px`
  const bounds = action.value.getBoundingClientRect()
  const range = selected.value.range
  const rects = [...range.getClientRects()]
  const result = selectionPosition(rects.length ? rects : [range.getBoundingClientRect()], viewport, props.scroller.getBoundingClientRect(), bounds.width, bounds.height)
  if (result) position.value = result
  else close()
}
async function update(): Promise<void> {
  if (pointerDown || keyboardSelecting || dismissed) return
  if (modalOpen() || !props.scroller || !props.conversationId) { close(); return }
  // Tabbing to the action must not discard the cached range.
  if (action.value?.contains(document.activeElement)) return
  selected.value = chatSelection(window.getSelection(), props.scroller, props.conversationId)
  await nextTick()
  if (!selected.value || !action.value) return
  action.value.showPopover?.()
  place()
}
function changed(): void {
  clearTimeout(timer)
  // Native touch handles can adjust the selection without pointer events.
  // Wait for a stable range; pointer/keyboard release updates immediately.
  timer = setTimeout(() => { void update() }, 160)
}
function start(event: PointerEvent): void {
  if (action.value?.contains(event.target as Node)) return
  const target = event.target instanceof Element ? event.target : null
  dismissed = !target?.closest('[data-selectable-message]') || !props.scroller?.contains(target) || Boolean(target.closest('button, input, textarea, [contenteditable]'))
  pointerDown = true
  close()
}
function end(): void { pointerDown = false; void update() }
function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && selected.value) {
    event.preventDefault(); event.stopImmediatePropagation()
    const focused = action.value?.contains(document.activeElement)
    dismissed = true; close()
    if (focused) props.scroller?.focus({ preventScroll: true })
  }
  else if (event.key === 'Tab' && !event.shiftKey && selected.value && !modalOpen() && !action.value?.contains(document.activeElement) && (document.activeElement === document.body || props.scroller?.contains(document.activeElement))) {
    event.preventDefault(); button.value?.focus({ preventScroll: true })
  }
  else if (event.shiftKey && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
    if (event.target instanceof Element && event.target.closest(editable)) { dismissed = true; close(); return }
    dismissed = false; keyboardSelecting = true; close()
  }
}
function keyup(event: KeyboardEvent): void {
  if (keyboardSelecting && (event.key === 'Shift' || !event.shiftKey)) { keyboardSelecting = false; void update() }
}
function focusChanged(): void { if (modalOpen() || document.activeElement?.closest(editable)) { dismissed = true; close() } }
function activate(): void {
  if (!selected.value) return
  const value = selected.value.reference
  dismissed = true; close()
  emit('reference', value)
}
watch(() => props.conversationId, () => { dismissed = false; close() })
watch(() => props.scroller, (current, previous) => { if (previous) observer?.unobserve(previous); if (current) observer?.observe(current) })
onMounted(() => {
  document.addEventListener('selectionchange', changed)
  document.addEventListener('pointerdown', start, true)
  document.addEventListener('pointerup', end, true)
  document.addEventListener('pointercancel', end, true)
  document.addEventListener('keydown', keydown, true)
  document.addEventListener('keyup', keyup, true)
  document.addEventListener('focusin', focusChanged)
  window.addEventListener('scroll', place, true)
  window.addEventListener('resize', place)
  window.visualViewport?.addEventListener('resize', place)
  window.visualViewport?.addEventListener('scroll', place)
  observer = new ResizeObserver(place)
  if (props.scroller) observer.observe(props.scroller)
})
onUnmounted(() => {
  close(); observer?.disconnect()
  document.removeEventListener('selectionchange', changed)
  document.removeEventListener('pointerdown', start, true)
  document.removeEventListener('pointerup', end, true)
  document.removeEventListener('pointercancel', end, true)
  document.removeEventListener('keydown', keydown, true)
  document.removeEventListener('keyup', keyup, true)
  document.removeEventListener('focusin', focusChanged)
  window.removeEventListener('scroll', place, true)
  window.removeEventListener('resize', place)
  window.visualViewport?.removeEventListener('resize', place)
  window.visualViewport?.removeEventListener('scroll', place)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="selected" ref="action" popover="manual" class="text-selection-action" :style="{ left: `${position.left}px`, top: `${position.top}px` }">
      <button ref="button" type="button" aria-label="noris AI fragen" aria-describedby="text-selection-hint" @pointerdown.prevent @click="activate">
        <UIcon name="i-lucide-message-circle" class="size-4" aria-hidden="true" />
        noris AI fragen
      </button>
      <span id="text-selection-hint" class="sr-only">Markierten Text als Referenz in die Nachricht übernehmen</span>
    </div>
  </Teleport>
</template>
