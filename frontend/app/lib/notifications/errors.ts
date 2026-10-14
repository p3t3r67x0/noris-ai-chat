export type NotificationSeverity = 'success' | 'info' | 'warning' | 'error'
export type ErrorCategory = 'transient' | 'persistent' | 'action' | 'generation'
export type RecoveryStrategy = 'retry' | 'reload' | 'models' | 'signin' | 'configuration' | 'edit' | 'remove' | 'none'
export type NotificationOperation = 'generation' | 'models' | 'upload' | 'attachments' | 'attachment-remove' | 'settings' | 'history' | 'older-history' | 'variant' | 'sidebar' | 'archive' | 'search' | 'create' | 'rename' | 'restore' | 'delete' | 'preferences' | 'draft' | 'storage' | 'import' | 'connection'

interface ErrorDefinition { category: ErrorCategory, message: string, recovery: RecoveryStrategy, severity: 'error' | 'warning' | 'info' }
const definition = (category: ErrorCategory, message: string, recovery: RecoveryStrategy = 'retry', severity: ErrorDefinition['severity'] = 'error'): ErrorDefinition => ({ category, message, recovery, severity })

// Presentation of the existing REST/stream contracts. No backend codes or states are replaced.
export const ERROR_PRESENTATIONS: Readonly<Record<string, ErrorDefinition>> = {
  ACCESS_DENIED: definition('persistent', 'Bitte melde dich für den Chatzugriff an.', 'signin'),
  ORIGIN_DENIED: definition('persistent', 'Der Chatzugriff ist für diese Adresse nicht freigegeben.', 'configuration'),
  LLM_DISABLED: definition('persistent', 'Die Modellanbindung ist noch nicht freigeschaltet.', 'configuration'),
  RESEARCH_DISABLED: definition('persistent', 'Die Recherche ist nicht freigeschaltet.', 'configuration'),
  RESEARCH_UNAVAILABLE: definition('transient', 'Die Recherche ist derzeit nicht verfügbar.'),
  RESEARCH_INVALID: definition('transient', 'Die Anfrage ist für die Recherche nicht zulässig.', 'edit'),
  RESEARCH_NO_SOURCES: definition('transient', 'Die Recherche hat keine verwendbaren Quellen geliefert.', 'edit'),
  RESEARCH_FAILED: definition('transient', 'Die Recherche konnte nicht sicher abgeschlossen werden.'),
  RESEARCH_APPROVAL_REQUIRED: definition('persistent', 'Die Recherche benötigt eine ausdrückliche Freigabe.', 'configuration'),
  MODEL_UNAVAILABLE: definition('persistent', 'Dein gewähltes Modell ist nicht mehr verfügbar. Wähle ein verfügbares Modell; dein Chat und Entwurf bleiben erhalten.', 'models'),
  MODEL_CATALOG_STALE: definition('persistent', 'Der Modellkatalog ist veraltet. Neue Anfragen sind bis zur Prüfung gesperrt.', 'reload', 'warning'),
  NO_MODELS: definition('persistent', 'Für diesen Zugang sind derzeit keine Chatmodelle verfügbar.', 'models', 'warning'),
  INVALID_CONFIGURATION: definition('persistent', 'Die Modellkonfiguration konnte nicht gelesen werden. Bitte lade die Modelle erneut.', 'reload'),
  PROVIDER_AUTH_FAILED: definition('persistent', 'Die Anmeldung beim Modelldienst funktioniert derzeit nicht. Bitte prüfe den Modellzugriff.', 'configuration'),
  PROVIDER_UNREACHABLE: definition('transient', 'Der Modelldienst ist momentan nicht erreichbar. Bitte versuche es erneut.'),
  PROVIDER_ERROR: definition('transient', 'Der Modelldienst konnte die Anfrage gerade nicht bearbeiten. Bitte versuche es erneut.'),
  NETWORK_ERROR: definition('transient', 'Die Verbindung ist unterbrochen. Prüfe deine Internetverbindung und versuche es erneut.'),
  TIMEOUT: definition('transient', 'Die Anfrage hat zu lange gedauert. Bitte versuche es erneut.'),
  RATE_LIMIT: definition('transient', 'Es laufen gerade zu viele Anfragen. Warte einen Moment und versuche es erneut.', 'retry', 'warning'),
  CONNECTION_LIMIT: definition('transient', 'Es sind zu viele Chatverbindungen geöffnet. Schließe einen anderen Chat-Tab und verbinde dich erneut.', 'reload', 'warning'),
  NOT_READY: definition('transient', 'Der Chatdienst ist momentan nicht bereit. Bitte versuche es gleich erneut.'),
  BUDGET_LIMIT: definition('persistent', 'Das tägliche Nutzungslimit ist erreicht. Bitte versuche es morgen erneut.', 'none', 'warning'),
  STREAM_INTERRUPTED: definition('generation', 'Die Antwort wurde unterbrochen. Der bisherige Text bleibt erhalten. Bitte versuche es erneut.'),
  INTERRUPTED: definition('generation', 'Die Generierung wurde unterbrochen. Der gespeicherte Antwortstand bleibt erhalten.'),
  INVALID_RESPONSE: definition('generation', 'Die Antwort konnte nicht vollständig übertragen werden. Bitte versuche es erneut.'),
  OUTPUT_LIMIT: definition('generation', 'Das Ausgabelimit ist erreicht. Der bisherige Text bleibt erhalten.', 'none', 'warning'),
  RESPONSE_SIZE_LIMIT: definition('generation', 'Die Antwort hat ihre Größenbegrenzung erreicht. Der bisherige Text bleibt erhalten.', 'none', 'warning'),
  STREAM_SIZE_LIMIT: definition('generation', 'Die Übertragung hat ihre Größenbegrenzung erreicht. Der bisherige Text bleibt erhalten.', 'none', 'warning'),
  CONTINUATION_LIMIT: definition('generation', 'Das Fortsetzungslimit ist erreicht. Der bisherige Text bleibt erhalten.', 'none', 'warning'),
  AUTO_CONTINUATION_LIMIT: definition('generation', 'Das Limit für automatische Fortsetzungen ist erreicht. Der bisherige Text bleibt erhalten.', 'none', 'warning'),
  DUPLICATE_CONTINUATION: definition('generation', 'Das Modell hat vorhandenen Text wiederholt. Die bisherige Antwort bleibt erhalten.', 'none', 'warning'),
  CANCELLED: definition('generation', 'Die Antwort wurde gestoppt. Der bisherige Text bleibt erhalten.', 'none', 'info'),
  CONTENT_FILTERED: definition('persistent', 'Der Modelldienst konnte diese Anfrage nicht beantworten. Bitte formuliere sie anders.', 'edit'),
  CONTEXT_LIMIT: definition('persistent', 'Der Chat mit seinen Anhängen ist für dieses Modell zu lang. Kürze den Inhalt oder wähle ein Modell mit größerem Kontext.', 'edit'),
  REQUEST_TOO_LARGE: definition('persistent', 'Die Anfrage ist zu groß. Bitte kürze die Nachricht oder entferne Anhänge.', 'edit'),
  REASONING_UNSUPPORTED: definition('persistent', 'Diese Denkstufe wird vom ausgewählten Modell nicht unterstützt. Wähle eine andere Denkstufe.', 'edit'),
  ATTACHMENT_NOT_FOUND: definition('persistent', 'Diese Datei ist nicht mehr verfügbar. Bitte hänge sie erneut an.', 'remove'),
  ATTACHMENT_TYPE: definition('persistent', 'Dieser Dateityp wird nicht unterstützt. Verwende Text, Markdown, PDF, PNG oder JPEG.', 'remove'),
  ATTACHMENT_INVALID: definition('persistent', 'Die Datei ist beschädigt oder hat ein anderes Format. Bitte wähle eine gültige Datei.', 'remove'),
  ATTACHMENT_PDF_ENCRYPTED: definition('persistent', 'Verschlüsselte PDFs werden nicht unterstützt. Bitte wähle eine unverschlüsselte Datei.', 'remove'),
  ATTACHMENT_PDF_PAGE_LIMIT: definition('persistent', 'Die PDF hat zu viele Seiten. Bitte wähle eine kleinere Datei.', 'remove'),
  ATTACHMENT_TEXT_LIMIT: definition('persistent', 'Die Datei enthält zu viel Text. Bitte kürze sie oder wähle eine kleinere Datei.', 'remove'),
  ATTACHMENT_PROCESSING_LIMIT: definition('persistent', 'Die Datei ist zu aufwendig zu verarbeiten. Bitte wähle eine kleinere Datei.', 'remove'),
  ATTACHMENT_SIZE: definition('persistent', 'Die Datei ist leer oder zu groß. Bitte wähle eine kleinere Datei mit Inhalt.', 'remove'),
  ATTACHMENT_QUOTA: definition('persistent', 'Die Datei- oder Speichergrenze ist erreicht. Entferne nicht mehr benötigte Anhänge.', 'remove'),
  ATTACHMENT_IN_USE: definition('persistent', 'Eine gesendete Datei kann nur zusammen mit dem Chat gelöscht werden.', 'none'),
  ATTACHMENT_INCOMPATIBLE: definition('persistent', 'Das gewählte Modell kann diesen Anhang nicht verwenden. Wähle ein passendes Modell oder entferne den Anhang.', 'models'),
  ATTACHMENT_PROCESSING_TIMEOUT: definition('transient', 'Die Dateiverarbeitung hat zu lange gedauert. Bitte versuche es erneut.'),
  ATTACHMENT_UPLOAD_TIMEOUT: definition('transient', 'Der Upload hat zu lange gedauert. Bitte versuche es erneut.'),
  NOT_FOUND: definition('persistent', 'Dieser Chat ist nicht mehr verfügbar. Lade die Chatliste erneut.', 'reload'),
  VERSION_CONFLICT: definition('action', 'Der Chat wurde inzwischen geändert. Lade den aktuellen Stand und versuche es erneut.', 'reload'),
  INVALID_CURSOR: definition('action', 'Die Chatliste hat sich geändert. Bitte lade sie erneut.', 'reload'),
  INVALID_PARENT: definition('action', 'Die ursprüngliche Nachricht ist nicht verfügbar. Bitte lade den Chat erneut.', 'reload'),
  INVALID_LEAF: definition('action', 'Diese Chatvariante ist nicht verfügbar. Bitte lade den Chat erneut.', 'reload'),
  INVALID_MESSAGE: definition('action', 'Die Nachricht konnte nicht übernommen werden. Bitte prüfe deine Eingabe.', 'edit'),
  MESSAGE_EXISTS: definition('action', 'Diese Nachricht wurde bereits geändert. Bitte lade den Chat erneut.', 'reload'),
  CONVERSATION_EXISTS: definition('action', 'Dieser Chat ist bereits mit anderen Daten vorhanden. Die lokale Sicherung bleibt erhalten.', 'none'),
  IMPORT_CONFLICT: definition('action', 'Der Import enthält Konflikte. Es wurden keine neuen Chats übernommen; der lokale Bestand bleibt erhalten.', 'none'),
  IMPORT_INVALID: definition('persistent', 'Die lokale Chatsicherung konnte nicht gelesen werden. Sie bleibt erhalten.', 'none'),
  GENERATION_NOT_FOUND: definition('generation', 'Die Generierung ist nicht mehr verfügbar. Lade den Chat erneut.', 'reload'),
  GENERATION_ACTIVE: definition('generation', 'Für diese Nachricht läuft bereits eine Antwort. Bitte warte auf ihren Abschluss.', 'none', 'info'),
  TITLE_ALREADY_ATTEMPTED: definition('action', 'Der Chat behält seinen bisherigen Titel.', 'none', 'info'),
  INVALID_INPUT: definition('action', 'Die Eingabe konnte nicht übernommen werden. Bitte prüfe sie und versuche es erneut.', 'edit'),
  INVALID_REQUEST: definition('action', 'Die Anfrage konnte nicht übernommen werden. Bitte lade den Chat erneut.', 'reload'),
  VALIDATION_ERROR: definition('action', 'Die Eingabe konnte nicht übernommen werden. Bitte prüfe sie und versuche es erneut.', 'edit'),
  HTTP_ERROR: definition('action', 'Die Anfrage konnte gerade nicht ausgeführt werden. Bitte versuche es erneut.'),
  DATABASE_ERROR: definition('transient', 'Der Chat konnte gerade nicht gespeichert werden. Dein bisheriger Text bleibt erhalten.'),
  INTERNAL_ERROR: definition('transient', 'Der Chatdienst konnte die Anfrage gerade nicht bearbeiten. Bitte versuche es erneut.'),
  REQUEST_FAILED: definition('action', 'Die Aktion konnte gerade nicht ausgeführt werden. Bitte versuche es erneut.'),
  MOCK_FAILURE: definition('generation', 'Die Antwort konnte nicht abgeschlossen werden. Bitte versuche es erneut.'),
  STORAGE_UNAVAILABLE: definition('persistent', 'Änderungen können gerade nicht lokal gespeichert werden. Behalte die Seite geöffnet, um deinen Entwurf zu sichern.', 'none', 'warning'),
  STORAGE_CHANGED: definition('persistent', 'Chats wurden in einem anderen Tab geändert. Lade diese Seite neu, um den aktuellen Stand zu verwenden.', 'reload', 'warning'),
  STORAGE_INVALID: definition('persistent', 'Gespeicherte Chats konnten nicht geladen werden. Die bisherige Sicherung bleibt erhalten.', 'none', 'warning'),
}

