import type { DropdownMenuItem } from '@nuxt/ui'
import type { MessageKey } from '../settings/messages'

const entries = [
  { id: 'upload', label: 'addPhotosFiles', description: 'uploadFromComputer', icon: 'i-lucide-paperclip' },
  { id: 'learning', label: 'learning', description: 'learnNew', icon: 'i-lucide-book-open' },
  { id: 'library', label: 'addFromLibrary', description: 'browseYourFiles', icon: 'i-lucide-folder-open' },
  { id: 'image', label: 'createImage', description: 'visualizeSomething', icon: 'i-lucide-image' },
  { id: 'web', label: 'webSearch', description: 'realtimeInformation', icon: 'i-lucide-globe' },
  { id: 'research', label: 'deepResearch', description: 'detailedResearch', icon: 'i-lucide-telescope' },
  { id: 'sketch', label: 'sketch', description: 'drawAndAttach', icon: 'i-lucide-pencil' },
] as const satisfies readonly { id: string, label: MessageKey, description: MessageKey, icon: string }[]

export type ComposerAction = typeof entries[number]['id']
export type ComposerMenuItem = DropdownMenuItem & { unavailable: boolean }

// A real handler is required to enable an entry. Future integrations register
// their existing action here rather than adding a placeholder click action.
export function composerMenuItems(t: (key: MessageKey) => string, actions: Partial<Record<ComposerAction, () => void>>, uploadAvailable: boolean, uploadUnavailableReason?: string | null, options: { learningAvailable?: boolean, learningActive?: boolean, webAvailable?: boolean, webActive?: boolean, webReason?: string | null | undefined } = {}): ComposerMenuItem[] {
  return entries.map(entry => {
    const action = actions[entry.id]
    const disabled = !action || (entry.id === 'upload' && !uploadAvailable) || (entry.id === 'learning' && options.learningAvailable === false) || (entry.id === 'web' && options.webAvailable === false)
    return {
      label: t(entry.label),
      description: entry.id === 'web' && options.webAvailable === false ? options.webReason || t('researchUnavailable') : entry.id === 'web' && options.webActive ? t('selected') : entry.id === 'upload' && !uploadAvailable ? uploadUnavailableReason || t('uploadPreparing') : entry.id === 'learning' && options.learningActive ? t('selected') : t(entry.description),
      icon: entry.icon,
      disabled,
      unavailable: !action,
      ...(((entry.id === 'learning' && options.learningActive) || (entry.id === 'web' && options.webActive)) ? { class: 'composer-menu-selected' } : {}),
      ...(!disabled ? { onSelect: action } : {}),
    }
  })
}
