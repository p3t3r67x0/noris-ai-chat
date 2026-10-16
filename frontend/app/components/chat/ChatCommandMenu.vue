<script setup lang="ts">
import { nextTick, watch } from 'vue'
import { useAppLocale } from '../../composables/useAppLocale'
import type { ChatCommand } from '../../lib/chat/commands'

const props = defineProps<{ anchor: HTMLElement | null, input?: HTMLTextAreaElement | undefined, items: ChatCommand[], active: number, listId: string, help: boolean }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ select: [command: ChatCommand], active: [index: number], close: [] }>()
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
  document.getElementById(`${props.listId}-${props.items[props.active]?.id}`)?.scrollIntoView({ block: 'nearest' })
}))
</script>

<template>
  <UPopover v-model:open="open" :modal="false" :reference="anchor ?? undefined" :content="{ side: 'top', align: 'start', sideOffset: 10, collisionPadding: 12, updatePositionStrategy: 'always', onOpenAutoFocus: preventFocus, onCloseAutoFocus: preventFocus, onFocusOutside: focusOutside, onPointerDownOutside: pointerOutside, onEscapeKeyDown: () => emit('close') }" :ui="{ content: 'composer-floating-menu composer-slash-menu' }">
    <template #content>
      <p class="command-menu-heading">{{ t(help ? 'commandHelp' : 'slashCommands') }}</p>
      <div :id="listId" role="listbox" :aria-label="t('slashCommands')">
        <button v-for="(entry, index) in items" :id="`${listId}-${entry.id}`" :key="entry.id" type="button" role="option" :aria-selected="index === active" tabindex="-1" class="command-menu-option" @pointermove="emit('active', index)" @mousedown.prevent @click="emit('select', entry)">
          <UIcon :name="entry.icon" class="size-5 shrink-0" aria-hidden="true" />
          <span class="command-menu-copy"><span class="command-menu-label">{{ t(entry.label) }} <span class="command-menu-name">/{{ entry.name }}</span></span><span class="command-menu-description">{{ t(entry.description) }}</span></span>
        </button>
      </div>
      <p v-if="!items.length" role="status" class="command-menu-heading">{{ t('noCommands') }}</p>
      <p class="command-menu-hint">{{ t('commandKeys') }}</p>
    </template>
  </UPopover>
</template>
