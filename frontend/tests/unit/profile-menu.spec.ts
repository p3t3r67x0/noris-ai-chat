import { describe, expect, it } from 'vitest'
import { helpDestinations, helpMenuItems } from '../../app/lib/settings/profileMenu'
import { translate } from '../../app/lib/settings/messages'

describe('supported profile help destinations', () => {
  it('uses real repository documents and the settings shortcut route', () => {
    const items = helpMenuItems(key => translate(key, 'de'))
    expect(items.map(item => item.to)).toEqual([
      'https://github.com/p3t3r67x0/noris-ai-chat/blob/main/README.md', '/settings/keyboard',
      'https://github.com/p3t3r67x0/noris-ai-chat/issues/new',
    ])
    expect(items.map(item => item.label)).toEqual(['Dokumentation', 'Tastaturkürzel', 'Fehler melden'])
    expect(helpDestinations.every(destination => destination.to.startsWith('/settings/') || destination.to.startsWith('https://github.com/p3t3r67x0/noris-ai-chat/'))).toBe(true)
  })
  it('translates labels and isolates external tabs', () => {
    const items = helpMenuItems(key => translate(key, 'en'))
    expect(items[1]?.label).toBe('Keyboard shortcuts')
    expect(items[1]?.target).toBeUndefined()
    for (const item of [items[0]!, items[2]!]) {
      expect(item.target).toBe('_blank')
      expect(item.rel).toBe('noopener noreferrer')
    }
    expect(items.map(item => item.label)).not.toContain('Log out')
  })
})
