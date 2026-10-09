import { onUnmounted, ref } from 'vue'

export function useCopy() {
  const copied = ref(false)
  const copyError = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | undefined
  async function copy(text: string): Promise<void> {
    copyError.value = null
    try {
      if (typeof navigator === 'undefined' || !navigator.clipboard) throw new Error('Zwischenablage nicht verfügbar')
      await navigator.clipboard.writeText(text)
      copied.value = true
      clearTimeout(timer)
      timer = setTimeout(() => { copied.value = false }, 1800)
    }
    catch { copied.value = false; copyError.value = 'Kopieren nicht möglich. Bitte wähle den Text aus.' }
  }
  onUnmounted(() => clearTimeout(timer))
  return { copied, copyError, copy }
}
