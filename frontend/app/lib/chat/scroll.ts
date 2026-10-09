export interface ScrollGeometry { top: number, height: number, viewport: number }
export function distanceToBottom(geometry: ScrollGeometry): number {
  return Math.max(0, geometry.height - geometry.viewport - geometry.top)
}
export function followingAfterScroll(following: boolean, previous: number, current: number, distance: number): boolean {
  if (current < previous - 1) return false
  if (current > previous + 1 && distance <= 64) return true
  return following
}
