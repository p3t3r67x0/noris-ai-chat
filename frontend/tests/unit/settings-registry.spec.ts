import { describe, expect, it } from 'vitest'
import { searchSettings, settingsRegistry } from '../../app/lib/settings/registry'
import { messages, resolveLanguage, translate } from '../../app/lib/settings/messages'

const capabilities = { importAvailable: true, models: [{ id: 'gpt-oss', label: 'GPT-OSS' }] }
describe('settings registry and locale', () => {
  it.each([
    ['Sprache', '/settings/general#language'], ['Dark Mode', '/settings/appearance#theme'],
    ['Importieren', '/settings/data-controls#local-import'], ['GPT-OSS', '/settings/models#model-gpt-oss'],
    ['Datensicherung', '/settings/backup'], ['Speicherfehler', '/settings/backup#persistence-status'],
  ])('locates supported settings for %s', (query, to) => {
    expect(searchSettings(query, 'de', capabilities).map(result => result.to)).toContain(to)
  })
  it('filters capabilities, missing categories and unavailable models without requests', () => {
    expect(searchSettings('Importieren', 'de', { ...capabilities, importAvailable: false })).toEqual([])
    expect(searchSettings('not-a-model', 'en', capabilities)).toEqual([])
    expect(settingsRegistry.map(category => category.id)).not.toContain('personalization')
    expect(settingsRegistry.map(category => category.id)).not.toContain('usage')
    expect(searchSettings('  DARK   MODE ', 'de', capabilities)[0]?.to).toBe('/settings/appearance#theme')
  })
  it('searches both languages and returns translated result labels', () => {
    expect(searchSettings('Sprache', 'en', capabilities)[0]?.label).toBe('Language')
    expect(searchSettings('language', 'de', capabilities)[0]?.label).toBe('Sprache')
    expect(searchSettings('Tastaturkurzel', 'de', capabilities)[0]?.to).toBe('/settings/keyboard#shortcuts')
  })
  it('has unique categories and stable setting identifiers', () => {
    expect(new Set(settingsRegistry.map(category => category.id)).size).toBe(settingsRegistry.length)
    for (const category of settingsRegistry) expect(new Set(category.entries.map(entry => entry.id)).size).toBe(category.entries.length)
  })
  it('resolves persisted and automatic preferences and translates all registered UI strings', () => {
    expect(resolveLanguage('auto', 'de-DE')).toBe('de')
    expect(resolveLanguage('auto', 'en-US')).toBe('en')
    expect(resolveLanguage('de', 'en')).toBe('de')
    expect(resolveLanguage('en', 'de')).toBe('en')
    for (const key of Object.keys(messages) as (keyof typeof messages)[]) {
      expect(translate(key, 'de')).toBeTruthy()
      expect(translate(key, 'en')).toBeTruthy()
    }
  })
})
