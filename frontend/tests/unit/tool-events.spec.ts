import { describe, expect, it } from 'vitest'
import { applyToolProjection, validateToolEvent } from '../../app/lib/chat/toolEvents'
import type { ToolRunRecords, ToolRunState } from '../../app/lib/chat/toolEvents'

const now = '2026-10-13T12:00:00Z'
function projection(sequence = 1): ToolRunState {
  return { runId: crypto.randomUUID(), conversationId: crypto.randomUUID(), generationId: crypto.randomUUID(),
    toolId: 'web.search.v1', state: 'running', lastSequence: sequence, updatedAt: now,
    cancelRequested: false, approval: null, result: null, errorCode: null }
}
function event(run = projection()) {
  const { conversationId, generationId, ...payload } = run
  return { version: 1, eventVersion: 1, type: 'tool.started', conversationId, generationId,
    runId: run.runId, seq: run.lastSequence, timestamp: now, payload }
}

describe('public tool contract', () => {
  it('validates the generated schema and snapshot shape', () => {
    const value = event()
    expect(validateToolEvent(value)).toBe(true)
    expect(validateToolEvent({ version: 1, eventVersion: 1, type: 'tool.snapshot', conversationId: value.conversationId,
      generationId: value.generationId, lastSequence: 1, timestamp: now, runs: [value.payload] })).toBe(true)
  })
  it.each([
    { eventVersion: 2 }, { version: 2 }, { type: 'tool.execute' }, { seq: 0 }, { seq: '1' },
    { timestamp: '2026-10-13T12:00:00' }, { runId: 'bad-uuid' }, { input: 'secret' },
  ])('rejects invalid envelopes: %j', change => expect(validateToolEvent({ ...event(), ...change })).toBe(false))
  it.each([
    { toolId: 'unknown.tool.v1' }, { input: 'secret' }, { output: {} }, { state: 'queued' },
    { lastSequence: 2 }, { errorCode: 'secret error' }, { cancelRequested: 'false' },
    { result: { resultVersion: 1, sourceCount: 9 } }, { secret: 'x'.repeat(20_000) },
  ])('rejects unsafe projections: %j', change => {
    const value = event()
    expect(validateToolEvent({ ...value, payload: { ...value.payload, ...change } })).toBe(false)
  })
  it('requires a validated result reference for terminal success', () => {
    const value = event()
    expect(validateToolEvent({ ...value, type: 'tool.completed', payload: { ...value.payload, state: 'succeeded' } })).toBe(false)
    expect(validateToolEvent({ ...value, type: 'tool.completed', payload: { ...value.payload, state: 'succeeded', result: { resultVersion: 1, sourceCount: 5 } } })).toBe(true)
  })
  it('rejects oversized snapshot pages and projections beyond the watermark', () => {
    const value = event()
    const snapshot = { version: 1, eventVersion: 1, type: 'tool.snapshot', conversationId: value.conversationId,
      generationId: value.generationId, lastSequence: 1, timestamp: now, runs: [value.payload] }
    expect(validateToolEvent({ ...snapshot, runs: Array(17).fill(value.payload) })).toBe(false)
    expect(validateToolEvent({ ...snapshot, lastSequence: 0 })).toBe(false)
  })
})

describe('existing chat tool projection', () => {
  it('deduplicates replay and stale updates and preserves terminal state', () => {
    const run = projection()
    let records = applyToolProjection({}, run)
    expect(applyToolProjection(records, run)).toBe(records)
    records = applyToolProjection(records, { ...run, state: 'cancelled', lastSequence: 3 })
    expect(applyToolProjection(records, { ...run, lastSequence: 2 })).toBe(records)
    expect(applyToolProjection(records, { ...run, lastSequence: 4 })).toBe(records)
    expect(applyToolProjection(records, { ...run, state: 'failed', lastSequence: 4 })).toBe(records)
    expect(records[run.runId]?.state).toBe('cancelled')
  })
  it('rejects a run moving to another conversation or generation', () => {
    const run = projection()
    const records = applyToolProjection({}, run)
    expect(applyToolProjection(records, { ...run, conversationId: crypto.randomUUID(), lastSequence: 2 })).toBe(records)
    expect(applyToolProjection(records, { ...run, generationId: crypto.randomUUID(), lastSequence: 2 })).toBe(records)
  })
  it('reconstructs terminal results after reload without duplicate result content', () => {
    const run = { ...projection(8), state: 'succeeded' as const, result: { resultVersion: 1 as const, sourceCount: 5 } }
    const records = applyToolProjection({}, run)
    expect(records[run.runId]?.result?.sourceCount).toBe(5)
    expect(applyToolProjection(records, run)).toBe(records)
  })
  it('bounds the projection cache', () => {
    let records: ToolRunRecords = {}
    for (let i = 0; i < 1030; i++) records = applyToolProjection(records, projection())
    expect(Object.keys(records)).toHaveLength(1024)
  })
})
