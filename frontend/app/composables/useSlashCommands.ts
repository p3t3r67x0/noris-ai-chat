import { computed, nextTick, ref, useId, watch } from 'vue'
import type { Ref } from 'vue'
import type { ChatCommand, CommandContext, CommandToken } from '../lib/chat/commands'
import { commandToken, findCommand, leadingCommand, matchingCommands } from '../lib/chat/commands'

export interface SlashChoice { id: string, label: string, description: string, group?: string, virtual?: boolean, disabled?: boolean, checked?: boolean }
interface ModelChoices { items: Ref<SlashChoice[]>, available: () => boolean, select: (id: string) => void }

export function useSlashCommands(text: Ref<string>, context: Ref<CommandContext>, input: () => HTMLTextAreaElement | undefined, conversation: () => string | null | undefined, models?: ModelChoices) {
  const open = ref(false)
  const token = ref<CommandToken | null>(null)
  const help = ref(false)
  const modelView = ref(false)
  const active = ref(0)
  const unavailable = ref(false)
  const composing = ref(false)
  let compositionEndedAt = -Infinity
  const listId = useId()
  const items = computed(() => matchingCommands(help.value ? '' : token.value?.query ?? '', context.value))
  const choices = computed(() => modelView.value ? models?.items.value ?? [] : items.value)
  const activeId = computed(() => open.value && choices.value[active.value] ? `${listId}-${choices.value[active.value]!.id}` : undefined)
  function focus(): void { input()?.focus({ preventScroll: true }) }
  function close(): void { open.value = false; token.value = null; help.value = false; modelView.value = false }
  function showModels(): void {
    if (!models?.available()) return
    modelView.value = true; help.value = false; token.value = null; active.value = 0; open.value = true
    void nextTick(focus)
  }
  function chooseModel(choice: SlashChoice): void {
    // A catalog refresh or generation can revoke availability while open.
    const current = models?.items.value.find(item => item.id === choice.id)
    if (!models?.available() || !current || current.disabled) { unavailable.value = true; return }
    models.select(current.id); unavailable.value = false; close(); focus()
  }
  function update(): void {
    if (composing.value) return
    modelView.value = false
    const element = input()
    const next = element && element.selectionStart === element.selectionEnd ? commandToken(element.value, element.selectionStart) : null
    if (next?.query !== token.value?.query || next?.start !== token.value?.start) active.value = 0
    token.value = next
    help.value = false
    unavailable.value = false
    open.value = Boolean(next)
  }
  function showHelp(): void { help.value = true; open.value = true; active.value = 0; void nextTick(focus) }
  function execute(entry: ChatCommand, range = token.value): boolean {
    // Recheck current permissions after selection, including a refreshed model catalog.
    if (!entry.available(context.value)) { unavailable.value = true; close(); return false }
    if (range) {
      const current = commandToken(text.value, range.end)
      if (!current || current.start !== range.start || current.query !== range.query.toLocaleLowerCase()) { close(); return false }
      text.value = text.value.slice(0, range.start) + text.value.slice(range.end)
      void nextTick(() => input()?.setSelectionRange(range.start, range.start))
    }
    close()
    unavailable.value = false
    return entry.execute(context.value)
  }
  function guardSubmit(): boolean {
    if (composing.value || performance.now() - compositionEndedAt < 50) return true
    if (open.value) {
      if (modelView.value) { const entry = choices.value[active.value] as SlashChoice | undefined; if (entry) chooseModel(entry); return true }
      const entry = items.value[active.value] ?? (token.value ? findCommand(token.value.query) : undefined)
      if (entry) { execute(entry); return true }
      close()
    }
    const current = commandToken(text.value, input()?.selectionStart ?? text.value.length)
    const atCaret = current && findCommand(current.query)
    if (atCaret) { execute(atCaret, current); return true }
    const command = leadingCommand(text.value)
    if (command) { execute(command.command, command.token); return true }
    return false
  }
  function keydown(event: KeyboardEvent): void {
    if (event.target !== input() || event.isComposing || event.keyCode === 229 || composing.value || performance.now() - compositionEndedAt < 50 || !open.value) return
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', 'Tab', 'Escape'].includes(event.key)) return
    if (event.key === 'Enter' || event.key === 'Tab') {
      if (modelView.value) {
        event.preventDefault(); event.stopPropagation()
        const entry = choices.value[active.value] as SlashChoice | undefined
        if (entry) chooseModel(entry)
        return
      }
      const entry = items.value[active.value] ?? (token.value ? findCommand(token.value.query) : undefined)
      if (!entry) { close(); return } // Unknown tokens remain ordinary chat text.
      event.preventDefault()
      event.stopPropagation()
      execute(entry)
      return
    }
    event.preventDefault()
    event.stopPropagation()
    if (event.key === 'Escape') { close(); focus(); return }
    const count = choices.value.length
    if (!count) return
    active.value = event.key === 'Home' ? 0 : event.key === 'End' ? count - 1 : (active.value + (event.key === 'ArrowUp' ? -1 : 1) + count) % count
  }
  function compositionStart(): void { composing.value = true; close() }
  function compositionEnd(): void { composing.value = false; compositionEndedAt = performance.now(); void nextTick(update) }
  watch(choices, entries => { if (active.value >= entries.length) active.value = 0 })
  watch(text, () => { if (open.value && !help.value && !modelView.value) void nextTick(update) })
  watch(conversation, () => { close(); unavailable.value = false; composing.value = false })
  return { open, token, help, modelView, active, unavailable, items, activeId, listId, close, update, showHelp, showModels, chooseModel, execute, guardSubmit, keydown, compositionStart, compositionEnd }
}
