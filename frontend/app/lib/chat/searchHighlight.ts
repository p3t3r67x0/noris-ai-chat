import { foldSearchText } from './searchCasefold'

export interface SearchTextPart { text: string, matched: boolean }

// Keep an offset map per grapheme: case conversion and Unicode normalization
// can change string length (e.g. İ and decomposed accents). Never split a glyph.
export function searchTextParts(text: string, query: string, phraseOnly = false): SearchTextPart[] {
  const needle = foldSearchText(query).replace(/\p{White_Space}+/gu, ' ').replace(/^ +| +$/g, '')
  if (!needle) return [{ text, matched: false }]
  let folded = ''
  const offsets: { start: number, end: number }[] = []
  for (const { segment, index } of new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(text)) {
    const normalized = foldSearchText(segment)
    folded += normalized
    for (let i = 0; i < normalized.length; i++) offsets.push({ start: index, end: index + segment.length })
  }
  // Highlight an exact phrase first, then individual AND terms. All text stays
  // literal; the offset map retains original graphemes after casefold expansion.
  const needles = phraseOnly ? [needle] : [...new Set([needle, ...needle.split(' ')])].sort((a, b) => b.length - a.length)
  const matcher = new RegExp(needles.map(value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'gu')
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
