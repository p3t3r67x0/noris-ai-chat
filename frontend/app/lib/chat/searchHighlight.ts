export interface SearchTextPart { text: string, matched: boolean }

// Keep an offset map per grapheme: case conversion and Unicode normalization
// can change string length (e.g. İ and decomposed accents). Never split a glyph.
export function searchTextParts(text: string, query: string): SearchTextPart[] {
  const needle = query.trim().normalize('NFC').toLowerCase()
  if (!needle) return [{ text, matched: false }]
  let folded = ''
  const offsets: { start: number, end: number }[] = []
  for (const { segment, index } of new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(text)) {
    const normalized = segment.normalize('NFC').toLowerCase()
    folded += normalized
    for (let i = 0; i < normalized.length; i++) offsets.push({ start: index, end: index + segment.length })
  }
  if (needle.length > folded.length) return [{ text, matched: false }]
  // Unicode ignore-case also recognizes alternative lowercase forms such as
  // Greek sigma (σ/ς) and long s (ſ). Escape the query so it stays literal.
  const matcher = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'giu')
  const parts: SearchTextPart[] = []
  let source = 0, match: RegExpExecArray | null
  while ((match = matcher.exec(folded)) !== null) {
    const start = offsets[match.index]!.start, end = offsets[match.index + match[0].length - 1]!.end
    if (start >= source) {
      if (start > source) parts.push({ text: text.slice(source, start), matched: false })
      parts.push({ text: text.slice(start, end), matched: true })
      source = end
    }
  }
  if (source < text.length) parts.push({ text: text.slice(source), matched: false })
  return parts
}
