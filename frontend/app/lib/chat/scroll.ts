export interface ScrollGeometry { top: number, height: number, viewport: number }
export function distanceToBottom(geometry: ScrollGeometry): number {
  return Math.max(0, geometry.height - geometry.viewport - geometry.top)
}
export function followingAfterScroll(following: boolean, previous: number, current: number, distance: number, maxTop = Infinity): boolean {
  // Reparsed Markdown can shrink; the browser then clamps the old scroll offset.
  const previousTop = Math.min(previous, Math.max(0, maxTop))
  if (current < previousTop - 1) return false
  if (current > previousTop + 1 && distance <= 64) return true
  return following
}