export const OPERATION_TITLES: Record<NotificationOperation, string> = {
  generation: 'Antwort konnte nicht erstellt werden.', models: 'Modelle nicht verfügbar.',
  upload: 'Upload fehlgeschlagen.', attachments: 'Anhänge konnten nicht geladen werden.', 'attachment-remove': 'Anhang konnte nicht entfernt werden.',
  settings: 'Einstellung konnte nicht gespeichert werden.', history: 'Chat konnte nicht geladen werden.', 'older-history': 'Ältere Nachrichten konnten nicht geladen werden.', variant: 'Chatvariante konnte nicht geladen werden.',
  sidebar: 'Chatliste konnte nicht geladen werden.', archive: 'Archiv konnte nicht geladen werden.', search: 'Suche fehlgeschlagen.',
  create: 'Chat konnte nicht gespeichert werden.', rename: 'Chat konnte nicht umbenannt werden.', restore: 'Chat konnte nicht wiederhergestellt werden.', delete: 'Chat konnte nicht gelöscht werden.',
  preferences: 'Auswahl konnte nicht gespeichert werden.', draft: 'Entwurf konnte nicht gespeichert werden.', storage: 'Lokale Sicherung nicht verfügbar.', import: 'Chats konnten nicht importiert werden.', connection: 'Chatverbindung unterbrochen.',
}

