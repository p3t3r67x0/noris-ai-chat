import type { ChatRequest, ChatTransport, StreamEvent } from './types'

export interface MockClock { wait: (milliseconds: number, signal: AbortSignal) => Promise<void> }
export const browserClock: MockClock = {
  wait(milliseconds, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(new DOMException('Abgebrochen', 'AbortError')); return }
      const abort = () => { clearTimeout(timer); reject(new DOMException('Abgebrochen', 'AbortError')) }
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, milliseconds)
      signal.addEventListener('abort', abort, { once: true })
    })
  },
}

function answer(request: ChatRequest): string {
  const prompt = request.messages.at(-1)?.content ?? ''
  if (prompt.startsWith('/fehler')) return 'Eine Teilantwort bleibt auch bei einem Fehler erhalten.'
  if (prompt.startsWith('/lang')) return Array.from({ length: 35 }, (_, i) => `### Gedanke ${i + 1}\n\nEin langer Verlauf lässt dir Raum zum Lesen. Du kannst nach oben scrollen, während die Antwort weiter entsteht.\n\n`).join('')
  return `Lass uns das gemeinsam durchdenken.\n\nDu fragst: **${prompt.replace(/[\\*_[\]<>`]/g, '')}**\n\n### Ein guter Anfang\n\n1. Kläre das Ziel und die wichtigsten Rahmenbedingungen.\n2. Teile die Aufgabe in überschaubare Schritte.\n3. Prüfe das Ergebnis und passe es bei Bedarf an.\n\n| Schritt | Ergebnis |\n| --- | --- |\n| Verstehen | Eine klare Frage |\n| Umsetzen | Ein erster Entwurf |\n\nEin kleines Beispiel mit Python:\n\n\`\`\`python\ndef greet(name: str) -> str:\n    return f"Hallo, {name}!"\n\nprint(greet("noris"))\n\`\`\`\n\nMehr dazu in der [Python-Dokumentation](https://docs.python.org/3/).\n\n${request.attempt > 1 ? `Das ist ein neuer Blick auf dieselbe Frage (Variante ${request.attempt}).` : 'Welchen Schritt möchtest du als Nächstes vertiefen?'}\n`
}

export function createMockTransport(options: { clock?: MockClock, initialDelay?: number, chunkDelay?: number, chunkSize?: number } = {}): ChatTransport {
  const clock = options.clock ?? browserClock
  const size = Math.max(1, options.chunkSize ?? 24)
  return {
    async *stream(request, signal): AsyncIterable<StreamEvent> {
      let seq = 0
      try {
        await clock.wait(options.initialDelay ?? 450, signal)
        yield { seq: ++seq, type: 'response.started' }
        const response = answer(request)
        for (let offset = 0; offset < response.length; offset += size) {
          await clock.wait(options.chunkDelay ?? 45, signal)
          yield { seq: ++seq, type: 'response.output_text.delta', delta: response.slice(offset, offset + size) }
        }
        if (request.messages.at(-1)?.content.startsWith('/fehler')) {
          yield { seq: ++seq, type: 'response.failed', code: 'MOCK_FAILURE', message: 'Die Antwort konnte nicht abgeschlossen werden. Bitte versuche es erneut.' }
        }
        else yield { seq: ++seq, type: 'response.completed' }
      }
      catch (error) {
        if (!signal.aborted) throw error
        yield { seq: seq + 1, type: 'response.cancelled' }
      }
    },
  }
}
