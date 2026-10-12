<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { useChatBackend } from '../../composables/useChatBackend'
import { useConversationSearch } from '../../composables/useConversationSearch'
import { useChatViewport } from '../../composables/useChatViewport'
import { useAppLocale } from '../../composables/useAppLocale'
import type { Conversation } from '../../lib/chat/conversations'
import { compareConversations } from '../../lib/chat/conversations'
import { useAppNotifications } from '../../composables/useAppNotifications'

const props = defineProps<{
  conversations: readonly Conversation[]
  pagination?: ReturnType<typeof useChatBackend>['pagination'] | undefined
  returnFocus?: HTMLElement | null
}>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ select: [id: string] }>()
const { query, results, loading, error, diagnostics, cursor, search } = useConversationSearch(open, () => props.conversations, () => props.pagination)
const notifications = useAppNotifications()
const { viewportStyle } = useChatViewport()
const { t } = useAppLocale()
const selected = ref(false)
const selectionVisible = ref(false)
let focusRevision = 0
watch(query, () => { selectionVisible.value = false }, { flush: 'sync' })
// UCommandPalette forwards this object to UInput, including native attributes.
const input = computed(() => ({
  id: 'chat-search-input', 'aria-label': t('searchChats'), role: 'combobox',
  'aria-expanded': true, 'aria-controls': 'chat-search-listbox', 'aria-autocomplete': 'list',
  ui: { root: () => 'chat-search-input', base: () => 'chat-search-input-base', trailing: () => 'chat-search-input-trailing' },
}))

function select(id: string): void {
  selected.value = true
  open.value = false
  emit('select', id)
}

const groups = computed(() => [{
  id: 'recent-chats', label: t('recentChats'), ignoreFilter: Boolean(props.pagination),
  items: [...(props.pagination ? results.value : props.conversations)].sort(compareConversations).map(conversation => ({
    id: conversation.id, label: conversation.title, icon: 'i-lucide-message-circle', onSelect: () => select(conversation.id),
  })),
}])

function initialFocus(event: Event): void {
  event.preventDefault()
  focusRevision++
  selected.value = false
  selectionVisible.value = false
  // This version of the palette exposes no content-ID prop. Label the native
  // Reka listbox so the input's controls relationship targets the actual popup.
  const listbox = document.querySelector<HTMLElement>('.chat-search-dialog [role="listbox"]')
  listbox?.setAttribute('id', 'chat-search-listbox')
  listbox?.setAttribute('aria-label', t('recentChats'))
  document.querySelector<HTMLInputElement>('#chat-search-input')?.focus({ preventScroll: true })
}

function revealKeyboardSelection(event: KeyboardEvent): void {
  if (!event.isComposing && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) selectionVisible.value = true
}

function revealPointerSelection(event: PointerEvent): void {
  if ((event.target as HTMLElement).closest('[role="option"]')) selectionVisible.value = true
}

function restoreFocus(event: Event): void {
  event.preventDefault()
  const revision = focusRevision
  const chosen = selected.value
  const trigger = props.returnFocus
  // Reka dispatches closeAutoFocus before releasing its focus scope. Wait for
  // that cleanup and the conversation render, so neither can take focus back.
  void nextTick(() => requestAnimationFrame(() => {
    if (open.value || revision !== focusRevision) return
    if (!chosen && trigger?.isConnected && !trigger.closest('[inert], [role="dialog"][data-state="closed"]') && trigger.getClientRects().length) trigger.focus({ preventScroll: true })
    else (document.querySelector<HTMLElement>('.composer-input') ?? document.querySelector<HTMLElement>('#chat-main'))?.focus({ preventScroll: true })
  }))
}

const content = computed(() => ({
  'aria-modal': true, style: viewportStyle.value,
  onOpenAutoFocus: initialFocus, onCloseAutoFocus: restoreFocus,
}))
</script>

<template>
  <UModal
    v-model:open="open" :title="t('searchChats')" :transition="false" :content="content"
    :ui="{ overlay: () => 'chat-search-overlay', content: () => 'chat-search-dialog' }"
  >
    <!-- UModal's content slot keeps DialogTitle visually hidden. Reka owns the
         focus trap, dismissal, list navigation and active descendant. -->
    <template #content>
      <UCommandPalette
        v-model:search-term="query" :groups="groups" :icon="false" :autofocus="false" :data-selection-visible="selectionVisible"
        :fuse="{ resultLimit: Number.MAX_SAFE_INTEGER }" :placeholder="t('searchPlaceholder')"
        :input="input"
        :ui="{
          root: () => 'chat-search-palette', input: () => 'chat-search-input',
          content: () => 'chat-search-content', viewport: () => 'chat-search-viewport',
          group: () => 'chat-search-group', label: () => 'chat-search-label',
          item: () => 'chat-search-row', itemLeadingIcon: () => 'chat-search-icon',
          itemWrapper: () => 'chat-search-row-copy', itemLabel: () => 'chat-search-row-title',
          empty: () => 'chat-search-empty', footer: () => 'chat-search-footer',
        }"
        @keydown="revealKeyboardSelection" @pointermove="revealPointerSelection"
      >
        <template #close>
          <span class="chat-search-loading" aria-hidden="true">
            <UIcon v-if="loading" name="i-lucide-loader-circle" class="size-4 motion-safe:animate-spin" />
          </span>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" :aria-label="t('closeSearch')" class="chat-search-close" @click="open = false" />
        </template>
        <template #item-label="{ item }"><span :title="item.label">{{ item.label }}</span></template>
        <template #empty>
          <p class="chat-search-label">{{ t('recentChats') }}</p>
          <p v-if="!loading && !error" role="status" class="chat-search-message">{{ t('noChats') }}</p>
        </template>
        <template #footer>
          <p role="status" aria-live="polite" class="sr-only">{{ loading ? t('searchLoading') : t('searchReady') }}</p>
          <p v-if="error" role="alert" class="chat-search-message">
            {{ error }}
            <UButton color="neutral" variant="ghost" :label="t('retrySearch')" class="min-h-11" @click="search(Boolean(cursor))" />
            <UButton v-if="diagnostics && notifications" color="neutral" variant="link" label="Details" @click="notifications.details.value = diagnostics" />
          </p>
          <UButton v-if="cursor" color="neutral" variant="ghost" :label="t('moreChats')" :loading="loading" :disabled="loading" class="min-h-11" @click="search(true)" />
        </template>
      </UCommandPalette>
    </template>
  </UModal>
