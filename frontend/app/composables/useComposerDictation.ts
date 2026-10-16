import { onMounted, onUnmounted, ref } from 'vue'
import type { Ref } from 'vue'

// Web Speech is optional and is not included in TypeScript's DOM interfaces.
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: { results: ArrayLike<{ isFinal: boolean, 0: { transcript: string } }> }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition, webkitSpeechRecognition?: new () => Recognition }

export function useComposerDictation(text: Ref<string>, language: Ref<string>, focus: () => void) {
  const supported = ref(false)
  const listening = ref(false)
  const error = ref(false)
  let recognition: Recognition | undefined

  function stop(): void {
    const current = recognition
    recognition = undefined
    listening.value = false
    // Discard late results after sending or switching away from this composer.
    if (current) {
      current.onresult = current.onerror = current.onend = null
      current.abort()
    }
  }
  function toggle(): void {
    if (listening.value) { stop(); focus(); return }
    const browser = window as SpeechWindow
    const Constructor = browser.SpeechRecognition ?? browser.webkitSpeechRecognition
    if (!Constructor) return
    error.value = false
    const current = new Constructor()
    recognition = current
    current.lang = language.value === 'en' ? 'en-US' : 'de-DE'
    current.continuous = true
    current.interimResults = false
    let consumed = 0
    current.onresult = event => {
      if (recognition !== current) return
      for (; consumed < event.results.length; consumed++) {
        const result = event.results[consumed]
        if (result?.isFinal) text.value += `${text.value && !/\s$/.test(text.value) ? ' ' : ''}${result[0].transcript}`
      }
    }
    current.onerror = () => { if (recognition !== current) return; error.value = true; stop(); focus() }
    current.onend = () => { if (recognition !== current) return; recognition = undefined; listening.value = false; focus() }
    try { current.start(); listening.value = true; focus() }
    catch { error.value = true; stop() }
  }
  onMounted(() => {
    const browser = window as SpeechWindow
    supported.value = Boolean(browser.SpeechRecognition ?? browser.webkitSpeechRecognition)
  })
  onUnmounted(stop)
  return { supported, listening, error, toggle, stop }
}
