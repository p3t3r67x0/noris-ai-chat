import type { MessageKey } from '../settings/messages'

export type CommandId = 'learning' | 'search' | 'reasoning' | 'model' | 'image' | 'file' | 'help'
export interface CommandContext {
  learning: boolean
  search: boolean
  reasoning: boolean
  model: boolean
  image: boolean
  file: boolean
  actions: Partial<Record<CommandId, () => void>>
}
export interface ChatCommand {
  id: CommandId
  name: string
  label: MessageKey
  description: MessageKey
  icon: string
  aliases: readonly string[]
  available: (context: CommandContext) => boolean
  execute: (context: CommandContext) => boolean
}

function command(definition: Omit<ChatCommand, 'available' | 'execute'>): ChatCommand {
  const available = (context: CommandContext) => Boolean(context.actions[definition.id]) && (definition.id === 'help' || context[definition.id])
  return {
    ...definition,
    available,
    execute(context) {
      if (!available(context)) return false
      context.actions[definition.id]?.()
      return true
    },
  }
}

// One registry owns discovery, aliases, permissions and local dispatch.
// Image generation needs an actual integration/handler; image INPUT is insufficient.
export const CHAT_COMMANDS: readonly ChatCommand[] = [
  command({ id: 'learning', name: 'lernen', label: 'learning', description: 'learnNew', icon: 'i-lucide-book-open', aliases: ['learn', 'study'] }),
  command({ id: 'search', name: 'suche', label: 'webSearch', description: 'realtimeInformation', icon: 'i-lucide-globe', aliases: ['search', 'web'] }),
  command({ id: 'reasoning', name: 'denken', label: 'chooseReasoning', description: 'reasoningDescription', icon: 'i-lucide-sparkles', aliases: ['think', 'reasoning'] }),
  command({ id: 'model', name: 'modell', label: 'chooseModel', description: 'modelDescription', icon: 'i-lucide-box', aliases: ['model'] }),
  command({ id: 'image', name: 'bild', label: 'createImage', description: 'visualizeSomething', icon: 'i-lucide-image', aliases: ['image'] }),
  command({ id: 'file', name: 'datei', label: 'addPhotosFiles', description: 'uploadFromComputer', icon: 'i-lucide-paperclip', aliases: ['file', 'upload'] }),
  command({ id: 'help', name: 'hilfe', label: 'commandHelp', description: 'commandHelpDescription', icon: 'i-lucide-circle-help', aliases: ['help'] }),
]

export interface CommandToken { start: number, end: number, query: string }
export function commandToken(text: string, caret = text.length): CommandToken | null {
  if (caret < 0 || caret > text.length || (text[caret] && !/\s/.test(text[caret]!))) return null
  const match = /(?:^|\s)\/([\p{L}]*)$/u.exec(text.slice(0, caret))
  return match ? { start: caret - match[1]!.length - 1, end: caret, query: match[1]!.toLocaleLowerCase() } : null
}
export function findCommand(name: string): ChatCommand | undefined {
  const query = name.toLocaleLowerCase()
  return CHAT_COMMANDS.find(entry => entry.name === query || entry.aliases.includes(query))
}
export function matchingCommands(query: string, context: CommandContext): ChatCommand[] {
  const filter = query.toLocaleLowerCase()
  return CHAT_COMMANDS.filter(entry => entry.available(context) && [entry.name, ...entry.aliases].some(name => name.startsWith(filter)))
}

// The send guard also runs after Escape, paste, mobile submit, and programmatic updates.
export function leadingCommand(text: string): { command: ChatCommand, token: CommandToken } | null {
  const match = /^\s*\/([\p{L}]+)(?=\s|$)/u.exec(text)
  const entry = match && findCommand(match[1]!)
  return match && entry ? { command: entry, token: { start: match[0].lastIndexOf('/'), end: match[0].length, query: match[1]! } } : null
}
