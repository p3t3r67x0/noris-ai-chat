import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'

// Keep Nuxt UI's textarea and IME handling; measure fractional line heights in
// pixels instead of rounding wrapped text to integer textarea rows.
export function useComposerAutosize(prompt: Ref<{ textareaRef: HTMLTextAreaElement | undefined } | null>, text: Ref<string>, hasAttachments: Ref<boolean> = ref(false)) {
  const expanded = ref(false)
  const maximized = ref(false)
  let observer: ResizeObserver | undefined
  let lastWidth = -1
  let mirror: HTMLTextAreaElement | undefined
  function fit(): void {
    const input = prompt.value?.textareaRef
    if (!input) return
    const style = getComputedStyle(input)
    const minimum = Number.parseFloat(style.lineHeight) + Number.parseFloat(style.paddingTop) + Number.parseFloat(style.paddingBottom)
    const top = input.scrollTop
    input.style.height = '0px'
    input.style.height = `${Math.max(minimum, input.scrollHeight)}px`
    input.scrollTop = top
    maximized.value = input.scrollHeight > input.clientHeight + 1
  }
  function resize(): void {
    const input = prompt.value?.textareaRef
    const root = input?.closest<HTMLElement>('.chat-composer')
    if (!input || !root || !mirror) return
    const style = getComputedStyle(input)
    const layout = getComputedStyle(root)
    const controls = [...root.querySelectorAll<HTMLElement>('.composer-attachment, .composer-model, .composer-submit')]
    // Measure at the hypothetical compact width even while expanded. Measuring
    // only the expanded textarea would repeatedly toggle long wrapped sentences.
    const compactWidth = root.clientWidth - Number.parseFloat(layout.paddingLeft) - Number.parseFloat(layout.paddingRight)
      - controls.reduce((width, control) => width + Number.parseFloat(getComputedStyle(control).width), 0)
      - Number.parseFloat(layout.columnGap) * controls.length
    for (const property of ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing', 'wordSpacing', 'textTransform'] as const) mirror.style[property] = style[property]
    mirror.style.width = `${Math.max(1, compactWidth - (expanded.value ? 8 : 0))}px`
    mirror.value = input.value
    const wrapped = mirror.scrollHeight > Math.ceil(Number.parseFloat(style.lineHeight)) + 1
    const next = hasAttachments.value || wrapped
    if (expanded.value !== next) {
      expanded.value = next
      void nextTick(fit)
    }
    else fit()
  }
  watch([text, hasAttachments], resize, { flush: 'post' })
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
      const width = entries[0]?.contentRect.width ?? 0
      if (width !== lastWidth) { lastWidth = width; resize() }
    })
    const root = input?.closest('.chat-composer')
    if (root) observer.observe(root)
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
  return { resize, expanded, maximized }
}