</template>

<style>
.chat-search-overlay { position: fixed; inset: 0; z-index: 60; background: rgb(0 0 0 / 4%); }
.dark .chat-search-overlay { background: rgb(0 0 0 / 24%); }
.chat-search-dialog {
  position: fixed;
  z-index: 70;
  left: 50%;
  top: calc(var(--chat-viewport-offset, 0px) + var(--chat-viewport-height, 100dvh) / 2 - 1rem);
  transform: translate(-50%, -50%);
  display: flex;
  width: min(830px, calc(100vw - 32px));
  height: min(530px, calc(var(--chat-viewport-height, 100dvh) - 64px));
  min-height: min(530px, calc(var(--chat-viewport-height, 100dvh) - 64px));
  max-height: calc(var(--chat-viewport-height, 100dvh) - 32px);
  overflow: hidden;
  border: 1px solid var(--noris-border);
  border-radius: 18px;
  background: var(--noris-composer-background);
  color: var(--noris-text-primary);
  box-shadow: 0 20px 40px rgb(0 0 0 / 14%);
  outline: none;
}
.chat-search-palette { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; }
.chat-search-input { position: relative; flex-shrink: 0; width: 100%; }
.chat-search-input-base { width: 100%; height: 76px; padding: 0 100px 0 28px; border: 0; border-radius: 0; background: transparent; box-shadow: none; color: inherit; font-size: 20px; outline: none; }
.chat-search-input-base::placeholder { color: var(--noris-text-secondary); opacity: 1; }
.chat-search-input-base:focus-visible { outline: none; }
.chat-search-input-trailing { position: absolute; inset-block: 0; right: 16px; display: flex; align-items: center; gap: 8px; }
.chat-search-loading { display: flex; width: 16px; color: var(--noris-text-secondary); }
.chat-search-close { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; padding: 12px; border-radius: 12px; color: var(--noris-text-secondary); }
.chat-search-content { display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; }
.chat-search-viewport { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; overscroll-behavior: contain; padding: 0 16px 16px; scroll-padding-block: 12px; }
.chat-search-label { margin: 0; padding: 12px 12px 14px; color: var(--noris-text-secondary); font-size: 16px; font-weight: 400; line-height: 24px; }
.chat-search-row { display: flex; align-items: center; gap: 24px; width: 100%; min-width: 0; height: 56px; padding: 0 20px; border: 0; border-radius: 12px; font-size: 18px; line-height: 24px; text-align: left; cursor: pointer; outline: none; }
.chat-search-palette[data-selection-visible="true"] .chat-search-row[data-highlighted] { background: var(--noris-active-background); }
.chat-search-row:focus-visible { outline: 2px solid var(--noris-text-primary); outline-offset: -2px; }
.chat-search-icon { flex-shrink: 0; width: 20px; height: 20px; }
.chat-search-row-copy { flex: 1; min-width: 0; }
.chat-search-row-title { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.chat-search-empty { padding-inline: 16px; }
.chat-search-message { margin: 0; padding: 12px; color: var(--noris-text-secondary); font-size: 14px; }
.chat-search-footer { flex-shrink: 0; padding-inline: 28px; }
.chat-search-footer:has(> button), .chat-search-footer:has(> [role="alert"]) { padding-bottom: 12px; }
@media (max-width: 639px) {
  .chat-search-dialog { top: calc(var(--chat-viewport-offset, 0px) + var(--chat-viewport-height, 100dvh) / 2); height: min(530px, calc(var(--chat-viewport-height, 100dvh) - 32px)); min-height: min(530px, calc(var(--chat-viewport-height, 100dvh) - 32px)); }
  .chat-search-input-base { font-size: 18px; padding-left: 20px; }
  .chat-search-viewport, .chat-search-empty { padding-inline: 8px; }
  .chat-search-row { gap: 16px; padding-inline: 12px; font-size: 16px; }
  .chat-search-footer { padding-inline: 20px; }
}
</style>
