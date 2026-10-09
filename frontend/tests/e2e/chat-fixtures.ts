import type { Page } from '@playwright/test'
import type { ChatSnapshot } from '../../app/lib/chat/persistence'
import { CHAT_STORAGE_KEY } from '../../app/lib/chat/persistence'

export function savedChat(turns = 1): ChatSnapshot {
  const date = '2026-10-09T12:00:00.000Z'
  const snapshot: ChatSnapshot = {
    version: 1, conversations: { version: 1, activeConversationId: 'main', conversations: {} }, messages: {}, drafts: {}, preferredLeaves: {},
  }
  for (let index = 0; index < 45; index++) {
    const id = index === 0 ? 'main' : `conversation-${index}`
    snapshot.conversations.conversations[id] = { id, title: index === 0 ? 'Unser Gespräch' : `Gedanken ${index}`, createdAt: date, updatedAt: date, archivedAt: null, activeLeafMessageId: null }
  }
  for (let index = 0; index < turns; index++) {
    const user = `user-${index}`, assistant = `assistant-${index}`
    snapshot.messages[user] = { id: user, conversationId: 'main', parentMessageId: index ? `assistant-${index - 1}` : null, role: 'user', content: index ? `Frage ${index + 1}` : 'Wie können wir eine gute Idee weiterentwickeln?', status: 'completed', createdAt: date }
    snapshot.messages[assistant] = { id: assistant, conversationId: 'main', parentMessageId: user, role: 'assistant', content: '### Ein guter Anfang\n\nBeginne mit einer klaren Frage. Halte fest, für wen deine Idee hilfreich ist.\n\n1. Beschreibe dein Ziel.\n2. Probiere einen kleinen Schritt aus.\n3. Prüfe, was du gelernt hast.\n\n**Wir können gemeinsam daran weiterarbeiten.**', status: 'completed', createdAt: date }
    snapshot.conversations.conversations.main!.activeLeafMessageId = assistant
  }
  return snapshot
}
export async function seedChat(page: Page, snapshot: ChatSnapshot, theme = 'light') {
  await page.addInitScript(({ key, value, selectedTheme }) => {
    localStorage.setItem(key, value)
    localStorage.setItem('noris-ai-theme', selectedTheme)
  }, { key: CHAT_STORAGE_KEY, value: JSON.stringify(snapshot), selectedTheme: theme })
}

export function referenceChat(): ChatSnapshot {
  const snapshot = savedChat()
  for (const [index, conversation] of Object.values(snapshot.conversations.conversations).entries()) {
    conversation.title = index === 0 ? 'Fiktiver Tagesplan' : `Beispiel ${index + 1}`
  }
  snapshot.messages['user-0']!.content = 'Erstelle einen frei erfundenen Tagesplan mit drei einfachen Schritten.'
  snapshot.messages['assistant-0']!.content = `# Ein fiktiver Tagesplan mit drei einfachen Schritten für eine neutrale Demonstration

Diese Darstellung verwendet ausschließlich **frei erfundene Beispieldaten**. Sie dient zur Prüfung von Lesebreite, Abständen und gut erreichbaren Bedienelementen.

Ein ruhiger Start beginnt mit einer übersichtlichen Auswahl. **Notiere drei neutrale Tätigkeiten, entscheide dich für eine kleine Aufgabe und halte am Ende fest, welche nächsten Schritte sinnvoll erscheinen.** Plane dabei genügend Zeit für Pausen ein und bleibe bei einem einfachen Ablauf.

Am Vormittag entsteht ein kurzer Überblick. Danach folgt eine überschaubare Aufgabe. Zum Abschluss hilft ein kleiner Rückblick, die nächste Auswahl vorzubereiten. Weitere fiktive Angaben stehen auf der [Beispielseite](https://example.com). Diese Verknüpfung bezeichnet keine echte Person, Organisation oder Kundeninformation.

Alle Bezeichnungen und Gesprächsinhalte dieser Ansicht wurden eigens für einen synthetischen Test formuliert. Sie stammen aus keinem persönlichen Gespräch. Der Verlauf enthält weder echte Kontodaten noch private Projekte, Quellenangaben, Kennungen oder Zugangsdaten.

## 1. Drei neutrale Schritte

1. Erstelle einen Überblick über frei gewählte Tätigkeiten.
2. Plane einen kurzen Zeitraum für eine kleine Aufgabe.
3. Notiere einen sachlichen Rückblick und eine nächste Möglichkeit.`
  return snapshot
}

export function codeChat(): ChatSnapshot {
  const snapshot = savedChat()
  snapshot.messages['assistant-0']!.content = '## Ein kleines Beispiel\n\nCode lässt sich kopieren und bleibt auch auf kleinen Bildschirmen lesbar.\n\n```python\ndef greet(name: str) -> str:\n    return f"Hallo, {name}!"\n\nprint(greet("Noris"))\n```\n\n| Schritt | Ergebnis |\n| --- | --- |\n| Planen | Eine klare Frage |\n| Umsetzen | Ein erster Entwurf |'
  return snapshot
}
