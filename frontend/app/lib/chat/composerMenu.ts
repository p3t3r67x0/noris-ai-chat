import type { DropdownMenuItem } from '@nuxt/ui'
import type { MessageKey } from '../settings/messages'

const entries = [
  { id: 'upload', label: 'addPhotosFiles', description: 'uploadFromComputer', icon: 'i-lucide-paperclip' },
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
export function composerMenuItems(t: (key: MessageKey) => string, actions: Partial<Record<ComposerAction, () => void>>, uploadAvailable: boolean, uploadUnavailableReason?: string | null): ComposerMenuItem[] {
  return entries.map(entry => {
    const action = actions[entry.id]
    const disabled = !action || (entry.id === 'upload' && !uploadAvailable)
    return {
      label: t(entry.label),
      description: entry.id === 'upload' && !uploadAvailable ? uploadUnavailableReason || t('uploadPreparing') : t(entry.description),
      icon: entry.icon,
      disabled,
      unavailable: !action,
      ...(!disabled ? { onSelect: action } : {}),
    }
  })
}
