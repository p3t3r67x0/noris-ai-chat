<script setup lang="ts">
import { CHAT_LIMITS } from '../../lib/chat/limits'
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
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
import { workspaceKey } from '../../composables/useWorkspace'
import { useAppLocale } from '../../composables/useAppLocale'
import { useChatAttachments } from '../../composables/useChatAttachments'
import type { ApiSchemas } from '../../types/generated/api'
import { supportsPreference } from '../../lib/chat/reasoning'
import { useAppNotifications } from '../../composables/useAppNotifications'
import { normalizeAppError } from '../../lib/notifications/errors'

const { transport, mode } = useChatTransport()
const chat = useChat(transport)
const { conversations, stream } = chat
const notifications = useAppNotifications()
const selection = useModelSelection({ mode })
const { modelId, error: modelError, notice: modelNotice, loading: modelsLoading, canSend: modelCanSend, fallbackId, refresh: refreshModels, chooseFallback } = selection
const supportsImages = computed(() => !modelsLoading.value && !selection.stale.value && !modelError.value && selection.models.some(model => model.id === modelId.value && !model.disabled && model.imageInput === true))
const attachments = useChatAttachments(transport.backend, conversations.active, chat.backendReady, () => {
  // The first attachment creates the conversation; carry its unsent draft along.
  const previousDraft = chat.drafts.draft.value
  const conversation = conversations.create()
  chat.drafts.draft.value = previousDraft
  chat.drafts.clear(null)
  return conversation
}, supportsImages)
watch([stream.status, stream.busy], ([status, busy]) => {
  if (busy) return
  if (status === 'failed') void attachments.refresh()
  if (status !== 'failed' && status !== 'incomplete') return
  const context = { ...stream.context.value, requestId: stream.errorRequestId.value }
  const messageId = context.resourceId
  const code = stream.errorCode.value ?? (status === 'incomplete' ? 'OUTPUT_LIMIT' : 'STREAM_INTERRUPTED')
  const error = normalizeAppError({ code }, context)
  const retry = messageId ? { label: status === 'incomplete' ? 'Weiterschreiben' : 'Erneut versuchen', onClick: async () => {
    if (stream.busy.value || !context.conversationId) return
    conversations.select(context.conversationId)
    await chat.pagination?.loadConversation(context.conversationId)
    await nextTick()
    if (modelsLoading.value) await refreshModels()
    if (!canSend.value) return
    if (status === 'incomplete') chat.continueResponse(messageId, modelId.value)
    else chat.regenerate(messageId, modelId.value)
  } } : undefined
  const canRecover = status === 'failed' ? error.recovery === 'retry' : Boolean(messageId && chat.canContinue(messageId))
  notifications?.reportError({ code }, context, canRecover ? retry : { label: 'Chat öffnen', onClick: () => { if (context.conversationId) conversations.select(context.conversationId) } })
})
provide(workspaceKey, { chat, selection, mode, importAvailable: computed(() => Boolean(transport.backend) && chat.importAvailable.value) })
const { t } = useAppLocale()
const uploadUnavailableReason = computed(() => !transport.backend ? t('uploadDemoUnavailable') : attachments.error.value || chat.storageWarning.value || t('uploadPreparing'))
const route = useRoute()
const router = useRouter()
const inSettings = computed(() => route.path.startsWith('/settings'))
const openSettings = () => router.push('/settings/general')
let readingPosition = 0
watch(inSettings, async (settings) => {
  const scroll = document.querySelector<HTMLElement>('.chat-scroll')
  if (settings) {
    readingPosition = scroll?.scrollTop ?? 0
    if (window.matchMedia('(max-width: 1023px)').matches) sidebarOpen.value = false
  }
  else {
    await nextTick()
    requestAnimationFrame(() => { if (scroll) scroll.scrollTop = readingPosition; composer.value?.focus() })
  }
}, { flush: 'pre' })
const canSend = computed(() => !chat.settingsBusy.value && !chat.settingsError.value && modelCanSend.value && chat.backendReady.value && !chat.pagination?.historyLoading.value && !chat.pagination?.historyError.value)
const selectedModel = computed(() => selection.models.find(model => model.id === modelId.value))
const reasoningPreference = computed(() => {
  const preference = conversations.active.value?.reasoningPreference
  return preference && supportsPreference(selectedModel.value, preference) ? preference : null
})
let preferencesRestored = false
watch([chat.backendReady, modelsLoading], ([loaded, loading]) => {
  if (!transport.backend || !loaded || loading || preferencesRestored) return
  preferencesRestored = true
  if (transport.backend.preferredModelId) modelId.value = transport.backend.preferredModelId
})
async function saveModelPreference(value: string): Promise<void> {
  if (!transport.backend || !preferencesRestored || !value) return
  await chat.saveModelPreference(value)
}
watch(modelId, value => { void saveModelPreference(value) })
watch([modelId, selectedModel, () => conversations.active.value?.reasoningPreference, chat.backendReady, modelsLoading, chat.settingsBusy], () => {
  if ((transport.backend && !preferencesRestored) || !chat.backendReady.value || modelsLoading.value || chat.settingsBusy.value || chat.settingsError.value) return
  void chat.reconcileReasoningPreference(modelId.value)
}, { immediate: true })
watch(stream.errorCode, (code) => { if (code === 'MODEL_UNAVAILABLE' || code === 'PROVIDER_AUTH_FAILED') void refreshModels(false) })
const { draft } = chat.drafts
const { sidebarOpen } = useSidebarPreference()
const chatSidebarOpen = computed({ get: () => sidebarOpen.value && !inSettings.value, set: (value: boolean) => { if (!inSettings.value || (import.meta.client && window.matchMedia('(max-width: 1023px)').matches)) sidebarOpen.value = value } })
const sidebar = ref<InstanceType<typeof ChatSidebar> | null>(null)
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const { viewportStyle } = useChatViewport()
const ready = ref(false)
onMounted(() => {
  ready.value = true
  if (inSettings.value && window.matchMedia('(max-width: 1023px)').matches) sidebarOpen.value = false
  window.addEventListener('keydown', onShortcut)
})
onUnmounted(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', onShortcut) })

function send(text: string): void {
  if (canSend.value && !attachments.blocked.value && chat.send(text, modelId.value, attachments.confirmed.value)) {
    if (conversations.activeId.value) attachments.sent(conversations.activeId.value)
    composer.value?.focus()
  }
}
function stop(): void { stream.stop(); composer.value?.focus() }
function addReference(value: ApiSchemas['TextReference']): void {
  void attachments.addReference(value)
  composer.value?.focus()
}
function newChat(): void { chat.newChat(); if (inSettings.value) void router.push('/'); else composer.value?.focus() }
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
  if (inSettings.value || event.defaultPrevented || document.querySelector('[role="menu"][data-state="open"]')) return
  if (event.isComposing || event.repeat) return
  if (event.key === 'Escape' && event.target instanceof HTMLElement && event.target.closest('.app-notification, .app-notification-viewport')) return
  if (document.querySelector('.delete-dialog[data-state="open"]')) return
  if (document.querySelector('.chat-search-dialog[data-state="open"]')) {
    if ((event.ctrlKey || event.metaKey) && ((!event.shiftKey && event.key.toLowerCase() === 'k') || (event.shiftKey && event.key.toLowerCase() === 'o'))) event.preventDefault()
    return
  }
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
  <div class="chat-workspace" :class="{ 'settings-workspace': inSettings }" :style="viewportStyle" :data-ready="ready" :inert="!ready" :aria-busy="!ready">
    <a :href="inSettings ? '#settings-main' : '#chat-main'" class="sr-only z-50 rounded-md bg-default p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">{{ inSettings ? t('skipSettings') : t('skipChat') }}</a>
    <ChatRail :demo="mode === 'mock'" @home="inSettings ? router.push('/') : newChat()" @search="router.push('/').then(() => sidebar?.openSearch())" @archive="router.push('/settings/archived')" />
    <div v-show="!inSettings" class="chat-sidebar-container" :inert="inSettings" :aria-hidden="inSettings || undefined">
      <ChatSidebar
        ref="sidebar" v-model:open="chatSidebarOpen"
        :demo="mode === 'mock'" :conversations="chat.pagination?.conversations.value ?? conversations.visible.value" :archived="conversations.archived.value"
        :active-id="conversations.activeId.value" :remove-conversation="chat.remove" :pagination="chat.pagination"
        @new-chat="newChat" @select="conversations.select" @rename="conversations.rename"
        @archive="conversations.archive" @restore="conversations.restore"
        @settings="openSettings"
      />
    </div>
    <main v-show="!inSettings" id="chat-main" class="chat-main" aria-label="Chat" tabindex="-1" :inert="inSettings">
      <ChatHeader v-model:model="modelId" :sidebar-open="sidebarOpen" :busy="stream.busy.value" :demo="mode === 'mock'" @toggle-sidebar="sidebarOpen = !sidebarOpen" @new-chat="newChat" />
      <div class="chat-content" :data-empty="chat.visible.value.length === 0">
        <p v-if="chat.pagination?.historyLoading.value" role="status" class="p-4 text-sm text-muted">Chat wird geladen …</p>
        <div v-if="chat.pagination?.historyError.value" class="p-4 text-sm text-warning">
          <details><summary>Chat konnte nicht geladen werden.</summary><p>{{ chat.pagination.historyError.value }}</p></details>
          <UButton color="neutral" variant="link" label="Chat erneut laden" @click="chat.pagination.retryHistory" />
        </div>
        <EmptyChatState v-if="chat.visible.value.length === 0 && !chat.pagination?.historyLoading.value && !chat.pagination?.historyError.value" />
        <ChatTimeline v-show="chat.visible.value.length > 0" :messages="chat.visible.value" :conversation-id="conversations.activeId.value" :busy="stream.busy.value || Boolean(chat.pagination?.historyLoading.value)" :variants="chat.variants" :variant-summary="chat.variantSummary" :persistent-scroll="Boolean(chat.pagination)" :has-older="chat.pagination?.hasOlder.value" :older-loading="chat.pagination?.olderLoading.value" :load-older="chat.pagination?.loadOlder" :can-continue="chat.canContinue" @reference="addReference" @continue="continueResponse" @edit="beginEdit" @regenerate="regenerateResponse" @select-variant="chat.selectVariant" />
        <div class="composer-dock">
          <div v-if="modelError || modelNotice" class="px-4 pb-2 text-sm text-muted">
            <details><summary>Modellzugriff prüfen</summary><p>{{ modelError || modelNotice }}</p></details>
            <UButton v-if="fallbackId && !canSend" color="neutral" variant="link" label="Verfügbares Modell auswählen" @click="chooseFallback" />
            <UButton color="neutral" variant="link" label="Modelle neu laden" :loading="modelsLoading" @click="refreshModels()" />
          </div>
          <p class="composer-note">{{ t('disclaimer') }}</p>
          <ChatComposer ref="composer" v-model="draft" v-model:model="modelId" :conversation-mode="conversations.active.value?.conversationMode ?? 'normal'" :reasoning-preference="reasoningPreference" :settings-busy="chat.settingsBusy.value" :learning-available="mode !== 'real' && chat.backendReady.value" :busy="stream.busy.value" :model-unavailable="!canSend" :input-error="chat.drafts.error.value" :streaming="stream.status.value === 'streaming'" :cancellation-requested="stream.cancellationRequested.value" :files="attachments.files.value" :upload-available="attachments.available.value" :upload-unavailable-reason="uploadUnavailableReason" :upload-blocked="attachments.blocked.value" :image-supported="attachments.imageCompatible.value" :upload-error="attachments.error.value" :upload-error-notified="attachments.errorNotified.value" @mode="chat.setConversationMode" @reasoning="chat.setReasoningPreference" @files="attachments.add" @remove-file="attachments.remove" @retry-file="attachments.retry" @refresh-files="attachments.refresh" @send="send" @stop="stop" />
          <div v-if="chat.settingsError.value" class="px-4 pt-2 text-sm text-error"><details><summary>Einstellung nicht gespeichert.</summary><p>{{ chat.settingsError.value }}</p></details> <UButton label="Einstellung erneut speichern" color="neutral" variant="link" @click="chat.retryConversationSettings" /></div>
          <p v-if="chat.drafts.error.value" role="alert" class="mt-2 text-center text-xs text-error">{{ chat.drafts.error.value }}</p>
        </div>
        <div class="chat-status" :data-attention="stream.busy.value && chat.generatingConversationId.value !== conversations.activeId.value" role="status" aria-live="polite" aria-atomic="true" :data-generation-status="stream.status.value">
          <template v-if="stream.busy.value && chat.generatingConversationId.value !== conversations.activeId.value">
            <UButton color="neutral" variant="link" size="xs" label="Antwort läuft in einem anderen Chat" @click="selectRunningChat" />
          </template>
          <span v-else-if="stream.status.value === 'submitting'">Antwort wird vorbereitet …</span>
          <span v-else-if="stream.status.value === 'streaming'">{{ stream.cancellationRequested.value ? 'Antwort wird gestoppt …' : 'noris AI antwortet …' }}</span>
          <span v-else-if="stream.status.value === 'cancelled'">Antwort gestoppt.</span>
          <span v-else-if="stream.status.value === 'completed'" class="sr-only">Antwort abgeschlossen.</span>
        </div>
        <details v-if="chat.storageWarning.value" class="px-4 pb-3 text-center text-xs text-warning"><summary>Sicherung und Änderungen prüfen</summary><p>{{ chat.storageWarning.value }}</p><UButton v-if="chat.retryPersistence.value" color="neutral" variant="link" label="Erneut speichern" @click="chat.retryPersistence.value?.()" /></details>
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
    <slot />
  </div>
</template>
