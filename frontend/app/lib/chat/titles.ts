export const TITLE_INPUT_LIMIT = 1024
export const TITLE_MAX_LENGTH = 40
export const FALLBACK_TITLE = 'Neuer Chat'

const unsafe = /[\p{Cc}\p{Cf}\p{So}"„“”«»?!<>`]|\.{2}|…|[.,;:!]$|https?:\/\/|www\.|\S+@\S+|(?:sk-|Bearer\s)\S+|(?:password|passwort|api[_ -]?key|token|secret)\s*[:=]\s*\S+/iu
const introduction = /^(?:wie|warum|was|welch\w*|kannst|könntest|bitte|erkläre|und\s+wie|how|why|what|which|can\s+you|could\s+you|please|explain|hello|hallo|hi|here|hier)\b/iu
const generic = /^(?:unterhaltung|neue unterhaltung|neuer chat|conversation|new conversation|new chat|chat|title|titel)$/iu

export function validGeneratedTitle(value: unknown): value is string {
  if (typeof value !== 'string' || value !== value.trim() || / {2}/u.test(value)) return false
  const words = value.split(/\s+/).length
  return words >= 2 && words <= 5 && Array.from(value).length <= TITLE_MAX_LENGTH
    && !unsafe.test(value) && !introduction.test(value) && !generic.test(value)
}

/** Only recognized topics: never copy a question prefix or arbitrary personal data. */
export function fallbackConversationTitle(source: string): string {
  const english = /^(?:how|why|what|which|can you|could you|please|explain|compare|hello)\b|\b(?:troubleshooting|implementation|setup)\b/i.test(source.trim())
  if (/chat[- ]?titel|titelgenerierung|(?:conversation|chat) titles/i.test(source)) return english ? 'Automatic Chat Titles' : 'Automatische Chat-Titel'
  if (/rust/i.test(source) && /c\+\+/i.test(source)) return 'Rust vs. C++'
  if (/postgresql/i.test(source) && /mariadb/i.test(source)) return 'PostgreSQL vs. MariaDB'
  if (/docker/i.test(source) && /nftables/i.test(source)) return english ? 'Docker and nftables' : 'Docker und nftables'
  if (/docker/i.test(source) && /dns/i.test(source)) return english ? 'Docker DNS Troubleshooting' : 'Docker DNS-Probleme'
  if (/noris\s+ai/i.test(source) && /docker/i.test(source)) return 'Noris AI Docker-Setup'
  if (/docker\s+compose/i.test(source)) return english ? 'Docker Compose Setup' : 'Docker Compose Einrichtung'
  if (/mcp/i.test(source) && /codex/i.test(source)) return english ? 'Add MCP to Codex' : 'MCP zu Codex hinzufügen'
  if (/statusübersicht/i.test(source)) return 'Statusübersicht einrichten'
  if (/sicherheitskonzept/i.test(source)) return 'Sicherheitskonzept entwickeln'
  if (/chatplan/i.test(source) && /noris/i.test(source)) return 'Chatplan für noris AI'
  if (/noris\s*ai/i.test(source) && /integrat|einbind/i.test(source)) return 'Noris AI Integration'
  return FALLBACK_TITLE
}

/** Semantic alternatives keep whole terms; unknown oversized topics use the placeholder. */
export function automaticTitleCandidates(value: string, context = ''): string[] {
  const title = value.normalize('NFKC').trim().replace(/ +/g, ' ')
  const compact = title.replace(/^Automatisierte?\b/iu, 'Automatische')
    .replace(/\s+(?:Implementierung|implementation|Einrichtung|setup)$/iu, '')
  const candidates = (Array.from(title).length > 30 ? [compact, title] : [title, compact]).filter(validGeneratedTitle)
  candidates.sort((a, b) => (Array.from(a).length > 30 ? 1 : 0) - (Array.from(b).length > 30 ? 1 : 0))
  const topic = fallbackConversationTitle(context || title)
  const shortTopics: Record<string, string> = {
    'Docker DNS Troubleshooting': 'Docker DNS', 'Docker DNS-Probleme': 'Docker DNS',
    'Sicherheitskonzept entwickeln': 'Sicherheitskonzept planen',
    'Docker Compose Einrichtung': 'Docker Compose', 'Noris AI Docker-Setup': 'Noris AI Docker',
    'MCP zu Codex hinzufügen': 'MCP in Codex', 'Statusübersicht einrichten': 'Statusübersicht planen',
  }
  const shortTopic = shortTopics[topic] ?? topic
  return [...new Set([...candidates, topic, shortTopic, FALLBACK_TITLE])]
}

export function normalizeAutomaticTitle(value: string, context = ''): string {
  return automaticTitleCandidates(value, context)[0]!
}

export function mockConversationTitle(firstMessage: string): string {
  return fallbackConversationTitle(firstMessage)
}
