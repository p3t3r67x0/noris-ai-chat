<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DropdownMenuItem } from '@nuxt/ui'
import type { Conversation } from '../../lib/chat/conversations'
import { groupConversations } from '../../lib/chat/conversations'

const props = defineProps<{ conversations: readonly Conversation[], archived: readonly Conversation[], activeId: string | null }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ newChat: [], select: [id: string], rename: [id: string, title: string], archive: [id: string], restore: [id: string], delete: [id: string] }>()
const groups = computed(() => groupConversations(props.conversations))
const searchOpen = ref(false)
const archiveOpen = ref(false)
const renameTarget = ref<Conversation | null>(null)
const deleteTarget = ref<Conversation | null>(null)
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
    { label: 'Löschen', icon: 'i-lucide-trash-2', color: 'error', onSelect: () => { closeOnMobile(); deleteTarget.value = conversation } },
  ]
}

function saveRename(): void {
  if (!renameTarget.value || !renameTitle.value.trim()) return
  emit('rename', renameTarget.value.id, renameTitle.value)
  renameTarget.value = null
}

function confirmDelete(): void {
  if (!deleteTarget.value) return
  emit('delete', deleteTarget.value.id)
  deleteTarget.value = null
}

const searchGroups = computed(() => [{
  id: 'conversations', label: 'Gespräche',
  items: [...props.conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).map(conversation => ({
    id: conversation.id, label: conversation.title, icon: 'i-lucide-square-pen', onSelect: () => selectChat(conversation.id),
  })),
}])

defineExpose({ openSearch: showSearch })
</script>

<template>
  <USidebar
    id="chat-sidebar" v-model:open="open" title="Gespräche" description="Deine Chats mit noris AI"
    collapsible="offcanvas" mode="slideover" :aria-hidden="!open" :inert="!open"
    style="--sidebar-width: 17rem"
    :menu="{ side: 'left', ui: { content: 'max-w-[min(19rem,90vw)] bg-[var(--noris-sidebar)]' } }"
    :ui="{
      container: 'h-[var(--chat-viewport-height,100dvh)] bottom-auto',
      inner: 'bg-[var(--noris-sidebar)] border-r border-default',
      header: 'flex-col items-stretch px-3 py-3', body: 'min-h-0 overflow-y-auto px-2', footer: 'border-t border-default p-3',
    }"
  >
    <template #header>
      <div class="flex w-full items-center gap-2 px-1">
        <span aria-hidden="true" class="flex size-8 items-center justify-center rounded-xl bg-inverted text-sm font-bold text-inverted">n</span>
        <span class="flex-1 text-base font-semibold tracking-tight">noris AI</span>
        <UButton icon="i-lucide-panel-left-close" color="neutral" variant="ghost" class="touch-control" aria-label="Gesprächsliste schließen" @click="open = false" />
      </div>
      <div class="mt-4 flex w-full flex-col gap-1">
        <UButton icon="i-lucide-square-pen" color="neutral" variant="ghost" label="Neuer Chat" class="min-h-11 justify-start rounded-lg" @click="newChat" />
        <UButton icon="i-lucide-search" color="neutral" variant="ghost" label="Chats suchen" class="min-h-11 justify-start rounded-lg" @click="showSearch" />
      </div>
    </template>

    <nav aria-label="Gespräche" class="pb-4">
      <p v-if="groups.length === 0" class="px-3 py-6 text-sm leading-relaxed text-muted">Hier ist Platz für deine Gedanken.<br>Deine Chats erscheinen hier.</p>
      <section v-for="group in groups" :key="group.label" class="mt-5" :aria-label="group.label">
        <h2 class="px-3 pb-2 text-xs font-medium text-muted">{{ group.label }}</h2>
        <ul class="space-y-0.5">
          <li v-for="conversation in group.conversations" :key="conversation.id" class="conversation-row" :data-active="activeId === conversation.id">
            <button type="button" :aria-current="activeId === conversation.id ? 'page' : undefined" :title="conversation.title" @click="selectChat(conversation.id)">
              <span>{{ conversation.title }}</span>
            </button>
            <UDropdownMenu :items="actions(conversation)" :content="{ align: 'start', side: 'right' }">
              <UButton icon="i-lucide-ellipsis" color="neutral" variant="ghost" class="touch-control shrink-0" :aria-label="`Aktionen für ${conversation.title}`" />
            </UDropdownMenu>
          </li>
        </ul>
      </section>
    </nav>

    <template #footer>
      <div class="flex flex-col gap-2">
        <UButton icon="i-lucide-archive" color="neutral" variant="ghost" label="Archivierte Chats" class="min-h-11 justify-start" @click="showArchive" />
        <UColorModeSelect aria-label="Darstellung" class="w-full" :ui="{ base: 'min-h-11' }" />
        <div class="flex items-center gap-3 px-2 pt-2">
          <UAvatar text="N" size="sm" />
          <div class="min-w-0"><p class="text-sm font-medium">Dein Arbeitsbereich</p><p class="text-xs text-muted">Lokale Demo</p></div>
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

  <UModal v-model:open="deleteOpen" title="Chat löschen?" description="Dieser Chat und sein Verlauf werden aus der lokalen Demo entfernt.">
    <template #body><p class="break-words text-sm">{{ deleteTarget?.title }}</p></template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="Abbrechen" @click="deleteTarget = null" />
        <UButton color="error" label="Löschen" @click="confirmDelete" />
      </div>
    </template>
  </UModal>

  <UModal v-model:open="archiveOpen" title="Archivierte Chats">
    <template #body>
      <p v-if="archived.length === 0" class="text-sm text-muted">Keine archivierten Chats.</p>
      <ul v-else class="space-y-3">
        <li v-for="conversation in archived" :key="conversation.id" class="flex items-center gap-3">
          <span class="min-w-0 flex-1 truncate text-sm">{{ conversation.title }}</span>
          <UButton icon="i-lucide-undo-2" color="neutral" variant="ghost" class="touch-control" :aria-label="`${conversation.title} wiederherstellen`" @click="emit('restore', conversation.id); archiveOpen = false; closeOnMobile()" />
          <UButton icon="i-lucide-trash-2" color="error" variant="ghost" class="touch-control" :aria-label="`${conversation.title} löschen`" @click="deleteTarget = conversation; archiveOpen = false" />
        </li>
      </ul>
    </template>
  </UModal>
</template>
