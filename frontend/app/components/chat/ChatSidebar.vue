<script setup lang="ts">
import { normalizeAppError } from '../../lib/notifications/errors'
import { useAppLocale } from '../../composables/useAppLocale'
import { computed, ref } from 'vue'
import type { useChatBackend } from '../../composables/useChatBackend'
import type { DropdownMenuItem } from '@nuxt/ui'
import type { Conversation } from '../../lib/chat/conversations'
import { groupConversations } from '../../lib/chat/conversations'
import DeleteConversationDialog from './DeleteConversationDialog.vue'
import ConversationTitle from './ConversationTitle.vue'
import ProfileMenu from './ProfileMenu.vue'
import ChatSearchDialog from './ChatSearchDialog.vue'
const { t } = useAppLocale()

const props = defineProps<{ demo?: boolean, pagination?: ReturnType<typeof useChatBackend>['pagination'] | undefined, conversations: readonly Conversation[], archived: readonly Conversation[], activeId: string | null, removeConversation: (id: string) => void | Promise<void> }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ newChat: [], focusComposer: [], select: [id: string], rename: [id: string, title: string], archive: [id: string], restore: [id: string], settings: [] }>()
const groups = computed(() => groupConversations(props.conversations))
const searchOpen = ref(false)
const archiveOpen = ref(false)
const searchReturnFocus = ref<HTMLElement | null>(null)
let searchDrawerHandoff = false
let newChatDrawerHandoff = false
const archiveLoading = ref(false)
const archiveError = ref<string | null>(null)
const archiveCursor = ref<string | null>(null)
const archiveResults = ref<Conversation[]>([])
const archivedRows = computed(() => props.pagination ? archiveResults.value : props.archived)
async function loadArchive(more = false): Promise<void> {
  if (!props.pagination || archiveLoading.value) return
  archiveLoading.value = true; archiveError.value = null
  try {
    const result = await props.pagination.loadArchive(more ? archiveCursor.value ?? undefined : undefined)
    const rows = result.conversations.map(c => ({ ...c, titleGenerationAttempted: c.titleSource !== 'fallback' }))
    archiveResults.value = [...new Map([...(more ? archiveResults.value : []), ...rows].map(c => [c.id, c])).values()]
    archiveCursor.value = result.nextCursor ?? null
  }
  catch (cause) { archiveError.value = normalizeAppError(cause, { operation: 'archive' }).message }
  finally { archiveLoading.value = false }
}
const renameTarget = ref<Conversation | null>(null)
const deleteTarget = ref<Conversation | null>(null)
const deleteReturnFocus = ref<HTMLElement | null>(null)
const actionsTrigger = ref<HTMLElement | null>(null)
const renameTitle = ref('')
const renameOpen = computed({ get: () => renameTarget.value !== null, set: (value: boolean) => { if (!value) renameTarget.value = null } })
const deleteOpen = computed({ get: () => deleteTarget.value !== null, set: (value: boolean) => { if (!value) deleteTarget.value = null } })

function closeOnMobile(): void {
  if (import.meta.client && window.matchMedia('(max-width: 1023px)').matches) open.value = false
}

function selectChat(id: string): void {
  searchOpen.value = false
  emit('select', id)
  closeOnMobile()
}

function newChat(): void {
  newChatDrawerHandoff = open.value && window.matchMedia('(max-width: 1023px)').matches
  emit('newChat')
  closeOnMobile()
}

function showSearch(event?: Event): void {
  if (searchOpen.value) return
  searchReturnFocus.value = event?.currentTarget instanceof HTMLElement ? event.currentTarget : document.activeElement as HTMLElement | null
  if (window.matchMedia('(max-width: 1023px)').matches && document.querySelector('[role="dialog"] .sidebar-primary-actions')) searchDrawerHandoff = true
  closeOnMobile()
  searchOpen.value = true
}

function finishDrawerHandoff(event: Event): void {
  if (newChatDrawerHandoff) {
    newChatDrawerHandoff = false
    event.preventDefault()
    emit('focusComposer')
  }
  if (!searchDrawerHandoff) return
  searchDrawerHandoff = false
  // The drawer's delayed cleanup must not reclaim focus from search or the
  // composer when search has already closed. Its normal dismissal is unchanged.
  event.preventDefault()
}

