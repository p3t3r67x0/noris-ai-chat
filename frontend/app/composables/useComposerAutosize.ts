import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'

// Keep Nuxt UI's textarea and IME handling; measure fractional line heights in
// pixels instead of rounding wrapped text to integer textarea rows.
export function useComposerAutosize(prompt: Ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>, text: Ref<string>, hasHeader: Ref<boolean> = ref(false)) {
  const expanded = ref(false)
  const stacked = ref(false)
  const maximized = ref(false)
  let observer: ResizeObserver | undefined
  const widths = new WeakMap<Element, number>()
  let mirror: HTMLTextAreaElement | undefined
  function measuredHeight(style: CSSStyleDeclaration, width: number, value: string): number {
    if (!mirror) return 0
    for (const property of ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing', 'wordSpacing', 'textTransform', 'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight', 'tabSize'] as const) mirror.style[property] = style[property]
    mirror.style.width = `${Math.max(1, width)}px`
    mirror.value = value
    return mirror.scrollHeight
  }
  function fit(): void {
    const input = prompt.value?.textareaRef
    if (!input || !mirror) return
    const style = getComputedStyle(input)
    const minimum = Number.parseFloat(style.lineHeight) + Number.parseFloat(style.paddingTop) + Number.parseFloat(style.paddingBottom)
    const top = input.scrollTop
    // Never collapse the live textarea for measurement. That briefly enlarges
    // the timeline, clamps its scroll offset, and looks like manual scrolling.
    const height = measuredHeight(style, Number.parseFloat(style.width) || input.clientWidth, input.value)
    input.style.height = `${Math.max(minimum, height)}px`
    input.scrollTop = top
    maximized.value = input.scrollHeight > input.clientHeight + 1
  }
  function resize(): void {
    const input = prompt.value?.textareaRef
    const root = input?.closest<HTMLElement>('.chat-composer')
    if (!input || !root || !mirror) return
    const style = getComputedStyle(input)
    const layout = getComputedStyle(root)
    const controls = [...root.querySelectorAll<HTMLElement>('.composer-attachment, .composer-model-controls, .composer-microphone, .composer-submit')]
    // The same textarea stays mounted. On narrow composers the controls always
    // occupy the bottom row, so adding/removing the inline search chip cannot
    // push the model selector over the input or move the actions down a row.
    const narrow = root.clientWidth < 560
    const changed = stacked.value !== narrow
    stacked.value = narrow
    const padding = Number.parseFloat(layout.paddingLeft) + Number.parseFloat(layout.paddingRight)
    const prefix = root.querySelector<HTMLElement>('.composer-web-search')
    const prefixWidth = prefix ? Number.parseFloat(getComputedStyle(prefix).width) + 8 : 0
    // Measure the hypothetical single-line layout even while expanded to avoid
    // alternating between two widths when a sentence wraps.
    const compactWidth = root.clientWidth - padding - prefixWidth - (narrow ? 16
      : controls.reduce((width, control) => width + Number.parseFloat(getComputedStyle(control).width), 0)
        + Number.parseFloat(layout.columnGap) * controls.length)
    const wrapped = measuredHeight(style, compactWidth, input.value) > Math.ceil(Number.parseFloat(style.lineHeight)) + 1
    const next = hasHeader.value || wrapped
    if (expanded.value !== next || changed) {
      expanded.value = next
      void nextTick(fit)
    }
    else fit()
  }
  watch([text, hasHeader], resize, { flush: 'post' })
  onMounted(async () => {
    await nextTick()
    const input = prompt.value?.textareaRef
    if (input) {
      mirror = document.createElement('textarea')
      mirror.className = 'composer-measure'
      mirror.setAttribute('aria-hidden', 'true')
      mirror.tabIndex = -1
      mirror.rows = 1
      document.body.append(mirror)
    }
    resize()
    observer = new ResizeObserver(entries => {
      let changed = false
      for (const entry of entries) {
        const width = entry.contentRect.width
        if (widths.get(entry.target) !== width) { widths.set(entry.target, width); changed = true }
      }
      if (changed) resize()
    })
    const root = input?.closest('.chat-composer')
    if (root) observer.observe(root)
    const controls = root?.querySelector('.composer-model-controls')
    if (controls) observer.observe(controls)
    window.addEventListener('resize', resize)
    window.visualViewport?.addEventListener('resize', resize)
    void document.fonts?.ready.then(resize)
  })
  onUnmounted(() => {
    observer?.disconnect()
    mirror?.remove()
    window.removeEventListener('resize', resize)
    window.visualViewport?.removeEventListener('resize', resize)
  })
  return { resize, expanded, stacked, maximized }
}
