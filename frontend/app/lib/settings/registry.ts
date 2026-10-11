import { messages, translate } from './messages'
import type { AppLanguage, MessageKey } from './messages'

export interface SettingEntry { id: string, title: MessageKey, keywords?: string[], requiresImport?: boolean }
export interface SettingsCategory {
  id: string, title: MessageKey, icon: string, group: 'personal' | 'noris', entries: SettingEntry[]
}
export const settingsRegistry: SettingsCategory[] = [
  { id: 'general', title: 'general', icon: 'i-lucide-settings', group: 'personal', entries: [{ id: 'language', title: 'language', keywords: ['Deutsch', 'English', 'Sprache der App-Oberfläche'] }] },
  { id: 'appearance', title: 'appearance', icon: 'i-lucide-sun', group: 'personal', entries: [{ id: 'theme', title: 'appearance', keywords: ['Dark Mode', 'Theme', 'Hell', 'Dunkel', 'System', 'Light'] }] },
  { id: 'archived', title: 'archived', icon: 'i-lucide-archive', group: 'personal', entries: [{ id: 'archive', title: 'archived', keywords: ['Wiederherstellen', 'Löschen', 'Restore', 'Delete'] }] },
  { id: 'keyboard', title: 'keyboard', icon: 'i-lucide-command', group: 'personal', entries: [{ id: 'shortcuts', title: 'shortcuts', keywords: ['Enter', 'Shift', 'Ctrl', 'Cmd'] }] },
  { id: 'data-controls', title: 'dataControls', icon: 'i-lucide-shield', group: 'personal', entries: [{ id: 'local-import', title: 'importTitle', keywords: ['Importieren', 'PostgreSQL', 'Import'], requiresImport: true }] },
  { id: 'models', title: 'models', icon: 'i-lucide-box', group: 'noris', entries: [{ id: 'default-model', title: 'defaultModel', keywords: ['LLM', 'Standard', 'Default'] }] },
]
export interface SettingsSearchResult { key: string, label: string, category: string, to: string }
const normalize = (value: string) => value.normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase().trim()
export function searchSettings(query: string, language: AppLanguage, capabilities: { importAvailable: boolean, models: readonly { id: string, label: string }[] }): SettingsSearchResult[] {
  const tokens = normalize(query).split(/\s+/).filter(Boolean)
  if (!tokens.length) return []
  const matches = (values: readonly string[]) => tokens.every(token => normalize(values.join(' ')).includes(token))
  const results: SettingsSearchResult[] = []
  for (const category of settingsRegistry) {
    const categoryLabel = translate(category.title, language)
    const root = `/settings/${category.id}`
    if (matches(messages[category.title])) results.push({ key: category.id, label: categoryLabel, category: categoryLabel, to: root })
    for (const entry of category.entries) {
      if (entry.requiresImport && !capabilities.importAvailable) continue
      if (matches([...messages[entry.title], ...(entry.keywords ?? [])])) {
        results.push({ key: `${category.id}-${entry.id}`, label: translate(entry.title, language), category: categoryLabel, to: `${root}#${entry.id}` })
      }
    }
    if (category.id === 'models') for (const model of capabilities.models) {
      if (matches([model.id, model.label])) results.push({ key: `model-${model.id}`, label: model.label, category: categoryLabel, to: `${root}#${encodeURIComponent(`model-${model.id}`)}` })
    }
  }
  return results.filter((result, index) => !results.slice(0, index).some(previous => previous.label === result.label && previous.category === result.category))
}
