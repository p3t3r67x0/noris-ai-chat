<script setup lang="ts">
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useChat } from '../../composables/useChat'
import { useChatTransport } from '../../composables/useChatTransport'
import { useModelSelection } from '../../composables/useModelSelection'
import ChatHeader from './ChatHeader.vue'
import ChatSidebar from './ChatSidebar.vue'
import EmptyChatState from './EmptyChatState.vue'
import ChatComposer from './ChatComposer.vue'
import ChatTimeline from './ChatTimeline.vue'
import { useChatViewport } from '../../composables/useChatViewport'
import { useSidebarPreference } from '../../composables/useSidebarPreference'
import ChatRail from './ChatRail.vue'

const { transport, mode } = useChatTransport()
const chat = useChat(transport)
const { conversations, stream } = chat
const { modelId, error: modelError, notice: modelNotice, loading: modelsLoading, canSend: modelCanSend, fallbackId, refresh: refreshModels, chooseFallback } = useModelSelection({ mode })
const canSend = computed(() => modelCanSend.value && chat.backendReady.value)
let preferencesRestored = false
watch([chat.backendReady, modelsLoading], ([loaded, loading]) => {
  if (!transport.backend || !loaded || loading || preferencesRestored) return
  preferencesRestored = true
  if (transport.backend.preferredModelId) modelId.value = transport.backend.preferredModelId
})
watch(modelId, value => { if (transport.backend && preferencesRestored && value) void transport.backend.preferences(conversations.activeId.value, value).catch(() => {}) })
watch(stream.errorCode, (code) => { if (code === 'MODEL_UNAVAILABLE' || code === 'PROVIDER_AUTH_FAILED') void refreshModels() })
const { draft } = chat.drafts
const { sidebarOpen } = useSidebarPreference()
const sidebar = ref<InstanceType<typeof ChatSidebar> | null>(null)
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const { viewportStyle } = useChatViewport()
const ready = ref(false)
onMounted(() => { ready.value = true; window.addEventListener('keydown', onShortcut) })
onUnmounted(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', onShortcut) })

function send(text: string): void {
  if (canSend.value && chat.send(text, modelId.value)) composer.value?.focus()
}
function stop(): void { stream.stop(); composer.value?.focus() }
function newChat(): void { chat.newChat(); composer.value?.focus() }
async function continueResponse(id: string): Promise<void> {
  if (modelsLoading.value) await refreshModels()
  if (canSend.value) chat.continueResponse(id, modelId.value)
}
async function regenerateResponse(id: string): Promise<void> {
  if (modelsLoading.value) await refreshModels()
  if (canSend.value) chat.regenerate(id, modelId.value)
}
function selectRunningChat(): void {
  const id = chat.generatingConversationId.value
  if (id) conversations.select(id)
}
function onShortcut(event: KeyboardEvent): void {
  if (event.isComposing || event.repeat) return
  if (document.querySelector('.delete-dialog[data-state="open"]')) return
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'o') {
    event.preventDefault(); newChat()
  }
  else if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'k') {
    event.preventDefault(); sidebar.value?.openSearch()
  }
  else if (event.key === 'Escape' && stream.busy.value && !document.querySelector('[role="dialog"]')) { event.preventDefault(); stop() }
}
const editingId = ref<string | null>(null)
const editText = ref('')
const importOpen = ref(false)
const editOpen = computed({ get: () => editingId.value !== null, set: (open: boolean) => { if (!open) editingId.value = null } })
function beginEdit(id: string): void {
  const message = chat.messages.value[id]
  if (!message || stream.busy.value) return
  editingId.value = id
  editText.value = message.content
}
function saveEdit(): void {
  if (canSend.value && editingId.value && chat.edit(editingId.value, editText.value, modelId.value)) editingId.value = null
}
</script>

