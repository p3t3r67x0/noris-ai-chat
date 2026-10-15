import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { useComposerDictation } from '../../app/composables/useComposerDictation'

class Recognition {
  static latest: Recognition
  lang = ''
  continuous = false
  interimResults = false
  onresult: ((event: { results: { isFinal: boolean, 0: { transcript: string } }[] }) => void) | null = null
  onerror: (() => void) | null = null
  onend: (() => void) | null = null
  start = vi.fn()
  abort = vi.fn()
  stop = vi.fn()
  constructor() { Recognition.latest = this }
}
function setup() {
  const text = ref('Mein Entwurf')
  const focus = vi.fn()
  let dictation!: ReturnType<typeof useComposerDictation>
  const wrapper = mount(defineComponent({ setup() { dictation = useComposerDictation(text, ref('de'), focus); return () => h('div') } }))
  return { wrapper, dictation, text, focus }
}
afterEach(() => vi.unstubAllGlobals())

describe('composer dictation', () => {
  it('detects unsupported browsers without changing the draft', () => {
    const { wrapper, dictation, text } = setup()
    expect(dictation.supported.value).toBe(false)
    dictation.toggle()
    expect(text.value).toBe('Mein Entwurf')
    wrapper.unmount()
  })
  it('appends final transcripts once and discards late results after stopping', () => {
    vi.stubGlobal('SpeechRecognition', Recognition)
    const { wrapper, dictation, text, focus } = setup()
    expect(dictation.supported.value).toBe(true)
    dictation.toggle()
    const recognition = Recognition.latest
    expect(recognition.lang).toBe('de-DE')
    expect(dictation.listening.value).toBe(true)
    const result = { results: [{ isFinal: true, 0: { transcript: 'mit Sprache' } }] }
    recognition.onresult!(result)
    recognition.onresult!(result)
    expect(text.value).toBe('Mein Entwurf mit Sprache')
    const lateResult = recognition.onresult!
    dictation.stop()
    text.value = ''
    lateResult({ results: [...result.results, { isFinal: true, 0: { transcript: 'zu spät' } }] })
    expect(text.value).toBe('')
    expect(dictation.listening.value).toBe(false)
    expect(recognition.abort).toHaveBeenCalledOnce()
    expect(focus).toHaveBeenCalled()
    wrapper.unmount()
  })
  it('ignores delayed end and error callbacks from an earlier session', () => {
    vi.stubGlobal('SpeechRecognition', Recognition)
    const { wrapper, dictation } = setup()
    dictation.toggle()
    const lateEnd = Recognition.latest.onend!
    const lateError = Recognition.latest.onerror!
    dictation.stop()
    dictation.toggle()
    const active = Recognition.latest
    lateEnd()
    lateError()
    expect(dictation.listening.value).toBe(true)
    expect(dictation.error.value).toBe(false)
    expect(active.abort).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('reports microphone errors and cleans up an active session on unmount', () => {
    vi.stubGlobal('webkitSpeechRecognition', Recognition)
    const { wrapper, dictation, text } = setup()
    dictation.toggle()
    Recognition.latest.onerror!()
    expect(dictation.error.value).toBe(true)
    expect(dictation.listening.value).toBe(false)
    expect(text.value).toBe('Mein Entwurf')
    dictation.toggle()
    expect(dictation.error.value).toBe(false)
    const active = Recognition.latest
    wrapper.unmount()
    expect(active.abort).toHaveBeenCalledOnce()
  })
})
