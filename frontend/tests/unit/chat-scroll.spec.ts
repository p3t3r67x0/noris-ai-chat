import { describe, expect, it } from 'vitest'
import { distanceToBottom, followingAfterScroll } from '../../app/lib/chat/scroll'

describe('scroll decisions', () => {
  it('treats a short turn as the bottom and clamps overscroll', () => {
    expect(distanceToBottom({ top: 0, height: 400, viewport: 600 })).toBe(0)
    expect(distanceToBottom({ top: 1400, height: 1800, viewport: 600 })).toBe(0)
  })
  it('measures remaining distance for a long conversation', () => {
    expect(distanceToBottom({ top: 3000, height: 5000, viewport: 600 })).toBe(1400)
  })
  it('pauses as soon as the reader scrolls up, even near the end', () => {
    expect(followingAfterScroll(true, 1200, 1180, 20)).toBe(false)
  })
  it('keeps a paused reader stationary while streaming increases the height', () => {
    expect(followingAfterScroll(false, 500, 500, 1500)).toBe(false)
    expect(followingAfterScroll(false, 500, 700, 1300)).toBe(false)
  })
  it('resumes when the reader scrolls down to the end', () => {
    expect(followingAfterScroll(false, 500, 1800, 0)).toBe(true)
    expect(followingAfterScroll(false, 500, 1780, 20)).toBe(true)
  })
  it('preserves follow during programmatic movement and ignores subpixel jitter', () => {
    expect(followingAfterScroll(true, 1800, 1800, 0)).toBe(true)
    expect(followingAfterScroll(true, 1800, 1799.5, 0.5)).toBe(true)
  })
})