function showArchive(): void {
  closeOnMobile()
  archiveOpen.value = true
  void loadArchive()
}

function showSettings(): void { closeOnMobile(); emit('settings') }

function actions(conversation: Conversation): DropdownMenuItem[] {
  return [
    { label: t('rename'), icon: 'i-lucide-pencil', onSelect: () => { closeOnMobile(); renameTarget.value = conversation; renameTitle.value = conversation.title } },
    { label: t('archive'), icon: 'i-lucide-archive', onSelect: () => emit('archive', conversation.id) },
    { label: t('delete'), icon: 'i-lucide-trash-2', color: 'error', onSelect: () => showDelete(conversation, actionsTrigger.value) },
  ]
}

function saveRename(): void {
  if (!renameTarget.value || !renameTitle.value.trim()) return
  emit('rename', renameTarget.value.id, renameTitle.value)
  renameTarget.value = null
}

function showDelete(conversation: Conversation, trigger: HTMLElement | null): void {
  deleteReturnFocus.value = trigger
  closeOnMobile()
  archiveOpen.value = false
  deleteTarget.value = conversation
}

defineExpose({ openSearch: showSearch, openArchive: showArchive })
</script>

<template>
  <USidebar
    id="chat-sidebar" v-model:open="open" :title="t('conversations')" description="Deine Chats mit noris AI"
    collapsible="offcanvas" mode="slideover" :aria-hidden="!open" :inert="!open"
    class="conversation-sidebar" style="--sidebar-width: var(--noris-sidebar-width)"
    :menu="{ side: 'left', content: { onCloseAutoFocus: finishDrawerHandoff }, ui: { content: 'max-w-[min(23.5rem,90vw)] bg-[var(--noris-sidebar-background)]' } }"
    :ui="{
      container: 'h-[var(--chat-viewport-height,100dvh)] bottom-auto',
      inner: 'bg-[var(--noris-sidebar-background)] divide-transparent',
      header: 'flex-col items-stretch px-2 py-2', body: 'min-h-0 overflow-y-auto px-2', footer: 'p-3',
    }"
  >
    <template #header>
      <div class="sidebar-heading">
        <span class="sidebar-title">Noris AI</span>
        <UButton icon="i-lucide-search" color="neutral" variant="ghost" class="touch-control hidden lg:inline-flex" :aria-label="t('chatSearch')" @click="showSearch" />
        <UButton icon="i-lucide-panel-left-close" color="neutral" variant="ghost" class="touch-control" :aria-label="t('closeConversations')" @click="open = false" />
      </div>
      <div class="sidebar-primary-actions">
        <UButton icon="i-lucide-square-pen" color="neutral" variant="ghost" :label="t('newChat')" class="sidebar-new-chat min-h-11 justify-start rounded-lg" @click="newChat" />
        <UButton icon="i-lucide-search" color="neutral" variant="ghost" :label="t('searchChats')" class="min-h-11 justify-start rounded-lg lg:hidden" @click="showSearch" />
      </div>
    </template>

    <nav :aria-label="t('conversations')" class="pb-4">
      <details v-if="pagination?.sidebarError.value" class="px-3 py-2 text-sm text-warning"><summary>Chatliste nicht verfügbar.</summary><p>{{ pagination.sidebarError.value }}</p></details>
      <UButton v-if="pagination?.sidebarError.value || pagination?.windowedList.value" color="neutral" variant="ghost" label="Neueste Chats laden" :loading="pagination?.sidebarLoading.value" @click="pagination?.reloadSidebar" />
      <p v-if="pagination?.sidebarLoading.value && groups.length === 0" role="status" class="px-3 py-2 text-sm text-muted">Chats werden geladen …</p>
      <p v-if="groups.length === 0 && !pagination?.sidebarLoading.value && !pagination?.sidebarError.value" class="px-3 py-6 text-sm leading-relaxed text-muted">{{ t('emptyConversations') }}</p>
      <section v-for="group in groups" :key="group.label" class="mt-5" :aria-label="group.label">
        <h2 class="sidebar-group">{{ group.label }}</h2>
        <ul class="space-y-0.5">
          <li v-for="conversation in group.conversations" :key="conversation.id" class="conversation-row" :data-conversation-id="conversation.id" :data-active="activeId === conversation.id">
            <button type="button" :aria-current="activeId === conversation.id ? 'page' : undefined" :title="conversation.title" @click="selectChat(conversation.id)">
              <ConversationTitle :title="conversation.title" :source="conversation.titleSource" />
            </button>
            <UDropdownMenu :items="actions(conversation)" :content="{ align: 'start', side: 'right' }">
              <UButton icon="i-lucide-ellipsis" color="neutral" variant="ghost" class="touch-control shrink-0" :aria-label="`Aktionen für ${conversation.title}`" @focus="actionsTrigger = $event.currentTarget as HTMLElement" @click="actionsTrigger = $event.currentTarget as HTMLElement" />
            </UDropdownMenu>
          </li>
        </ul>
      </section>
      <UButton v-if="pagination?.hasMore.value" color="neutral" variant="ghost" :label="t('moreChats')" :loading="pagination.sidebarLoading.value" class="mt-3 w-full" @click="pagination.loadMore" />
    </nav>

    <template #footer>
      <div class="flex flex-col gap-2">
        <UButton icon="i-lucide-archive" color="neutral" variant="ghost" :label="t('archived')" class="min-h-11 justify-start lg:hidden" @click="showArchive" />
        <UButton icon="i-lucide-settings" color="neutral" variant="ghost" :label="t('settings')" class="min-h-11 justify-start lg:hidden" @click="showSettings" />
        <UColorModeSelect aria-label="Darstellung" class="w-full" :ui="{ base: 'min-h-11' }" />
        <div class="lg:hidden"><ProfileMenu :demo="demo" :compact="false" /></div>
      </div>
    </template>
  </USidebar>

  <ChatSearchDialog
    v-model:open="searchOpen" :conversations="conversations" :pagination="pagination"
    :return-focus="searchReturnFocus" @select="selectChat"
  />

  <UModal v-model:open="renameOpen" :title="t('renameChat')">
    <template #body>
      <form id="rename-chat-form" @submit.prevent="saveRename">
        <label for="chat-title" class="mb-2 block text-sm font-medium">{{ t('chatTitle') }}</label>
        <UInput id="chat-title" v-model="renameTitle" autofocus :maxlength="120" required class="w-full" />
      </form>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="ghost" :label="t('cancel')" @click="renameTarget = null" />
        <UButton type="submit" form="rename-chat-form" :label="t('save')" :disabled="!renameTitle.trim()" />
      </div>
    </template>
  </UModal>

  <DeleteConversationDialog v-model:open="deleteOpen" :conversation="deleteTarget" :remove-conversation="removeConversation" :return-focus="deleteReturnFocus" />

  <UModal v-model:open="archiveOpen" :title="t('archived')">
    <template #body>
      <p v-if="archiveError" role="alert" class="text-sm text-warning">{{ archiveError }} <UButton label="Archiv erneut laden" variant="link" @click="loadArchive()" /></p>
      <p v-if="archivedRows.length === 0 && !archiveLoading" class="text-sm text-muted">{{ t('emptyArchive') }}</p>
      <ul v-else class="space-y-3">
        <li v-for="conversation in archivedRows" :key="conversation.id" class="flex items-center gap-3">
          <span class="min-w-0 flex-1 truncate text-sm">{{ conversation.title }}</span>
          <UButton icon="i-lucide-undo-2" color="neutral" variant="ghost" class="touch-control" :aria-label="`${conversation.title} wiederherstellen`" @click="emit('restore', conversation.id); archiveOpen = false; closeOnMobile()" />
          <UButton icon="i-lucide-trash-2" color="error" variant="ghost" class="touch-control" :aria-label="`${conversation.title} löschen`" @click="showDelete(conversation, $event.currentTarget as HTMLElement)" />
        </li>
      </ul>
      <UButton v-if="archiveCursor" label="Weitere archivierte Chats laden" color="neutral" variant="ghost" :loading="archiveLoading" @click="loadArchive(true)" />
    </template>
  </UModal>
</template>