export interface ErrorContext {
  operation: NotificationOperation
  conversationId?: string | null
  generationId?: string | null
  requestId?: string | null
  resourceId?: string
  attemptId?: string
}
export interface ErrorDiagnostics { code: string, requestId: string | null, operation: NotificationOperation, conversationId: string | null, generationId: string | null, timestamp: string }
export interface NormalizedAppError extends ErrorDefinition { code: string, title: string, diagnostics: ErrorDiagnostics }
function record(value: unknown): Record<string, unknown> { return value !== null && typeof value === 'object' ? value as Record<string, unknown> : {} }
function identifier(value: unknown): string | null { return typeof value === 'string' && /^[a-zA-Z0-9_.:-]{1,128}$/.test(value) ? value : null }

export function normalizeAppError(cause: unknown, context: ErrorContext, now = new Date()): NormalizedAppError {
  const source = record(cause)
  const error = source.error ? record(source.error) : source
  const code = typeof error.code === 'string' && /^[A-Z][A-Z0-9_]{0,99}$/.test(error.code) ? error.code
    : cause instanceof TypeError ? 'NETWORK_ERROR' : error.name === 'TimeoutError' ? 'TIMEOUT' : 'REQUEST_FAILED'
  const presentation = ERROR_PRESENTATIONS[code] ?? ERROR_PRESENTATIONS.REQUEST_FAILED!
  return { ...presentation, code, title: OPERATION_TITLES[context.operation], diagnostics: {
    code, requestId: identifier(error.requestId ?? error.request_id ?? context.requestId),
    operation: context.operation, conversationId: identifier(context.conversationId), generationId: identifier(context.generationId), timestamp: now.toISOString(),
  } }
}

export function notificationKey(error: NormalizedAppError, context: ErrorContext): string {
  // Resource and attempt remain separate: two files/actions in one chat are never merged.
  return JSON.stringify([error.code, context.operation, context.conversationId ?? '', context.resourceId ?? '', context.generationId ?? error.diagnostics.requestId ?? context.attemptId ?? ''])
}
export function formatDiagnostics(details: ErrorDiagnostics): string {
  return [`Fehlercode: ${details.code}`, `Request-ID: ${details.requestId ?? 'nicht vorhanden'}`, `Funktion: ${details.operation}`, `Conversation-ID: ${details.conversationId ?? 'nicht vorhanden'}`, `Generation-ID: ${details.generationId ?? 'nicht vorhanden'}`, `Zeitpunkt: ${details.timestamp}`].join('\n')
}
