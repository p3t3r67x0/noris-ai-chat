export const TITLE_INPUT_LIMIT = 1024
export const FALLBACK_TITLE = 'Neuer Chat'

export function validGeneratedTitle(value: unknown): value is string {
  if (typeof value !== 'string' || value !== value.trim() || !value || Array.from(value).length > 50 || value.split(/\s+/).length > 6) return false
  return !/[\p{Cc}\p{Cf}\p{So}"„“”«»?!<>`]|[.]$|https?:\/\/|www\.|\S+@\S+|(?:sk-|Bearer\s)\S+|(?:password|passwort|api[_ -]?key|token|secret)\s*[:=]\s*\S+/iu.test(value)
    && !/^(?:wie|warum|was|welche|how|why|what|hello|hallo|hi|here|hier)\b/iu.test(value)
    && !/^(?:unterhaltung|neue unterhaltung|neuer chat|conversation|new conversation|new chat|chat|title|titel)$/iu.test(value)
}

export function mockConversationTitle(firstMessage: string): string {
  const english = /^(?:how|why|what|which|explain|compare|hello)\b/i.test(firstMessage.trim())
  if (/rust/i.test(firstMessage) && /c\+\+/i.test(firstMessage)) return 'Rust vs. C++'
  if (/postgresql/i.test(firstMessage) && /mariadb/i.test(firstMessage)) return 'PostgreSQL vs. MariaDB'
  if (/docker/i.test(firstMessage) && /dns/i.test(firstMessage)) return english ? 'Docker DNS troubleshooting' : 'Docker DNS-Probleme'
  if (/noris/i.test(firstMessage) && /docker/i.test(firstMessage)) return 'Noris AI Docker-Setup'
  if (/docker\s+compose/i.test(firstMessage)) return english ? 'Docker Compose setup' : 'Docker Compose Einrichtung'
  return english ? 'Local chat example' : 'Lokales Chat-Beispiel'
}
