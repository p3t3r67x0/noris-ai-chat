import { reactive } from 'vue'
import type { ApiSchemas } from '../../types/generated/api'

export type ChatLimits = ApiSchemas['ChatLimits']
export const DEFAULT_CHAT_LIMITS: ChatLimits = {
  max_message_chars: 32_000,
  max_response_chars: 262_144,
  max_stream_bytes: 16_777_216,
  stream_timeout_ms: 1_815_000,
  stream_idle_timeout_ms: 135_000,
}
export const CHAT_LIMITS = reactive<ChatLimits>({ ...DEFAULT_CHAT_LIMITS })
export const ABSOLUTE_MESSAGE_CHARS = 1_048_576

export function parseChatLimits(value: unknown): ChatLimits {
  if (!value || typeof value !== 'object') throw new Error('Ungültige Größenlimits')
  const ranges: Record<keyof ChatLimits, [number, number]> = {
    max_message_chars: [1, ABSOLUTE_MESSAGE_CHARS],
    max_response_chars: [1, ABSOLUTE_MESSAGE_CHARS],
    max_stream_bytes: [1024, 67_108_864],
    stream_timeout_ms: [1000, 3_615_000],
    stream_idle_timeout_ms: [1000, 615_000],
  }
  for (const key of Object.keys(ranges) as (keyof ChatLimits)[]) {
    const candidate: unknown = Reflect.get(value, key)
    const [minimum, maximum] = ranges[key]
    if (typeof candidate !== 'number' || !Number.isSafeInteger(candidate) || candidate < minimum || candidate > maximum) throw new Error('Ungültige Größenlimits')
  }
  const result = value as ChatLimits
  return Object.fromEntries(Object.keys(ranges).map(key => [key, Reflect.get(result, key)])) as unknown as ChatLimits
}
