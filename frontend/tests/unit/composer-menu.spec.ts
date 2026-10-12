import { describe, expect, it, vi } from 'vitest'
import { composerMenuItems } from '../../app/lib/chat/composerMenu'
import { translate } from '../../app/lib/settings/messages'
import type { MessageKey } from '../../app/lib/settings/messages'

const t = (key: MessageKey) => translate(key, 'de')

describe('composer menu capabilities', () => {
  it('registers learning in the existing menu and reflects its actual saved state', () => {
    const learning = vi.fn()
    const active = composerMenuItems(t, { learning }, false, null, { learningActive: true })
    expect(active[1]).toMatchObject({ label: 'Lernen', description: 'Ausgewählt', disabled: false, unavailable: false, class: 'composer-menu-selected', onSelect: learning })
    const pending = composerMenuItems(t, { learning }, false, null, { learningAvailable: false })
    expect(pending[1]).toMatchObject({ disabled: true, unavailable: false })
    expect(pending[1]?.onSelect).toBeUndefined()
  })
  it('exposes the existing upload and leaves unimplemented tools disabled without handlers', () => {
    const upload = vi.fn()
    const items = composerMenuItems(t, { upload }, true)
    expect(items).toHaveLength(7)
    expect(items[0]).toMatchObject({ label: 'Fotos und Dateien hinzufügen', disabled: false, unavailable: false, onSelect: upload })
    for (const item of items.slice(1)) {
      expect(item).toMatchObject({ disabled: true, unavailable: true })
      expect(item.onSelect).toBeUndefined()
    }
  })
  it('shows the actual unavailable reason and prevents activation without requiring a manually saved chat', () => {
    const items = composerMenuItems(t, { upload: vi.fn() }, false, 'Backend konnte nicht geladen werden.')
    expect(items[0]).toMatchObject({ disabled: true, unavailable: false })
    expect(items[0]?.description).toBe('Backend konnte nicht geladen werden.')
    expect(items[0]?.onSelect).toBeUndefined()
  })
  it('requires an actual integration before enabling a future tool and translates its copy', () => {
    const web = vi.fn()
    const items = composerMenuItems(key => translate(key, 'en'), { web }, false)
    expect(items[4]).toMatchObject({ label: 'Web search', description: 'Search real-time information', disabled: false, unavailable: false, onSelect: web })
    expect(items[0]?.disabled).toBe(true)
  })
})
