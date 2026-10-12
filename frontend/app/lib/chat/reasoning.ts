import type { ChatModel } from '../../composables/useModelSelection'

export type ReasoningPreference = 'instant' | 'medium' | 'high' | 'very_high' | 'pro'
export const REASONING_CHOICES: readonly { id: ReasoningPreference, label: string, description: string }[] = [
  { id: 'instant', label: 'Sofort', description: 'Geringster unterstützter Denkaufwand' },
  { id: 'medium', label: 'Mittel', description: 'Denkt länger für bessere Antworten' },
  { id: 'high', label: 'Hoch', description: 'Denkt länger für bessere Antworten' },
  { id: 'very_high', label: 'Sehr hoch', description: 'Denkt länger für bessere Antworten' },
  { id: 'pro', label: 'Pro', description: 'Intelligenz auf höchstem Niveau' },
]

export function isReasoningPreference(value: unknown): value is ReasoningPreference {
  return REASONING_CHOICES.some(choice => choice.id === value)
}

// The server owns the mapping. Category/name/provider effort strings cannot
// establish support, and a stale or unavailable catalog cannot enable options.
export function supportsPreference(model: ChatModel | undefined, preference: ReasoningPreference): boolean {
  return Boolean(model && !model.disabled && !model.virtual && model.reasoningPreferences?.includes(preference))
}

export function reasoningChoices(model: ChatModel | undefined) {
  return REASONING_CHOICES.filter(choice => supportsPreference(model, choice.id))
}
