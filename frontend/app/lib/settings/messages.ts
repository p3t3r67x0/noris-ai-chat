export const messages = {
  settings: ['Einstellungen', 'Settings'], general: ['Allgemein', 'General'], appearance: ['Darstellung', 'Appearance'],
  archived: ['Archivierte Chats', 'Archived chats'], keyboard: ['Tastatur', 'Keyboard'], models: ['Modelle', 'Models'],
  dataControls: ['Datenkontrollen', 'Data controls'], personal: ['Persönlich', 'Personal'], search: ['Suche', 'Search'],
  settingsSearch: ['Einstellungen durchsuchen', 'Search settings'], noResults: ['Keine passenden Einstellungen.', 'No matching settings.'],
  settingsNavigation: ['Einstellungsnavigation', 'Settings navigation'], backChat: ['Zurück zum Chat', 'Back to chat'],
  skipChat: ['Zum Chat springen', 'Skip to chat'], skipSettings: ['Zu den Einstellungen springen', 'Skip to settings'],
  language: ['Sprache', 'Language'], languageDescription: ['Sprache der App-Oberfläche', 'App interface language'],
  automatic: ['Automatisch erkennen', 'Detect automatically'], themeDescription: ['Wähle das Erscheinungsbild von noris AI.', 'Choose the appearance of noris AI.'],
  system: ['System', 'System'], light: ['Hell', 'Light'], dark: ['Dunkel', 'Dark'],
  importTitle: ['Lokale Chats importieren', 'Import local chats'],
  importDescription: ['Übertrage bisher lokal gespeicherte Unterhaltungen in die PostgreSQL-Datenbank.', 'Transfer locally saved conversations to the PostgreSQL database.'],
  import: ['Importieren', 'Import'], importConfirm: ['Import ausdrücklich starten', 'Confirm import'],
  importConfirmation: ['Überträgt die bisherigen Browser-Chats einschließlich Varianten, Titeln und Entwürfen in die Datenbank. Die lokale Sicherung bleibt erhalten. Bei Konflikten wird der Import abgebrochen.', 'Transfer browser chats, including variants, titles and drafts, to the database. The local backup is retained. Conflicts abort the import.'],
  noDataActions: ['Hier sind derzeit keine Datenaktionen verfügbar.', 'No data actions are currently available.'],
  cancel: ['Abbrechen', 'Cancel'], restore: ['Wiederherstellen', 'Restore'], delete: ['Löschen', 'Delete'],
  emptyArchive: ['Keine archivierten Chats.', 'No archived chats.'], archiveLoading: ['Archiv wird geladen …', 'Loading archive …'],
  archiveError: ['Das Archiv konnte nicht geladen werden.', 'The archive could not be loaded.'], retry: ['Erneut versuchen', 'Try again'],
  moreArchived: ['Weitere archivierte Chats laden', 'Load more archived chats'],
  defaultModel: ['Standardmodell', 'Default model'], defaultModelDescription: ['Wird auch im Eingabefeld verwendet.', 'Also used in the composer.'],
  refreshModels: ['Modelle neu laden', 'Refresh models'], available: ['Verfügbar', 'Available'], unavailable: ['Nicht verfügbar', 'Unavailable'],
  context: ['Kontextfenster', 'Context window'], outputLimit: ['Effektives Ausgabelimit', 'Effective output limit'],
  unknown: ['Nicht vom Provider angegeben', 'Not provided by the provider'], demoModels: ['Lokale Demo · synthetische Modelle', 'Local demo · synthetic models'],
  noModels: ['Keine Chatmodelle verfügbar.', 'No chat models available.'],
  sendMessage: ['Nachricht senden', 'Send message'], newline: ['Zeilenumbruch', 'New line'], chatSearch: ['Chat-Suche öffnen', 'Open chat search'],
  newChat: ['Neuer Chat', 'New chat'], stopResponse: ['Antwort stoppen', 'Stop response'],
  account: ['Dein Arbeitsbereich', 'Your workspace'], localAccount: ['Lokaler Arbeitsbereich', 'Local workspace'],
  demo: ['Lokale Demo', 'Local demo'], singleOwner: ['Single-Owner-Modus', 'Single-owner mode'],
  help: ['Hilfe', 'Help'], documentation: ['Dokumentation', 'Documentation'], shortcuts: ['Tastaturkürzel', 'Keyboard shortcuts'],
  reportBug: ['Fehler melden', 'Report a bug'], back: ['Zurück', 'Back'],
  home: ['Noris Home – neuer Chat', 'Noris Home – new chat'], searchChats: ['Chats suchen', 'Search chats'],
  chatControls: ['Chat-Steuerung', 'Chat controls'], openSidebar: ['Sidebar öffnen', 'Open sidebar'], closeSidebar: ['Sidebar schließen', 'Close sidebar'],
  chooseModel: ['Modell auswählen', 'Select model'], composerModel: ['Modell im Eingabefeld auswählen', 'Select composer model'],
  message: ['Nachricht', 'Message'], prompt: ['Frag noris AI …', 'Ask noris AI …'], welcome: ['Was möchtest du heute bewegen?', 'What would you like to work on today?'],
  disclaimer: ['noris AI kann Fehler machen. Prüfe wichtige Informationen.', 'noris AI can make mistakes. Check important information.'],
  stopping: ['Abbruch läuft', 'Stopping'], attachment: ['Dateien hinzufügen', 'Add files'],
  conversations: ['Gespräche', 'Conversations'], closeConversations: ['Gesprächsliste schließen', 'Close conversation list'],
  emptyConversations: ['Hier ist Platz für deine Gedanken. Deine Chats erscheinen hier.', 'Room for your ideas. Your chats appear here.'],
  moreChats: ['Weitere Chats laden', 'Load more chats'], rename: ['Umbenennen', 'Rename'], archive: ['Archivieren', 'Archive'],
  renameChat: ['Chat umbenennen', 'Rename chat'], chatTitle: ['Chat-Titel', 'Chat title'], save: ['Speichern', 'Save'],
  searchPlaceholder: ['Suchen...', 'Search...'], noChats: ['Keine Chats gefunden', 'No chats found'],
  recentChats: ['Letzte Chats', 'Recent chats'], closeSearch: ['Suche schließen', 'Close search'],
  searchLoading: ['Chats werden gesucht …', 'Searching chats …'], searchReady: ['Suche bereit', 'Search ready'],
  searchError: ['Die Suche ist fehlgeschlagen. Bitte versuche es erneut.', 'Search failed. Please try again.'],
  retrySearch: ['Suche erneut versuchen', 'Try searching again'],
} as const

export type MessageKey = keyof typeof messages
export type AppLanguage = 'de' | 'en'
export type LanguagePreference = 'auto' | AppLanguage
export function translate(key: MessageKey, language: AppLanguage): string {
  return messages[key][language === 'de' ? 0 : 1]
}
export function resolveLanguage(preference: LanguagePreference, browserLanguage: string): AppLanguage {
  return preference === 'auto' ? (browserLanguage.toLowerCase().startsWith('de') ? 'de' : 'en') : preference
}