<template>
  <div class="chat-workspace" :style="viewportStyle" :data-ready="ready" :inert="!ready" :aria-busy="!ready">
    <a href="#chat-main" class="sr-only z-50 rounded-md bg-default p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Zum Chat springen</a>
    <ChatRail :demo="mode === 'mock'" @home="newChat" @search="sidebar?.openSearch()" @archive="sidebar?.openArchive()" />
    <ChatSidebar
      ref="sidebar"
      v-model:open="sidebarOpen" :demo="mode === 'mock'" :conversations="conversations.visible.value" :archived="conversations.archived.value"
      :active-id="conversations.activeId.value" :remove-conversation="chat.remove"
      @new-chat="newChat" @select="conversations.select" @rename="conversations.rename"
      @fit-title="conversations.fitTitle"
      @archive="conversations.archive" @restore="conversations.restore"
    />
    <main id="chat-main" class="chat-main" aria-label="Chat" tabindex="-1">
      <ChatHeader v-model:model="modelId" :sidebar-open="sidebarOpen" :busy="stream.busy.value" :demo="mode === 'mock'" @toggle-sidebar="sidebarOpen = !sidebarOpen" @new-chat="newChat" />
      <div class="chat-content" :data-empty="chat.visible.value.length === 0">
        <EmptyChatState v-if="chat.visible.value.length === 0" />
        <ChatTimeline v-show="chat.visible.value.length > 0" :messages="chat.visible.value" :conversation-id="conversations.activeId.value" :busy="stream.busy.value" :variants="chat.variants" :can-continue="chat.canContinue" @continue="continueResponse" @edit="beginEdit" @regenerate="regenerateResponse" @select-variant="chat.selectVariant" />
        <div class="composer-dock">
          <div v-if="modelError || modelNotice" role="status" aria-live="polite" class="px-4 pb-2 text-sm text-muted">
            <p>{{ modelError || modelNotice }}</p>
            <UButton v-if="fallbackId && !canSend" color="neutral" variant="link" label="Verfügbares Modell auswählen" @click="chooseFallback" />
            <UButton color="neutral" variant="link" label="Modelle neu laden" :loading="modelsLoading" @click="refreshModels" />
          </div>
          <ChatComposer ref="composer" v-model="draft" v-model:model="modelId" :busy="stream.busy.value" :model-unavailable="!canSend" :input-error="chat.drafts.error.value" :streaming="stream.status.value === 'streaming'" :cancellation-requested="stream.cancellationRequested.value" @send="send" @stop="stop" />
          <p v-if="chat.drafts.error.value" role="alert" class="mt-2 text-center text-xs text-error">{{ chat.drafts.error.value }}</p>
          <p class="composer-note">noris AI kann Fehler machen. Prüfe wichtige Informationen.</p>
        </div>
        <div class="chat-status" :data-attention="stream.status.value === 'failed' || (stream.busy.value && chat.generatingConversationId.value !== conversations.activeId.value)" role="status" aria-live="polite" aria-atomic="true" :data-generation-status="stream.status.value">
          <template v-if="stream.busy.value && chat.generatingConversationId.value !== conversations.activeId.value">
            <UButton color="neutral" variant="link" size="xs" label="Antwort läuft in einem anderen Chat" @click="selectRunningChat" />
          </template>
          <span v-else-if="stream.status.value === 'submitting'">Antwort wird vorbereitet …</span>
          <span v-else-if="stream.status.value === 'streaming'">{{ stream.cancellationRequested.value ? 'Antwort wird gestoppt …' : 'noris AI antwortet …' }}</span>
          <span v-else-if="stream.status.value === 'cancelled'">Antwort gestoppt.</span>
          <template v-else-if="stream.status.value === 'failed'">
            <span>{{ stream.error.value }}</span>
            <UButton color="neutral" variant="ghost" label="Erneut versuchen" class="min-h-11" :disabled="stream.busy.value || !canSend" @click="chat.retry(modelId)" />
          </template>
          <span v-else-if="stream.status.value === 'completed'" class="sr-only">Antwort abgeschlossen.</span>
        </div>
        <p v-if="chat.storageWarning.value" role="alert" class="px-4 pb-3 text-center text-xs text-warning">{{ chat.storageWarning.value }}</p>
        <div v-if="chat.importAvailable.value" class="px-4 pb-2 text-center">
          <UButton color="neutral" variant="link" label="Lokale Chats importieren" @click="importOpen = true" />
        </div>
      </div>
    </main>
    <UModal v-model:open="editOpen" title="Nachricht bearbeiten" description="Deine ursprüngliche Frage und ihre Antworten bleiben als Variante erhalten.">
      <template #body>
        <form id="edit-message-form" @submit.prevent="saveEdit">
          <UTextarea v-model="editText" aria-label="Nachricht bearbeiten" autofocus autoresize :rows="4" :maxrows="12" class="w-full" />
          <p v-if="editText.length > CHAT_LIMITS.max_message_chars" role="alert" class="mt-2 text-xs text-error">Die Nachricht darf höchstens {{ CHAT_LIMITS.max_message_chars.toLocaleString('de-DE') }} Zeichen enthalten.</p>
        </form>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="Abbrechen" @click="editingId = null" />
          <UButton type="submit" form="edit-message-form" label="Speichern und senden" :disabled="stream.busy.value || !canSend || !editText.trim() || editText.length > CHAT_LIMITS.max_message_chars" />
        </div>
      </template>
    </UModal>
    <UModal v-model:open="importOpen" title="Lokale Chats importieren" description="Überträgt die bisherigen Browser-Chats einschließlich Varianten, Titeln und Entwürfen in die Datenbank. Die lokale Sicherung bleibt erhalten. Bei Konflikten wird der Import abgebrochen.">
      <template #footer>
        <UButton color="neutral" variant="ghost" label="Abbrechen" @click="importOpen = false" />
        <UButton label="Import ausdrücklich starten" :loading="chat.importBusy.value" @click="chat.importLocalChats().finally(() => { importOpen = false })" />
      </template>
    </UModal>
  </div>
</template>
