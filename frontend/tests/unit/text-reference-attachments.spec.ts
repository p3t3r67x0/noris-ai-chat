import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { useChatAttachments } from '../../app/composables/useChatAttachments'
import type { Conversation } from '../../app/lib/chat/conversations'

function fixture() {
  const active = ref<Conversation | null>({ id: 'main', title: 'Thema', titleSource: 'manual', titleGenerationAttempted: true, createdAt: '2026-10-09T12:00:00Z', updatedAt: '2026-10-09T12:00:00Z', archivedAt: null, activeLeafMessageId: 'source' })
  let attachments!: ReturnType<typeof useChatAttachments>
  const wrapper = mount(defineComponent({ setup() { attachments = useChatAttachments(undefined, active, ref(true), () => active.value!); return () => h('div') } }))
  return { wrapper, attachments, active }
}
const reference = (text: string) => ({ sourceMessageId: 'source', sourceConversationId: 'main', text })

beforeEach(() => localStorage.clear())
describe('existing attachment state with text references', () => {
  it('preserves exact text, isolates conversation drafts and removes individual references', async () => {
    const { wrapper, attachments, active } = fixture()
    await attachments.addReference(reference('  Erste Zeile\n\nZweiter Absatz  '))
    await attachments.addReference(reference('Zweiter Ausschnitt'))
    expect(attachments.confirmed.value.map(file => file.textReference?.text)).toEqual(['  Erste Zeile\n\nZweiter Absatz  ', 'Zweiter Ausschnitt'])
    const key = attachments.files.value[0]!.key
    active.value = { ...active.value!, id: 'other' }
    expect(attachments.files.value).toHaveLength(0)
    active.value = { ...active.value!, id: 'main' }
    await attachments.remove(key)
    expect(attachments.confirmed.value[0]?.textReference?.text).toBe('Zweiter Ausschnitt')
    attachments.sent('main')
    expect(attachments.files.value).toHaveLength(0)
    wrapper.unmount()
  })
  it('rejects oversized selections without silently truncating or blocking valid attachments', async () => {
    const { wrapper, attachments } = fixture()
    await attachments.addReference(reference('x'.repeat(32_001)))
    expect(attachments.files.value).toHaveLength(0)
    expect(attachments.error.value).toContain('32.000')
    await attachments.addReference(reference('Noch vollständig'))
    expect(attachments.blocked.value).toBe(false)
    expect(attachments.confirmed.value[0]?.textReference?.text).toBe('Noch vollständig')
    wrapper.unmount()
  })
  it('reserves attachment slots for rapid additions and restores pending references from the existing cache', async () => {
    let current = fixture()
    await Promise.all(Array.from({ length: 11 }, (_, index) => current.attachments.addReference(reference(`Ausschnitt ${index}`))))
    expect(current.attachments.files.value).toHaveLength(10)
    current.wrapper.unmount()
    current = fixture()
    expect(current.attachments.files.value).toHaveLength(10)
    expect(current.attachments.confirmed.value[9]?.textReference?.text).toBe('Ausschnitt 9')
    current.wrapper.unmount()
  })
})
