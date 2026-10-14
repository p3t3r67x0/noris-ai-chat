import type { ResearchView } from './types'
import type { MessageKey } from '../settings/messages'

export const researchStates: Record<ResearchView['state'], MessageKey> = {
  planning: 'researchPlanning', searching: 'researchSearching', selecting: 'researchSelecting',
  fetching: 'researchFetching', grounding: 'researchGrounding', generating: 'researchGenerating',
  completed: 'researchCompleted', failed: 'researchFailed', cancelled: 'researchCancelled',
  interrupted: 'researchInterrupted', skipped: 'researchSkipped',
}

export function researchErrorKey(code: string | undefined): MessageKey {
  switch (code) {
    case 'RESEARCH_DISABLED': return 'researchDisabled'
    case 'RESEARCH_APPROVAL_REQUIRED': return 'researchApproval'
    case 'MODEL_UNAVAILABLE': return 'researchModel'
    case 'CONTEXT_LIMIT': return 'researchContext'
    case 'BUDGET_LIMIT': return 'researchBudget'
    case 'RESEARCH_NO_SOURCES': return 'researchNoSources'
    case 'RESEARCH_INVALID': return 'researchInvalid'
    case 'TIMEOUT': return 'researchTimeout'
    case 'RESEARCH_UNAVAILABLE': return 'researchUnavailable'
    case 'LLM_DISABLED': case 'PROVIDER_ERROR': case 'PROVIDER_AUTH_FAILED': return 'researchLlm'
    default: return 'researchFailed'
  }
}

export function sourceHref(value: string | null | undefined): string | undefined {
  try {
    const url = new URL(value ?? '')
    if (['https:', 'http:'].includes(url.protocol) && !url.username && !url.password) return url.href
  }
  catch { /* Invalid provenance is never an interactive URL. */ }
  return undefined
}
export function sourceDomain(value: string): string {
  try { return new URL(sourceHref(value) ?? '').hostname }
  catch { return '' }
}

/** Convert server Unicode codepoint offsets once, preserving all original text. */
export function citationPlaceholders(content: string, citations: ResearchView['citations']) {
  let prefix = `\uE000noris${crypto.randomUUID()}_`
  while (content.includes(prefix)) prefix += '_'
  const offsets = [0]
  for (const character of content) offsets.push(offsets.at(-1)! + character.length)
  const replacements = new Map<string, string>()
  let result = '', previous = 0
  for (const citation of [...citations].sort((a, b) => a.start - b.start).slice(0, 256)) {
    const start = offsets[citation.start], end = offsets[citation.end]
    const original = `[[${citation.marker}]]`
    if (start === undefined || end === undefined || start < previous || content.slice(start, end) !== original || !/^R[1-3]$/.test(citation.marker)) continue
    const placeholder = `${prefix}${replacements.size}\uE001`
    result += content.slice(previous, start) + placeholder
    replacements.set(placeholder, original)
    previous = end
  }
  result += content.slice(previous)
  const restore = (value: string) => {
    for (const [placeholder, original] of replacements) value = value.replaceAll(placeholder, original)
    return value
  }
  return { content: result, prefix, replacements, restore }
}
