import type { ApiSchemas } from '../../types/generated/api'

export interface SelectionSnapshot {
  reference: ApiSchemas['TextReference']
  range: Range
}
const excluded = 'input, textarea, select, button, [contenteditable]:not([contenteditable="false"]), [role="dialog"], [role="menu"], [inert]'
function element(node: Node | null): Element | null { return node instanceof Element ? node : node?.parentElement ?? null }

export function chatSelection(selection: Selection | null, scroller: HTMLElement, conversationId: string): SelectionSnapshot | null {
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1 || !selection.toString().trim()) return null
  const range = selection.getRangeAt(0)
  const start = element(range.startContainer), end = element(range.endContainer)
  const content = start?.closest('[data-selectable-message]')
  if (!content || content !== end?.closest('[data-selectable-message]') || !scroller.contains(content) || start?.closest(excluded) || end?.closest(excluded)) return null
  const messageId = content.closest('[data-message-id]')?.getAttribute('data-message-id')
  if (!messageId) return null
  return { range: range.cloneRange(), reference: { sourceMessageId: messageId, sourceConversationId: conversationId, text: selection.toString() } }
}

export interface SelectionRect { left: number, right: number, top: number, bottom: number }
/** Anchor on the first visible line, with visual-viewport and scroll clipping. */
export function selectionPosition(rects: readonly SelectionRect[], viewport: SelectionRect, clip: SelectionRect, width: number, height: number): { left: number, top: number } | null {
  const visible = rects.find(rect => rect.right > rect.left && rect.bottom > rect.top && rect.bottom > Math.max(viewport.top, clip.top) && rect.top < Math.min(viewport.bottom, clip.bottom) && rect.right > Math.max(viewport.left, clip.left) && rect.left < Math.min(viewport.right, clip.right))
  if (!visible) return null
  const gap = 8
  const left = Math.max(viewport.left + gap, Math.min((Math.max(visible.left, clip.left) + Math.min(visible.right, clip.right)) / 2 - width / 2, viewport.right - width - gap))
  const above = Math.max(visible.top, clip.top) - height - gap
  const top = Math.max(viewport.top + gap, Math.min(above >= viewport.top + gap ? above : visible.bottom + gap, viewport.bottom - height - gap))
  return { left, top }
}
