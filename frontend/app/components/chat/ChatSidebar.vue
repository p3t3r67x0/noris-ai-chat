<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DropdownMenuItem } from '@nuxt/ui'
import type { Conversation } from '../../lib/chat/conversations'
import { groupConversations } from '../../lib/chat/conversations'
import DeleteConversationDialog from './DeleteConversationDialog.vue'

const props = defineProps<{ conversations: readonly Conversation[], archived: readonly Conversation[], activeId: string | null, removeConversation: (id: string) => void | Promise<void> }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ newChat: [], select: [id: string], rename: [id: string, title: string], archive: [id: string], restore: [id: string] }>()
const groups = computed(() => groupConversations(props.conversations))
const searchOpen = ref(false)
const archiveOpen = ref(false)
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
  emit('select', id)
  searchOpen.value = false
  closeOnMobile()
}

function newChat(): void {
  emit('newChat')
  closeOnMobile()
}

function showSearch(): void {
  closeOnMobile()
  searchOpen.value = true
}

function showArchive(): void {
  closeOnMobile()
  archiveOpen.value = true
}

function actions(conversation: Conversation): DropdownMenuItem[] {
  return [
    { label: 'Umbenennen', icon: 'i-lucide-pencil', onSelect: () => { closeOnMobile(); renameTarget.value = conversation; renameTitle.value = conversation.title } },
    { label: 'Archivieren', icon: 'i-lucide-archive', onSelect: () => emit('archive', conversation.id) },
    { label: 'Löschen', icon: 'i-lucide-trash-2', color: 'error', onSelect: () => showDelete(conversation, actionsTrigger.value) },
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

const searchGroups = computed(() => [{
  id: 'conversations', label: 'Gespräche',
  items: [...props.conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).map(conversation => ({
    id: conversation.id, label: conversation.title, icon: 'i-lucide-square-pen', onSelect: () => selectChat(conversation.id),
  })),
}])

defineExpose({ openSearch: showSearch, openArchive: showArchive })
</script>

<template>
  <USidebar
    id="chat-sidebar" v-model:open="open" title="Gespräche" description="Deine Chats mit noris AI"
    collapsible="offcanvas" mode="slideover" :aria-hidden="!open" :inert="!open"
    class="conversation-sidebar" style="--sidebar-width: var(--noris-sidebar-width)"
    :menu="{ side: 'left', ui: { content: 'max-w-[min(23.5rem,90vw)] bg-[var(--noris-sidebar-background)]' } }"
    :ui="{
      container: 'h-[var(--chat-viewport-height,100dvh)] bottom-auto',
      inner: 'bg-[var(--noris-sidebar-background)] divide-transparent',
      header: 'flex-col items-stretch px-2 py-2', body: 'min-h-0 overflow-y-auto px-2', footer: 'p-3',
    }"
  >
    <template #header>
      <div class="sidebar-heading">
        <span class="sidebar-title">Noris AI</span>
        <UButton icon="i-lucide-search" color="neutral" variant="ghost" class="touch-control hidden lg:inline-flex" aria-label="Suche öffnen" @click="showSearch" />
        <UButton icon="i-lucide-panel-left-close" color="neutral" variant="ghost" class="touch-control" aria-label="Gesprächsliste schließen" @click="open = false" />
      </div>
      <div class="sidebar-primary-actions">
        <UButton icon="i-lucide-square-pen" color="neutral" variant="ghost" label="Neuer Chat" class="sidebar-new-chat min-h-11 justify-start rounded-lg" @click="newChat" />
        <UButton icon="i-lucide-search" color="neutral" variant="ghost" label="Chats suchen" class="min-h-11 justify-start rounded-lg lg:hidden" @click="showSearch" />
      </div>
    </template>

    <nav aria-label="Gespräche" class="pb-4">
      <p v-if="groups.length === 0" class="px-3 py-6 text-sm leading-relaxed text-muted">Hier ist Platz für deine Gedanken.<br>Deine Chats erscheinen hier.</p>
      <section v-for="group in groups" :key="group.label" class="mt-5" :aria-label="group.label">
        <h2 class="sidebar-group">{{ group.label }}</h2>
        <ul class="space-y-0.5">
          <li v-for="conversation in group.conversations" :key="conversation.id" class="conversation-row" :data-conversation-id="conversation.id" :data-active="activeId === conversation.id">
            <button type="button" :aria-current="activeId === conversation.id ? 'page' : undefined" :title="conversation.title" @click="selectChat(conversation.id)">
              <span>{{ conversation.title }}</span>
            </button>
            <UDropdownMenu :items="actions(conversation)" :content="{ align: 'start', side: 'right' }">
              <UButton icon="i-lucide-ellipsis" color="neutral" variant="ghost" class="touch-control shrink-0" :aria-label="`Aktionen für ${conversation.title}`" @focus="actionsTrigger = $event.currentTarget as HTMLElement" @click="actionsTrigger = $event.currentTarget as HTMLElement" />
            </UDropdownMenu>
          </li>
        </ul>
      </section>
    </nav>

    <template #footer>
      <div class="flex flex-col gap-2">
        <UButton icon="i-lucide-archive" color="neutral" variant="ghost" label="Archivierte Chats" class="min-h-11 justify-start lg:hidden" @click="showArchive" />
        <UColorModeSelect aria-label="Darstellung" class="w-full" :ui="{ base: 'min-h-11' }" />
        <div class="flex items-center gap-3 px-2 pt-2 lg:hidden">
          <UAvatar text="N" size="sm" class="sidebar-account-avatar" />
          <div class="min-w-0"><p class="sidebar-account-label font-medium">Dein Arbeitsbereich</p><p class="sidebar-account-caption text-muted">Lokale Demo</p></div>
        </div>
      </div>
    </template>
  </USidebar>

  <UModal v-model:open="searchOpen" title="Chats suchen" :ui="{ content: 'max-w-xl', body: 'p-0 sm:p-0' }">
    <template #body>
      <UCommandPalette :groups="searchGroups" placeholder="Chat suchen …" :autofocus="true">
        <template #empty>Keine passenden Chats gefunden.</template>
      </UCommandPalette>
    </template>
  </UModal>

  <UModal v-model:open="renameOpen" title="Chat umbenennen">
    <template #body>
      <form id="rename-chat-form" @submit.prevent="saveRename">
        <label for="chat-title" class="mb-2 block text-sm font-medium">Chat-Titel</label>
        <UInput id="chat-title" v-model="renameTitle" autofocus :maxlength="120" required class="w-full" />
      </form>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="Abbrechen" @click="renameTarget = null" />
        <UButton type="submit" form="rename-chat-form" label="Speichern" :disabled="!renameTitle.trim()" />
      </div>
    </template>
  </UModal>

  <DeleteConversationDialog v-model:open="deleteOpen" :conversation="deleteTarget" :remove-conversation="removeConversation" :return-focus="deleteReturnFocus" />

  <UModal v-model:open="archiveOpen" title="Archivierte Chats">
    <template #body>
      <p v-if="archived.length === 0" class="text-sm text-muted">Keine archivierten Chats.</p>
      <ul v-else class="space-y-3">
        <li v-for="conversation in archived" :key="conversation.id" class="flex items-center gap-3">
          <span class="min-w-0 flex-1 truncate text-sm">{{ conversation.title }}</span>
          <UButton icon="i-lucide-undo-2" color="neutral" variant="ghost" class="touch-control" :aria-label="`${conversation.title} wiederherstellen`" @click="emit('restore', conversation.id); archiveOpen = false; closeOnMobile()" />
          <UButton icon="i-lucide-trash-2" color="error" variant="ghost" class="touch-control" :aria-label="`${conversation.title} löschen`" @click="showDelete(conversation, $event.currentTarget as HTMLElement)" />
        </li>
      </ul>
    </template>
  </UModal>
</template>
