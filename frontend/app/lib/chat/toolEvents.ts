import type { ChatWsEvent } from '../../types/generated/chat-ws'
import type { ToolProjection } from '../../types/generated/chat-ws-server'
import { toolWsDefinitions } from '../../types/generated/tool-ws-schema'

export type ToolWsEvent = Extract<ChatWsEvent, { type: `tool.${string}` }>
export type ToolRunState = ToolProjection & { conversationId: string, generationId: string }
export type ToolRunRecords = Record<string, ToolRunState>
const terminal = new Set(['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted', 'outcome_unknown'])

interface Schema {
  $ref?: string
  const?: unknown
  enum?: unknown[]
  anyOf?: Schema[]
  type?: string
  properties?: Record<string, Schema>
  required?: string[]
  additionalProperties?: boolean
  items?: Schema
  maxItems?: number
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  pattern?: string
  format?: string
}
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Limited to the shapes emitted by the checked Pydantic generator. */
function matches(value: unknown, schema: Schema): boolean {
  if (schema.$ref) return matches(value, toolWsDefinitions[schema.$ref.replace('#/$defs/', '')] as Schema)
  if (Object.hasOwn(schema, 'const') && value !== schema.const) return false
  if (schema.enum && !schema.enum.includes(value)) return false
  if (schema.anyOf) return schema.anyOf.some(option => matches(value, option))
  switch (schema.type) {
    case 'null': return value === null
    case 'boolean': return typeof value === 'boolean'
    case 'integer': return typeof value === 'number' && Number.isSafeInteger(value) && value >= (schema.minimum ?? -Infinity) && value <= (schema.maximum ?? Infinity)
    case 'string': return typeof value === 'string' && value.length >= (schema.minLength ?? 0) && value.length <= (schema.maxLength ?? Infinity)
      && (!schema.pattern || new RegExp(schema.pattern).test(value))
      && (schema.format !== 'uuid' || uuid.test(value))
      && (schema.format !== 'date-time' || (/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value))))
    case 'array': return Array.isArray(value) && value.length <= (schema.maxItems ?? Infinity) && Boolean(schema.items) && value.every(item => matches(item, schema.items!))
    case 'object': return record(value) && (schema.required ?? []).every(key => Object.hasOwn(value, key))
      && Object.entries(value).every(([key, item]) => schema.properties?.[key] ? matches(item, schema.properties[key]!) : schema.additionalProperties !== false)
    default: return Object.hasOwn(schema, 'const') || Boolean(schema.enum)
  }
}
function validProjection(value: ToolProjection): boolean {
  return (value.state === 'succeeded') === Boolean(value.result)
}

export function validateToolEvent(value: unknown): value is ToolWsEvent {
  if (!record(value) || value.version !== 1 || value.eventVersion !== 1) return false
  if (new TextEncoder().encode(JSON.stringify(value)).length > 16_384) return false
  const name = value.type === 'tool.snapshot' ? 'ToolSnapshotEvent' : 'ToolEvent'
  if (!matches(value, toolWsDefinitions[name] as Schema)) return false
  const event = value as unknown as ToolWsEvent
  if (event.type === 'tool.snapshot') return event.runs.every(run => validProjection(run) && run.lastSequence <= event.lastSequence)
  const states: Record<string, string[]> = {
    'tool.started': ['running'], 'tool.progress': ['queued', 'running', 'awaiting_approval'],
    'tool.result': ['succeeded'], 'tool.completed': ['succeeded'],
    'tool.approval_required': ['awaiting_approval'], 'tool.failed': ['failed', 'interrupted', 'outcome_unknown'],
    'tool.cancelled': ['cancelled'], 'tool.timed_out': ['timed_out'],
  }
  return validProjection(event.payload) && Boolean(states[event.type]?.includes(event.payload.state))
    && event.runId === event.payload.runId && event.seq === event.payload.lastSequence
    && event.timestamp === event.payload.updatedAt
    && (event.type !== 'tool.approval_required' || Boolean(event.payload.approval))
}

export function applyToolProjection(records: ToolRunRecords, next: ToolRunState): ToolRunRecords {
  const previous = Object.hasOwn(records, next.runId) ? records[next.runId] : undefined
  if (previous && (previous.conversationId !== next.conversationId || previous.generationId !== next.generationId
    || next.lastSequence <= previous.lastSequence || (terminal.has(previous.state) && next.state !== previous.state))) return records
  const entries = Object.entries(records).filter(([id]) => id !== next.runId)
  return Object.fromEntries([...entries.slice(-1023), [next.runId, next]]) as ToolRunRecords
}
