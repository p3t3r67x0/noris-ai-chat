import type { DropdownMenuItem } from '@nuxt/ui'
import type { MessageKey } from './messages'

export const helpDestinations = [
  { title: 'documentation', icon: 'i-lucide-book-open', to: 'https://github.com/p3t3r67x0/noris-ai-chat/blob/main/README.md', external: true },
  { title: 'shortcuts', icon: 'i-lucide-command', to: '/settings/keyboard', external: false },
  { title: 'reportBug', icon: 'i-lucide-bug', to: 'https://github.com/p3t3r67x0/noris-ai-chat/issues/new', external: true },
] as const

export function helpMenuItems(t: (key: MessageKey) => string): DropdownMenuItem[] {
  return helpDestinations.map(destination => ({
    label: t(destination.title), icon: destination.icon, to: destination.to,
    ...(destination.external ? { target: '_blank', rel: 'noopener noreferrer' } : {}),
  }))
}
