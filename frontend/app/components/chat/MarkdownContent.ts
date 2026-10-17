import { computed, defineComponent, h, onUnmounted, shallowRef, watch } from 'vue'
import type { PropType, VNode } from 'vue'
import MarkdownIt from 'markdown-it'
import CodeBlock from './CodeBlock.vue'
import { citationPlaceholders } from '../../lib/chat/research'
import type { ResearchView } from '../../lib/chat/types'
import { useAppLocale } from '../../composables/useAppLocale'

const markdown = new MarkdownIt({ html: false, linkify: false, breaks: false, typographer: false })
type CitationEnvironment = ReturnType<typeof citationPlaceholders>
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

function renderCitationText(value: string, environment: CitationEnvironment, citation: (marker: string, event: MouseEvent) => void, label: string, inLink: boolean): (VNode | string)[] {
  if (!environment.replacements.size) return [value]
  const nodes: (VNode | string)[] = []
  let previous = 0
  for (const match of value.matchAll(new RegExp(`${environment.prefix}\\d+\uE001`, 'g'))) {
    const original = environment.replacements.get(match[0])
    if (!original) continue
    nodes.push(value.slice(previous, match.index))
    const marker = original.slice(2, -2)
    nodes.push(inLink ? original : h('button', { key: match.index, type: 'button', class: 'research-citation', 'aria-label': `${label} ${marker.slice(1)}`, onClick: (event: MouseEvent) => citation(marker, event) }, `[${marker.slice(1)}]`))
    previous = match.index + match[0].length
  }
  nodes.push(value.slice(previous))
  return nodes
}

function renderTokens(tokens: readonly Token[], environment: CitationEnvironment, citation: (marker: string, event: MouseEvent) => void, label: string, inLink = false): (VNode | string)[] {
  let index = 0
  function children(link = inLink): (VNode | string)[] {
    const nodes: (VNode | string)[] = []
    while (index < tokens.length) {
      const token = tokens[index++]
      if (!token) break
      if (token.nesting === -1) break
      const key = index
      if (token.hidden && token.nesting === 1) nodes.push(...children(link))
      else if (token.type === 'inline') nodes.push(...renderTokens(token.children ?? [], environment, citation, label, link))
      else if (token.type === 'text') nodes.push(...renderCitationText(token.content, environment, citation, label, link))
      else if (token.type === 'code_inline') nodes.push(h('code', { key }, environment.restore(token.content)))
      else if (token.type === 'softbreak') nodes.push('\n')
      else if (token.type === 'hardbreak') nodes.push(h('br', { key }))
      else if (token.type === 'fence' || token.type === 'code_block') nodes.push(h(CodeBlock, { key, code: environment.restore(token.content), language: environment.restore(token.info).trim().split(/\s+/)[0] ?? '' }))
      else if (token.type === 'image') nodes.push(h('span', { key, class: 'text-muted' }, environment.restore(token.content) || '[Bild]'))
      else {
        const tag = tags.has(token.tag) ? token.tag : 'span'
        const attributes: Record<string, string | number | undefined> = { key }
        if (tag === 'a') {
          attributes.href = safeMarkdownHref(environment.restore(String(token.attrGet('href') ?? '')))
          attributes.rel = 'noopener noreferrer'
          attributes.target = '_blank'
        }
        if (tag === 'ol') {
          const start = Number(token.attrGet('start') ?? 1)
          if (Number.isSafeInteger(start) && start > 0) attributes.start = start
        }
        const content = token.nesting === 1 ? children(link || tag === 'a') : environment.restore(token.content)
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
  props: { content: { type: String, required: true }, streaming: { type: Boolean, default: false }, citations: { type: Array as PropType<ResearchView['citations']>, default: () => [] } },
  emits: ['rendered', 'citation'],
  setup(props, { emit }) {
    const { t } = useAppLocale()
    const rendered = shallowRef(props.content)
    let timer: ReturnType<typeof setTimeout> | undefined
    watch(() => [props.content, props.streaming], () => {
      if (!props.streaming) {
        clearTimeout(timer); timer = undefined
        rendered.value = props.content
      }
      else timer ??= setTimeout(() => { timer = undefined; rendered.value = props.content }, 50)
    })
    const nodes = computed(() => {
      const environment = citationPlaceholders(rendered.value, props.citations)
      return renderTokens(markdown.parse(environment.content, environment), environment, (marker, event) => emit('citation', marker, event), t('researchOpenSource'))
    })
    watch(rendered, () => emit('rendered'), { flush: 'post' })
    onUnmounted(() => clearTimeout(timer))
    return () => h('div', { class: 'markdown-content' }, nodes.value)
  },
})
