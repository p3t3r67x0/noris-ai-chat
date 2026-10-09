import { defineComponent, h } from 'vue'
import type { VNode } from 'vue'
import MarkdownIt from 'markdown-it'
import CodeBlock from './CodeBlock.vue'

const markdown = new MarkdownIt({ html: false, linkify: false, breaks: false, typographer: false })
type Token = ReturnType<typeof markdown.parse>[number]
const tags = new Set(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'strong', 'em', 's', 'a', 'hr'])

export function safeMarkdownHref(value: string): string | undefined {
  try {
    const url = new URL(value, 'https://noris.invalid')
    if (['https:', 'http:', 'mailto:'].includes(url.protocol)) return value
  }
  catch { return undefined }
  return undefined
}

function renderTokens(tokens: readonly Token[]): (VNode | string)[] {
  let index = 0
  function children(): (VNode | string)[] {
    const nodes: (VNode | string)[] = []
    while (index < tokens.length) {
      const token = tokens[index++]
      if (!token) break
      if (token.nesting === -1) break
      const key = index
      if (token.type === 'inline') nodes.push(...renderTokens(token.children ?? []))
      else if (token.type === 'text') nodes.push(token.content)
      else if (token.type === 'code_inline') nodes.push(h('code', { key }, token.content))
      else if (token.type === 'softbreak') nodes.push('\n')
      else if (token.type === 'hardbreak') nodes.push(h('br', { key }))
      else if (token.type === 'fence' || token.type === 'code_block') nodes.push(h(CodeBlock, { key, code: token.content, language: token.info.trim().split(/\s+/)[0] ?? '' }))
      else if (token.type === 'image') nodes.push(h('span', { key, class: 'text-muted' }, token.content || '[Bild]'))
      else {
        const tag = tags.has(token.tag) ? token.tag : 'span'
        const attributes: Record<string, string | number | undefined> = { key }
        if (tag === 'a') {
          attributes.href = safeMarkdownHref(String(token.attrGet('href') ?? ''))
          attributes.rel = 'noopener noreferrer'
          attributes.target = '_blank'
        }
        if (tag === 'ol') {
          const start = Number(token.attrGet('start') ?? 1)
          if (Number.isSafeInteger(start) && start > 0) attributes.start = start
        }
        const content = token.nesting === 1 ? children() : token.content
        const node = h(tag, attributes, content)
        nodes.push(tag === 'table' ? h('div', { key, class: 'markdown-table' }, [node]) : node)
      }
    }
    return nodes
  }
  return children()
}

export default defineComponent({
  name: 'MarkdownContent',
  props: { content: { type: String, required: true } },
  setup: props => () => h('div', { class: 'markdown-content' }, renderTokens(markdown.parse(props.content, {}))),
})
