import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownContent, { safeMarkdownHref } from '../../app/components/chat/MarkdownContent'
import { fiveColumnTable, longIdentifier, longUrl, overflowMarkdown, strengthTable } from '../fixtures/markdown'

describe('safe Markdown presentation', () => {
  it('preserves all table cells, long links and inline code without scroll wrappers', () => {
    const wrapper = mount(MarkdownContent, { props: { content: overflowMarkdown }, global: { stubs: { CodeBlock: true } } })
    const tables = wrapper.findAll('table')
    expect(tables).toHaveLength(2)
    expect(tables[0]!.findAll('th').map(cell => cell.text())).toEqual(['Stärke', 'Bedeutung'])
    expect(tables[0]!.findAll('td')).toHaveLength(4)
    expect(tables[1]!.findAll('th')).toHaveLength(5)
    expect(tables[1]!.findAll('td')).toHaveLength(10)
    expect(tables[1]!.find('a').attributes('href')).toBe(longUrl)
    expect(tables[1]!.find('a').text()).toBe(longUrl)
    expect(tables[1]!.find('code').text()).toBe(longIdentifier)
    for (const container of wrapper.findAll('.markdown-table')) expect(container.attributes('tabindex')).toBeUndefined()
    expect(wrapper.find('ul ul ul').exists()).toBe(true)
    wrapper.unmount()
  })
  it('renders incomplete streamed tables and keeps completed cells intact', async () => {
    const content = `${strengthTable}\n\n${fiveColumnTable}`
    const wrapper = mount(MarkdownContent, { props: { content: '' }, global: { stubs: { CodeBlock: true } } })
    for (let offset = 1; offset < content.length; offset += 37) {
      await wrapper.setProps({ content: content.slice(0, offset) })
      expect(wrapper.find('.markdown-content').exists()).toBe(true)
      expect(wrapper.find('script').exists()).toBe(false)
    }
    await wrapper.setProps({ content })
    expect(wrapper.findAll('table')).toHaveLength(2)
    expect(wrapper.findAll('td')).toHaveLength(14)
    expect(wrapper.findAll('table')[1]!.find('code').text()).toBe(longIdentifier)
    wrapper.unmount()
  })
  it('renders headings, lists, tables, inline code and safe external links', () => {
    const wrapper = mount(MarkdownContent, { props: { content: '# Titel\n\n- Punkt\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n`code` und [Link](https://example.com)' }, global: { stubs: { CodeBlock: true } } })
    expect(wrapper.get('h1').text()).toBe('Titel')
    expect(wrapper.get('li').text()).toBe('Punkt')
    expect(wrapper.findAll('td')).toHaveLength(2)
    expect(wrapper.get('code').text()).toBe('code')
    expect(wrapper.get('a').attributes('rel')).toBe('noopener noreferrer')
    expect(wrapper.get('a').attributes('target')).toBe('_blank')
    wrapper.unmount()
  })
  it('renders malicious HTML as text and rejects executable protocols', () => {
    const wrapper = mount(MarkdownContent, { props: { content: '<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))\n[bad](data:text/html,test)' }, global: { stubs: { CodeBlock: true } } })
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.text()).toContain('<script>')
    for (const url of ['javascript:alert(1)', 'data:text/html,test', 'vbscript:evil', 'file:///etc/passwd']) expect(safeMarkdownHref(url)).toBeUndefined()
    wrapper.unmount()
  })
  it('keeps code contents as component text and disables remote Markdown images', () => {
    const wrapper = mount(MarkdownContent, { props: { content: '```html\n<script>alert(1)</script>\n```\n\n![Tracking](https://example.com/pixel)' }, global: { stubs: { CodeBlock: true } } })
    expect(wrapper.getComponent({ name: 'CodeBlock' }).props('code')).toContain('<script>')
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    wrapper.unmount()
  })
})
