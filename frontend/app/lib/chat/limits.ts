import { reactive } from 'vue'

export const MAX_PERSISTED_MESSAGE_CHARS = 1_048_576
export const MAX_SNAPSHOT_CHARS = 6_000_000
export const DEFAULT_CHAT_LIMITS = {
  max_message_chars: 32_000,
  max_response_chars: 32_000,
  max_stream_bytes: 4_194_304,
  stream_timeout_ms: 135_000,
  stream_idle_timeout_ms: 45_000,
  max_continuations: 8,
}
export const chatLimits = reactive({ ...DEFAULT_CHAT_LIMITS })

export function applyChatLimits(value: unknown): void {
  if (!value || typeof value !== 'object') throw new Error('Ungültige Chat-Limits')
  const ceilings = { max_message_chars: MAX_PERSISTED_MESSAGE_CHARS, max_response_chars: MAX_PERSISTED_MESSAGE_CHARS, max_stream_bytes: 67_108_864, stream_timeout_ms: 3_660_000, stream_idle_timeout_ms: 660_000, max_continuations: 20 }
  for (const key of Object.keys(ceilings) as (keyof typeof ceilings)[]) {
    if (!(key in value)) throw new Error('Ungültige Chat-Limits')
    const limit = (value as Record<string, unknown>)[key]
    if (typeof limit !== 'number' || !Number.isSafeInteger(limit) || limit < 1 || limit > ceilings[key]) throw new Error('Ungültige Chat-Limits')
  }
  for (const key of Object.keys(ceilings) as (keyof typeof ceilings)[]) {
    chatLimits[key] = (value as Record<string, number>)[key]!
  }
}
