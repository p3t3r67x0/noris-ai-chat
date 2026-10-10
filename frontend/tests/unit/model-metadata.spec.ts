import { describe, expect, it } from 'vitest'
import { modelDetails } from '../../app/lib/chat/modelMetadata'

describe('provider model details', () => {
  it('shows dated USD and cached input with conservative limits', () => {
    const details = modelDetails({ provider_context_window: 1048576, estimated_max_cost_usd: '0.32', cost: {
      currency: 'USD', input_usd_per_million: '10', cached_input_usd_per_million: '2', output_usd_per_million: '30', as_of: '2026-10-10T00:00:00Z',
    } }, false)
    expect(details).toContain('1.048.576 Tokens Kontext')
    expect(details).toContain('10 / 30 USD je Mio.')
    expect(details).toContain('2 USD Cache-Eingabe')
    expect(details).toContain('Abruf 10.10.2026')
    expect(details).toContain('Kostenobergrenze 0,32 USD')
    expect(details).not.toContain('Punkte')
  })
  it('keeps unknown, unsupported and stale quotes explicit', () => {
    expect(modelDetails({ cost: { currency: null } }, false)).toBe('Preis unbekannt')
    const stale = modelDetails({ cost: { currency: 'USD', input_usd_per_million: 'NaN', output_usd_per_million: null } }, true)
    expect(stale).toContain('Preis unbekannt')
    expect(stale).toContain('Veraltet · nicht verfügbar')
    expect(modelDetails({ cost: { currency: 'USD', input_usd_per_million: '-1' } }, false)).toBe('Preis unbekannt')
  })
  it('accepts exact Decimal zero and exponent serialization without false zero prices', () => {
    expect(modelDetails({ cost: { currency: 'USD', input_usd_per_million: '0E-10', output_usd_per_million: '1E-6' } }, false)).toContain('0 / 1E-6 USD')
    expect(modelDetails({ cost: { currency: 'USD', input_usd_per_million: '1E-1000' } }, false)).toBe('Preis unbekannt')
  })
  it('separates free and unconfirmed discount flags', () => {
    const details = modelDetails({ cost: { is_free: true, discount_to_user: '15' } }, false)
    expect(details).toContain('Als kostenlos gemeldet')
    expect(details).toContain('Abrechnung unbestätigt')
  })
})
