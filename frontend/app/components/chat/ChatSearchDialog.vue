<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { useChatBackend } from '../../composables/useChatBackend'
import { useConversationSearch } from '../../composables/useConversationSearch'
import { useChatViewport } from '../../composables/useChatViewport'
import { useAppLocale } from '../../composables/useAppLocale'
import type { ChatMessage } from '../../lib/chat/types'
import type { Conversation } from '../../lib/chat/conversations'
import { compareConversations } from '../../lib/chat/conversations'
import { useAppNotifications } from '../../composables/useAppNotifications'
import SearchHighlight from './SearchHighlight.vue'

const props = defineProps<{
  conversations: readonly Conversation[]
  messages?: readonly ChatMessage[] | undefined
  pagination?: ReturnType<typeof useChatBackend>['pagination'] | undefined
  returnFocus?: HTMLElement | null
}>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ select: [id: string, messageId?: string] }>()
const { query, results, matches, loading, error, diagnostics, cursor, search } = useConversationSearch(open, () => props.conversations, () => props.pagination)
const notifications = useAppNotifications()
const { viewportStyle } = useChatViewport()
const { t, language } = useAppLocale()
const category = ref('all')
// Only conversations (including message text) have a searchable data source.
const categories = computed(() => [
  { id: 'all', label: t('searchAll'), available: true },
  { id: 'chats', label: t('searchCategoryChats'), available: true },
  { id: 'images', label: t('searchCategoryImages'), available: false },
  { id: 'documents', label: t('searchCategoryDocuments'), available: false },
  { id: 'pages', label: 'Pages', available: false },
  { id: 'projects', label: t('searchCategoryProjects'), available: false },
])
const dateFormat = computed(() => new Intl.DateTimeFormat(language.value === 'de' ? 'de-DE' : 'en-GB', { day: 'numeric', month: 'short' }))
function formatDate(date: string): string {
  return dateFormat.value.format(new Date(date))
}
function clearQuery(): void {
  query.value = ''
  document.querySelector<HTMLInputElement>('#chat-search-input')?.focus({ preventScroll: true })
}
const selected = ref(false)
const selectedMessage = ref<string | undefined>()
const selectionVisible = ref(false)
let focusRevision = 0
watch(query, () => { selectionVisible.value = false }, { flush: 'sync' })
// UCommandPalette forwards this object to UInput, including native attributes.
const input = computed(() => ({
  id: 'chat-search-input', 'aria-label': t('searchChats'), role: 'combobox',
  'aria-expanded': true, 'aria-controls': 'chat-search-listbox', 'aria-autocomplete': 'list',
  ui: { root: () => 'chat-search-input', base: () => 'chat-search-input-base', trailing: () => 'chat-search-input-trailing' },
}))

function select(id: string, messageId?: string): void {
  selected.value = true
  selectedMessage.value = messageId
  open.value = false
  emit('select', id, messageId)
}

const localMatches = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  if (!needle || props.pagination) return []
  return (props.messages ?? []).filter(message => message.content.toLocaleLowerCase().includes(needle)).map(message => {
    const index = message.content.toLocaleLowerCase().indexOf(needle)
    const start = Math.max(0, index - 60)
    return { conversationId: message.conversationId, messageId: message.id, excerpt: `${start ? '…' : ''}${message.content.slice(start, start + 180)}` }
  })
})
const searchMatches = computed(() => props.pagination ? matches.value : localMatches.value)
const groups = computed(() => [{
  id: 'recent-chats', label: t('recentChats'), ignoreFilter: true,
  items: [...(props.pagination ? results.value : props.conversations)].sort(compareConversations).filter(conversation => props.pagination || !query.value.trim() || conversation.title.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase()) || searchMatches.value.some(match => match.conversationId === conversation.id)).map(conversation => {
    const match = searchMatches.value.find(match => match.conversationId === conversation.id)
    // Render text ourselves via #item. Nuxt UI's descriptionHtml branch bypasses
    // #item-description; interpolation here keeps server excerpts out of v-html.
    const date = conversation.updatedAt
    return { id: conversation.id, label: conversation.title, excerpt: match?.excerpt, date, icon: 'i-lucide-message-circle', onSelect: () => select(conversation.id, match?.messageId) }
  }),
}])

