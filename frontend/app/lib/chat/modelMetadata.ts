/** Optional catalog details never authorize generation or select a replacement model. */
export function modelDetails(value: Record<string, unknown>, stale: boolean): string {
  const parts: string[] = []
  const context = value.provider_context_window
  if (typeof context === 'number' && Number.isSafeInteger(context) && context > 0) parts.push(`${new Intl.NumberFormat('de-DE').format(context)} Tokens Kontext`)
  const cost = value.cost
  if (cost && typeof cost === 'object') {
    const quote = cost as Record<string, unknown>
    const usd = (amount: unknown): string | null => {
      if (typeof amount !== 'string' || !/^\d+(\.\d+)?$/.test(amount)) return null
      const parsed = Number(amount)
      return Number.isFinite(parsed) ? new Intl.NumberFormat('de-DE', { maximumFractionDigits: 4 }).format(parsed) : null
    }
    const input = usd(quote.input_usd_per_million)
    const output = usd(quote.output_usd_per_million)
    const cached = usd(quote.cached_input_usd_per_million)
    if (quote.is_free === true) parts.push('Als kostenlos gemeldet')
    else if (quote.currency === 'USD' && (input !== null || output !== null)) {
      parts.push(`${input ?? '?'} / ${output ?? '?'} USD je Mio. Tokens (Ein / Aus)`)
      if (cached !== null) parts.push(`${cached} USD Cache-Eingabe`)
    }
    else parts.push('Preis unbekannt')
    if (typeof quote.as_of === 'string' && Number.isFinite(Date.parse(quote.as_of))) parts.push(`Abruf ${new Date(quote.as_of).toLocaleDateString('de-DE')}`)
    const estimate = usd(value.estimated_max_cost_usd)
    if (estimate !== null && quote.is_free !== true) parts.push(`Kostenobergrenze ${estimate} USD je Anfrage bei lokalen Tokenlimits; ohne Rabatte`)
    if (quote.discount_to_user != null && quote.discount_to_user !== '0') parts.push('Rabatt gemeldet; Abrechnung unbestätigt')
  }
  if (stale) parts.push('Veraltet · nicht verfügbar')
  return parts.join(' · ')
}
