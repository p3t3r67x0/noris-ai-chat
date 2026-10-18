<script setup lang="ts">
import { nextTick, watch } from 'vue'
import { useAppLocale } from '../../composables/useAppLocale'
import type { SlashChoice } from '../../composables/useSlashCommands'
import type { ChatCommand } from '../../lib/chat/commands'

const props = defineProps<{ anchor: HTMLElement | null, input?: HTMLTextAreaElement | undefined, items: ChatCommand[], choices: SlashChoice[], models: boolean, active: number, listId: string, help: boolean }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ select: [command: ChatCommand], model: [choice: SlashChoice], active: [index: number], close: [] }>()
const { t } = useAppLocale()
function preventFocus(event: Event): void { event.preventDefault() }
function focusOutside(event: Event): void {
  const target = (event as CustomEvent<{ originalEvent: FocusEvent }>).detail?.originalEvent.target
  if (target === props.input) event.preventDefault()
}
function pointerOutside(event: Event): void {
  const target = (event as CustomEvent<{ originalEvent: PointerEvent }>).detail?.originalEvent.target
  if (target === props.input) event.preventDefault()
}
watch(() => props.active, () => nextTick(() => {
  document.getElementById(`${props.listId}-${(props.models ? props.choices : props.items)[props.active]?.id}`)?.scrollIntoView({ block: 'nearest' })
}))
</script>

<template>
  <UPopover v-model:open="open" :modal="false" :reference="anchor ?? undefined" :content="{ side: 'top', align: 'start', sideOffset: 10, collisionPadding: 12, updatePositionStrategy: 'always', onOpenAutoFocus: preventFocus, onCloseAutoFocus: preventFocus, onFocusOutside: focusOutside, onPointerDownOutside: pointerOutside, onEscapeKeyDown: () => emit('close') }" :ui="{ content: 'composer-floating-menu composer-slash-menu' }">
    <template #content>
      <p class="command-menu-heading">{{ t(models ? 'chooseModel' : help ? 'commandHelp' : 'slashCommands') }}</p>
      <div :id="listId" role="listbox" :aria-label="t(models ? 'chooseModel' : 'slashCommands')">
        <template v-if="models">
          <template v-for="(entry, index) in choices" :key="entry.id">
          <p v-if="entry.group && entry.group !== choices[index - 1]?.group" class="command-menu-heading">{{ entry.group }}</p>
          <button :id="`${listId}-${entry.id}`" type="button" role="option" :aria-label="entry.label" :aria-description="entry.description" :aria-selected="entry.checked" :aria-disabled="entry.disabled || undefined" :data-active="index === active" tabindex="-1" class="command-menu-option" @pointermove="emit('active', index)" @mousedown.prevent @click="emit('model', entry)">
            <UIcon name="i-lucide-box" class="size-5 shrink-0" aria-hidden="true" />
            <span class="command-menu-copy"><span class="command-menu-label">{{ entry.label }}</span><span class="command-menu-description">{{ entry.description }}</span></span>
            <UIcon v-if="entry.checked" name="i-lucide-check" class="model-choice-check size-5 shrink-0" aria-hidden="true" />
          </button>
          </template>
        </template>
        <template v-else>
        <button v-for="(entry, index) in items" :id="`${listId}-${entry.id}`" :key="entry.id" type="button" role="option" :aria-selected="index === active" tabindex="-1" class="command-menu-option" @pointermove="emit('active', index)" @mousedown.prevent @click="emit('select', entry)">
          <UIcon :name="entry.icon" class="size-5 shrink-0" aria-hidden="true" />
          <span class="command-menu-copy"><span class="command-menu-label">{{ t(entry.label) }} <span class="command-menu-name">/{{ entry.name }}</span></span><span class="command-menu-description">{{ t(entry.description) }}</span></span>
        </button>
        </template>
      </div>
      <p v-if="models ? !choices.length : !items.length" role="status" class="command-menu-heading">{{ t('noCommands') }}</p>
      <p v-if="models && choices.some(choice => choice.virtual)" class="command-menu-hint">Bei „Automatisch“ kann das tatsächliche Modell je nach Anfrage wechseln.</p>
      <p class="command-menu-hint">{{ t('commandKeys') }}</p>
    </template>
  </UPopover>
</template>
