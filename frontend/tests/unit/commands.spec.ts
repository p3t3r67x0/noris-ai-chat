import { describe, expect, it, vi } from 'vitest'
import { CHAT_COMMANDS, commandToken, findCommand, leadingCommand, matchingCommands } from '../../app/lib/chat/commands'
import type { CommandContext } from '../../app/lib/chat/commands'

function context(): CommandContext {
  return { learning: true, search: false, reasoning: false, model: true, image: false, file: false, actions: { learning: vi.fn(), search: vi.fn(), reasoning: vi.fn(), model: vi.fn(), image: vi.fn(), file: vi.fn(), help: vi.fn() } }
}
describe('native command registry', () => {
  it('filters aliases and exposes only executable, currently permitted actions', () => {
    const capabilities = context()
    expect(matchingCommands('', capabilities).map(entry => entry.id)).toEqual(['learning', 'model', 'help'])
    expect(matchingCommands('STU', capabilities).map(entry => entry.id)).toEqual(['learning'])
    expect(matchingCommands('den', capabilities)).toEqual([])
    capabilities.reasoning = true
    expect(matchingCommands('den', capabilities).map(entry => entry.id)).toEqual(['reasoning'])
    delete capabilities.actions.reasoning
    expect(matchingCommands('den', capabilities)).toEqual([])
  })
  it('rechecks permissions before execution, including unavailable known commands', () => {
    const capabilities = context()
    expect(findCommand('model')?.execute(capabilities)).toBe(true)
    expect(capabilities.actions.model).toHaveBeenCalledOnce()
    capabilities.model = false
    expect(findCommand('modell')?.execute(capabilities)).toBe(false)
    expect(capabilities.actions.model).toHaveBeenCalledOnce()
    expect(findCommand('bild')?.execute(capabilities)).toBe(false)
    expect(capabilities.actions.image).not.toHaveBeenCalled()
    expect(leadingCommand('/bild eine Katze')?.command.id).toBe('image')
  })
  it('recognizes tokens at the caret without consuming surrounding text or URLs', () => {
    expect(commandToken('Vorne /ler hinten', 10)).toEqual({ start: 6, end: 10, query: 'ler' })
    expect(commandToken('/')).toEqual({ start: 0, end: 1, query: '' })
    for (const text of ['https://example.com/', '/usr/local', '1/2', 'Text', '/lernenX tail']) expect(commandToken(text)).toBeNull()
    expect(commandToken('/modell', 4)).toBeNull() // Caret inside a word.
    expect(leadingCommand('  /MODEL mein Entwurf')?.command.id).toBe('model')
    expect(leadingCommand('/unknown')).toBeNull()
    expect(leadingCommand('Erkläre /modell')).toBeNull()
  })
  it('keeps ids, canonical names and aliases unambiguous', () => {
    expect(new Set(CHAT_COMMANDS.map(entry => entry.id)).size).toBe(CHAT_COMMANDS.length)
    const names = CHAT_COMMANDS.flatMap(entry => [entry.name, ...entry.aliases])
    expect(new Set(names).size).toBe(names.length)
  })
})