function syncListbox(): void {
  const listbox = document.querySelector<HTMLElement>('.chat-search-dialog [role="listbox"]')
  listbox?.setAttribute('id', 'chat-search-listbox')
  listbox?.setAttribute('aria-label', t('recentChats'))
  // Chromium makes overflowing non-interactive scroll areas an implicit Tab
  // stop. Results already use the combobox's active descendant and arrow keys.
  // Keep Tab on search actions and filters, including after empty/results swaps.
  document.querySelector<HTMLElement>('.chat-search-dialog .chat-search-viewport')?.setAttribute('tabindex', '-1')
}
watch([open, groups], () => { void nextTick(syncListbox) }, { flush: 'post' })

function initialFocus(event: Event): void {
  event.preventDefault()
  focusRevision++
  selected.value = false
  selectedMessage.value = undefined
  category.value = 'all'
  selectionVisible.value = false
  // This version of the palette exposes no content-ID prop. Label the native
  // Reka listbox so the input's controls relationship targets the actual popup.
  syncListbox()
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
    else if (chosen && selectedMessage.value) {
      const message = [...document.querySelectorAll<HTMLElement>('[data-message-id]')].find(node => node.dataset.messageId === selectedMessage.value)
      if (message) { message.tabIndex = -1; message.focus({ preventScroll: true }) }
    }
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
          itemWrapper: () => 'chat-search-row-copy', itemLabel: () => 'chat-search-row-title', itemDescription: () => 'chat-search-row-excerpt',
          empty: () => 'chat-search-empty', footer: () => 'chat-search-footer',
        }"
        @keydown="revealKeyboardSelection" @pointermove="revealPointerSelection"
      >
        <template #close>
          <span class="chat-search-loading" aria-hidden="true">
            <UIcon v-if="loading" name="i-lucide-loader-circle" class="size-4 motion-safe:animate-spin" />
          </span>
          <UButton v-if="query" color="neutral" variant="ghost" :label="t('delete')" class="chat-search-clear" @click="clearQuery" />
          <span v-if="query" class="chat-search-separator" aria-hidden="true" />
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" :aria-label="t('closeSearch')" class="noris-nav-icon-button chat-search-close" @click="open = false" />
        </template>
        <template #item="{ item }">
          <span class="chat-search-leading" aria-hidden="true"><UIcon :name="item.icon" class="chat-search-icon" /></span>
          <span class="chat-search-row-copy">
            <span class="chat-search-row-title" :title="item.label"><SearchHighlight :text="item.label ?? ''" :query="query" /></span>
            <span v-if="item.excerpt" class="chat-search-row-excerpt"><SearchHighlight :text="item.excerpt" :query="query" /></span>
          </span>
          <time class="chat-search-row-date" :datetime="item.date">{{ formatDate(item.date) }}</time>
        </template>
        <template #empty>
          <p class="chat-search-label">{{ t('recentChats') }}</p>
          <p v-if="!loading && !error" role="status" class="chat-search-message">{{ t('noChats') }}</p>
        </template>
        <template #footer>
          <!-- 4.11.3 exposes input/content/footer slots. Grid places these footer
               children above and below the list, leaving one scrolling viewport. -->
          <nav class="chat-search-categories" :aria-label="t('searchCategories')">
            <button
              v-for="entry in categories" :key="entry.id" type="button"
              :disabled="!entry.available" :aria-pressed="entry.available ? category === entry.id : undefined"
              :aria-describedby="!entry.available ? 'chat-search-availability' : undefined"
              :title="!entry.available ? t('searchUnavailable') : undefined"
              @click="category = entry.id"
            >{{ entry.label }}</button>
            <span class="chat-search-availability" aria-hidden="true">{{ t('searchAvailable') }}</span>
            <span id="chat-search-availability" class="sr-only">{{ t('searchUnavailable') }}</span>
          </nav>
          <div class="chat-search-actions">
            <p role="status" aria-live="polite" class="sr-only">{{ loading ? t('searchLoading') : t('searchReady') }}</p>
            <p v-if="error" role="alert" class="chat-search-message">
              {{ error }}
              <UButton color="neutral" variant="ghost" :label="t('retrySearch')" class="min-h-11" @click="search(Boolean(cursor))" />
              <UButton v-if="diagnostics && notifications" color="neutral" variant="link" label="Details" @click="notifications.details.value = diagnostics" />
            </p>
            <UButton v-if="cursor" color="neutral" variant="ghost" :label="t('moreChats')" :loading="loading" :disabled="loading" class="min-h-11" @click="search(true)" />
          </div>
        </template>
      </UCommandPalette>
    </template>
  </UModal>
