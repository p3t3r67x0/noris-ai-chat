/** Coordinates reads; rendered records continue to belong to useChat. */
export class ChatLoadCache {
  private entries = new Map<string, { version: number, time: number }>()
  private pending = new Map<string, Promise<unknown>>()
  constructor(readonly maximum = 10, readonly ttl = 30_000, readonly now = () => Date.now()) {}
  valid(id: string, version: number): boolean {
    const entry = this.entries.get(id)
    if (!entry || entry.version !== version || this.now() - entry.time > this.ttl) return false
    this.entries.delete(id); this.entries.set(id, entry)
    return true
  }
  touch(id: string, version: number): void {
    this.entries.delete(id); this.entries.set(id, { version, time: this.now() })
  }
  invalidate(id: string): void { this.entries.delete(id) }
  cancelRead(id: string): void { this.pending.delete(id) }
  evictions(pinned: ReadonlySet<string>): string[] {
    const evicted: string[] = []
    for (const id of this.entries.keys()) {
      if (this.entries.size <= this.maximum) break
      if (pinned.has(id) || this.pending.has(id)) continue
      this.entries.delete(id); evicted.push(id)
    }
    return evicted
  }
  read<T>(id: string, operation: () => Promise<T>): Promise<T> {
    const existing = this.pending.get(id)
    if (existing) return existing as Promise<T>
    const request = Promise.resolve().then(operation).finally(() => { if (this.pending.get(id) === request) this.pending.delete(id) })
    this.pending.set(id, request)
    return request
  }
}
