import { describe, expect, it } from 'vitest'
import { searchTextParts } from '../../app/lib/chat/searchHighlight'

describe('safe Unicode search highlighting', () => {
  it.each([
    ['Suche SUCHE suche', 'suche', ['Suche', 'SUCHE', 'suche']],
    ['Äpfel A\u0308PFEL', 'äpfel', ['Äpfel', 'A\u0308PFEL']],
    ['İstanbul', 'i', ['İ']],
    ['Σ ς σ', 'σ', ['Σ', 'ς', 'σ']],
    ['ΟΣΟΣ οσος', 'οσοσ', ['ΟΣΟΣ', 'οσος']],
    ['ſuchen Suchen', 'suchen', ['ſuchen', 'Suchen']],
    ['Straße STRASSE', 'strasse', ['Straße', 'STRASSE']],
    ['Docker setup · healthcheck', 'docker healthcheck', ['Docker', 'healthcheck']],
    ['docker healthcheck', 'docker healthcheck', ['docker healthcheck']],
    ['👩🏽‍💻 test', '👩', ['👩🏽‍💻']],
    ['<img src=x onerror=alert(1)> [a+b]', '[a+b]', ['[a+b]']],
    ['abc', ' ', []],
    ['abc', 'z', []],
  ])('preserves original text and glyphs in %s', (text, query, expected) => {
    const parts = searchTextParts(text, query)
    expect(parts.map(part => part.text).join('')).toBe(text)
    expect(parts.filter(part => part.matched).map(part => part.text)).toEqual(expected)
  })
})