</template>

<style>
/* Raster reference: 938×599 against a 68px rail. Normalize by the existing
   52px CSS rail: approximately 720×460. Original DPR/zoom are unknown. */
.chat-search-overlay { position: fixed; inset: 0; z-index: 60; background: rgb(0 0 0 / 4%); }
.dark .chat-search-overlay { background: rgb(0 0 0 / 24%); }
.chat-search-dialog {
  --search-width: 720px;
  --search-height: 460px;
  --search-inset: 24px;
  --search-input-height: 64px;
  --search-category-height: 44px;
  --search-icon-column: 28px;
  --search-result-icon-size: 18px;
  position: fixed; z-index: 70; left: 50%;
  top: calc(var(--chat-viewport-offset, 0px) + var(--chat-viewport-height, 100dvh) / 2 - 1rem);
  transform: translate(-50%, -50%); display: flex;
  width: min(var(--search-width), calc(100vw - 32px));
  height: min(var(--search-height), calc(var(--chat-viewport-height, 100dvh) - 64px));
  max-height: calc(var(--chat-viewport-height, 100dvh) - 32px);
  overflow: hidden; border: 1px solid var(--noris-border); border-radius: 16px;
  background: var(--noris-composer-background); color: var(--noris-text-primary);
  box-shadow: 0 16px 32px rgb(0 0 0 / 12%); outline: none;
}
.chat-search-palette { display: grid; flex: 1; grid-template-rows: auto auto minmax(0, 1fr) auto; min-width: 0; min-height: 0; }
.chat-search-input { position: relative; display: flex; align-items: center; grid-row: 1; width: 100%; min-width: 0; }
.chat-search-input-base { flex: 1; min-width: 0; width: 100%; height: var(--search-input-height); padding: 0 8px 0 var(--search-inset); border: 0; border-radius: 0; background: transparent; box-shadow: none; color: inherit; font-size: 16px; outline: none; }
.chat-search-input-base::placeholder { color: var(--noris-text-secondary); opacity: 1; }
.chat-search-input-base:focus-visible { outline: none; }
.chat-search-input-trailing { position: static; display: flex; flex: none; align-items: center; gap: 8px; padding-inline-end: 12px; }
.chat-search-loading { display: flex; width: 16px; color: var(--noris-text-secondary); }
.chat-search-clear { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 0 12px; border-radius: 8px; color: var(--noris-text-secondary); font-size: 14px; }
.chat-search-close { color: var(--noris-text-secondary); }
.chat-search-separator { width: 1px; height: 20px; background: var(--noris-border); }
.chat-search-categories { grid-row: 2; display: flex; align-items: center; gap: 4px; min-width: 0; min-height: var(--search-category-height); padding: 0 12px 8px; }
.chat-search-categories button { flex: none; min-height: 36px; padding: 6px 12px; border-radius: 999px; color: var(--noris-text-secondary); font-size: 14px; line-height: 24px; cursor: pointer; }
.chat-search-categories button[aria-pressed="true"], .chat-search-categories button:not(:disabled):hover { color: var(--noris-text-primary); background: var(--noris-hover-background); }
.chat-search-categories button:disabled { opacity: 0.55; cursor: not-allowed; }
.chat-search-content { grid-row: 3; display: flex; flex-direction: column; min-height: 0; min-width: 0; overflow: hidden; }
.chat-search-viewport { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; overscroll-behavior: contain; padding: 4px 12px 12px; scroll-padding-block: 8px; }
.chat-search-label { margin: 0; padding: 8px 12px; color: var(--noris-text-secondary); font-size: 14px; font-weight: 400; line-height: 20px; }
/* Search matches need no redundant recent-chats heading in the reference. */
.chat-search-palette:has(.chat-search-clear) .chat-search-group > .chat-search-label { display: none; }
.chat-search-row { display: flex; align-items: center; gap: 16px; width: 100%; min-width: 0; min-height: 64px; height: auto; padding: 10px 12px; border: 0; border-radius: 12px; font-size: 14px; font-weight: 400; line-height: 20px; text-align: left; cursor: pointer; outline: none; }
.chat-search-palette[data-selection-visible="true"] .chat-search-row[data-highlighted] { background: var(--noris-active-background); }
.chat-search-row:focus-visible { outline: 2px solid var(--noris-text-primary); outline-offset: -2px; }
.chat-search-leading { display: inline-flex; align-items: center; justify-content: center; flex: none; width: var(--search-icon-column); height: var(--search-icon-column); }
.chat-search-icon { flex: none; width: var(--search-result-icon-size); height: var(--search-result-icon-size); }
.chat-search-row-copy { display: flex; flex: 1; flex-direction: column; min-width: 0; overflow: hidden; gap: 4px; }
.chat-search-row-title { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.chat-search-row-excerpt { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; white-space: normal; font-size: 14px; line-height: 20px; color: var(--noris-text-secondary); }
.chat-search-row mark { background: transparent; color: inherit; font-weight: 600; }
.chat-search-row-date { flex: none; margin-inline-start: auto; color: var(--noris-text-secondary); font-size: 12px; line-height: 20px; white-space: nowrap; }
.chat-search-empty { padding-inline: 12px; }
.chat-search-message { margin: 0; padding: 8px 0; color: var(--noris-text-secondary); font-size: 14px; }
.chat-search-footer { display: contents; }
.chat-search-actions { grid-row: 4; }
.chat-search-actions:has(> button, > [role="alert"]) { padding: 0 var(--search-inset) 12px; }
.chat-search-availability { margin-inline-start: auto; font-size: 12px; line-height: 16px; color: var(--noris-text-secondary); white-space: nowrap; }
.chat-timeline [data-message-id][tabindex="-1"]:focus { outline: 2px solid var(--noris-text-primary); outline-offset: 4px; border-radius: 8px; }
@media (max-width: 639px) {
  .chat-search-dialog { --search-inset: 16px; top: calc(var(--chat-viewport-offset, 0px) + var(--chat-viewport-height, 100dvh) / 2); height: min(var(--search-height), calc(var(--chat-viewport-height, 100dvh) - 32px)); }
  .chat-search-categories { flex-wrap: wrap; gap: 0; padding-inline: 8px; }
  .chat-search-categories button { min-width: 44px; min-height: 44px; padding-inline: 8px; font-size: 12px; }
  .chat-search-availability { flex-basis: 100%; margin: 4px 8px 0; }
  .chat-search-viewport, .chat-search-empty { padding-inline: 8px; }
  .chat-search-row { gap: 12px; padding-inline: 8px; }
  .chat-search-row-date { font-size: 11px; }
}
</style>
